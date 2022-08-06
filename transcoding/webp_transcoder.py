import abc
import io
import math
import logging
from . import webm_transcoder, base_transcoder, noise_detection
from .. import config
from PIL import Image

logging.getLogger(__name__)


MAX_SIZE = 16383

if config.MAX_SIZE is not None:
    MAX_SIZE = min(16383, config.MAX_SIZE)


class WEBP_output(webm_transcoder.WEBM_VideoOutputFormat):
    __metaclass__ = abc.ABCMeta

    def __init__(self, source, path: str, file_name: str, forse_lossess=False):
        webm_transcoder.WEBM_VideoOutputFormat.__init__(self, source, path, file_name, )
        self.file_suffix = '.webp'
        self._lossy_encode = self.webp_lossy_encode
        self._forse_lossless = forse_lossess


    @abc.abstractmethod
    def _apng_test_convert(self, img):
        pass

    def _transparency_check(self, img: Image.Image) -> bool:
        if img.mode in {'RGBA', 'LA'}:
            alpha_histogram = img.histogram()[768:]
            return alpha_histogram[255] != img.width * img.height
        else:
            return False

    @abc.abstractmethod
    def _invalid_file_exception_handle(self, e):
        pass

    def _lossless_encode(self, img: Image.Image) -> None:
        lossless_out_io = io.BytesIO()
        img.save(lossless_out_io, format="WEBP", lossless=True, quality=100, method=6)
        self._lossless_data = lossless_out_io.getbuffer()

    def webp_lossy_encode(self, img: Image.Image) -> None:
        lossy_out_io = io.BytesIO()
        img.save(lossy_out_io, format="WEBP", lossless=False, quality=self._quality, method=6)
        self._lossy_data = lossy_out_io.getbuffer()

    def _core_encoder(self, img):
        self._lossless = False
        self._animated = False
        self._apng_test_convert(img)
        if self._animated:
            return
        if img.mode in {'1', 'P', 'PA'}:
            raise base_transcoder.NotOptimizableSourceException()
        self._lossless = True \
            if noise_detection.noise_detection(img) == noise_detection.NoisyImageEnum.NOISELESS else False
        try:
            if (img.width > MAX_SIZE) | (img.height > MAX_SIZE):
                img.thumbnail((MAX_SIZE, MAX_SIZE), Image.LANCZOS)
            else:
                img.load()
        except OSError as e:
            self._invalid_file_exception_handle(e)
            raise base_transcoder.NotOptimizableSourceException()
        ratio = 80
        if self._forse_lossless:
            self._quality = 100
            self._lossless = True
            self._lossless_encode(img)
            self._output_size = len(self._lossless_data)
        else:
            if self._lossless:
                ratio = 40
                self._lossless_encode(img)
                logging.debug("lossless size", len(self._lossless_data))
            self._lossy_encode(img)
            if self._lossless:
                logging.debug("lossy size", len(self._lossy_data), "quality", self._quality)
            if self._lossless and len(self._lossless_data) < len(self._lossy_data):
                self._lossless = True
                self._lossy_data = None
                self._output_size = len(self._lossless_data)
                self._quality = 100
            else:
                self._lossless_data = None
                self._lossless = False
                self._output_size = len(self._lossy_data)
                while ((self._output_size / self._get_source_size()) > ((100 - ratio) * 0.01)) and (self._quality >= 60):
                    self._quality -= 5
                    self._lossy_encode(img)
                    self._output_size = len(self._lossy_data)
                    ratio = math.ceil(ratio // config.WEBP_QSCALE)
        img.close()

    def _save_image(self):
        if not self._animated:
            output_fname = self._output_file + self.file_suffix
            outfile = open(output_fname, 'wb')
            if self._lossless:
                outfile.write(self._lossless_data)
            else:
                outfile.write(self._lossy_data)
            outfile.close()
            return output_fname
