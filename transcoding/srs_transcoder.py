import math
import pathlib
import logging
from PIL import Image
from . import avif_transcoder, webp_transcoder, noise_detection, base_transcoder, srs_video_loop
from .common import srs
from .. import config

logger = logging.getLogger(__name__)


class SrsTranscoder(avif_transcoder.AVIF_WEBP_output, srs_video_loop.SrsVideoLoopOutput):
    def __init__(self, source, path: str, file_name: str, item_data: dict, metadata):
        avif_transcoder.AVIF_WEBP_output.__init__(self, source, path, file_name, item_data)
        srs_video_loop.SrsVideoLoopOutput.__init__(self, source, path, file_name, item_data, metadata)
        self._content_metadata = metadata

    def _thumbnail_encode_for_lossless(self, img):
        if img.width >= config.srs_thumbnail_for_lossless_trigger_size or \
                img.height >= config.srs_thumbnail_for_lossless_trigger_size:
            self._thumbnail_encode(img, 90)
            self._output_size = len(self._lossless_data) + len(self._webp_lossy_data)

    def _thumbnail_encode(self, img, maxq):
        self._lossy_data = None
        img.thumbnail((config.srs_webp_size_limit, config.srs_webp_size_limit), Image.LANCZOS)
        q_copy = self._quality
        self._quality = min(maxq, self._quality)
        self.webp_lossy_encode(img)
        self._quality = q_copy
        self._webp_lossy_data = self._lossy_data

    def _core_encoder(self, img):
        def _lossless_encode_script():
            self._quality = 100
            self._lossless = True
            self._lossless_encode(img)
            self._output_size = len(self._lossless_data)
            self._thumbnail_encode_for_lossless(img)
        self._lossless = False
        self._animated = False
        self._avif_lossy_data = None
        self._webp_lossy_data = None
        self._apng_test_convert(img)
        if self._animated:
            return
        if img.mode in {'P', 'PA'}:
            _lossless_encode_script()
            return
        elif img.mode == '1':
            raise base_transcoder.NotOptimizableSourceException()
        self._lossless = True \
            if noise_detection.noise_detection(img) == noise_detection.NoisyImageEnum.NOISELESS and \
               img.width <= webp_transcoder.MAX_SIZE and img.height <= webp_transcoder.MAX_SIZE \
               and img.format != "JPEG" else False
        ratio = 80
        if 'vector' in self._item_data['content']:
            _lossless_encode_script()
        else:
            if img.width >= config.srs_avif_trigger_size or img.height >= config.srs_avif_trigger_size:
                if self._lossless:
                    ratio = 40
                    self._lossless_encode(img)
                    logging.debug("lossless size", len(self._lossless_data))
                self.avif_lossy_encode(img)
                if self._lossless:
                    logging.debug("lossy size", len(self._lossy_data), "quality", self._quality)
                if self._lossless and len(self._lossless_data) < len(self._lossy_data):
                    self._lossless = True
                    self._output_size = len(self._lossless_data)
                    self._quality = 100
                    self._thumbnail_encode_for_lossless(img)
                else:
                    self._lossless_data = None
                    self._lossless = False
                    self._output_size = len(self._lossy_data)
                    while ((self._output_size / self._get_source_size()) > ((100 - ratio) * 0.01)) and (self._quality >= 60):
                        self._quality -= 5
                        self.avif_lossy_encode(img)
                        self._output_size = len(self._lossy_data)
                        ratio = math.ceil(ratio // config.SRS_QSCALE)
                    self._avif_lossy_data = self._lossy_data
                    self._thumbnail_encode(img, 90)
                    self._output_size = len(self._avif_lossy_data) + len(self._webp_lossy_data)
                img.close()
            else:
                webp_transcoder.WEBP_output._core_encoder(self, img)
                self._webp_lossy_data = self._lossy_data

    def _save_image(self):
        cl3 = None
        cl2 = None
        cl1 = None
        if not self._animated:
            if self._avif_lossy_data is not None and len(self._avif_lossy_data):
                cl1 = pathlib.Path(self._output_file + '.avif').name
                cl1_file = open(self._output_file + '.avif', 'wb')
                cl1_file.write(self._avif_lossy_data)
                cl1_file.close()
            if self._lossless_data is not None and len(self._lossless_data):
                cl2 = pathlib.Path(self._output_file + '_lossless.webp').name
                cl2_file = open(self._output_file + '_lossless.webp', 'wb')
                cl2_file.write(self._lossless_data)
                cl2_file.close()
                if self._webp_lossy_data is None or len(self._webp_lossy_data) == 0:
                    cl2 = None
                    cl3 = self._file_name + '_lossless.webp'
            if self._webp_lossy_data is not None and len(self._webp_lossy_data):
                cl3 = pathlib.Path(self._output_file + '.webp').name
                cl3_file = open(self._output_file + '.webp', 'wb')
                cl3_file.write(self._webp_lossy_data)
                cl3_file.close()
            srs_data = {
                "ftype": "CLSRS",
                "content": {
                    "media-type": 0,
                    "tags": dict()
                },
                "streams": {
                    "image": {"levels": dict()}
                }
            }
            srs_image_levels = dict()
            if cl1:
                srs_image_levels["1"] = cl1
            if cl2:
                srs_image_levels['2'] = cl2
            if cl3:
                srs_image_levels["3"] = cl3
            srs_data['streams']['image']['levels'] = srs_image_levels
            return self._srs_write_srs(srs_data)

    def _srs_write_srs(self, srs_data):
        return srs.write_srs(srs_data, self._item_data, self._content_metadata, self._output_file)


