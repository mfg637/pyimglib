import abc
import io
import math
import os
import logging
import pathlib

from . import webp_transcoder, base_transcoder, webp_anim_converter, avif_transcoder, srs_transcoder, srs_video_loop, \
    noise_detection
from . import encoders
from .. import config
import PIL.Image
logger = logging.getLogger(__name__)


class PNGTranscode(base_transcoder.BaseTranscoder):
    __metaclass__ = abc.ABCMeta

    lossy_encoder_type = None
    lossless_encoder_type = None
    animation_encoder_type = None

    def _apng_test_convert(self, img):
        if img.custom_mimetype == "image/apng":
            self._animated = True
            self._fext = 'webm'
            config.VIDEOLOOP_CRF = config.APNG_VIDEOLOOP_CRF
            #self.animation_encode()
            config.VIDEOLOOP_CRF = config.GIF_VIDEOLOOP_CRF
            img.close()
            return None

    @abc.abstractmethod
    def _invalid_file_exception_handle(self, e):
        pass

    def __init__(self, source, path, file_name, force_lossless=False):
        base_transcoder.BaseTranscoder.__init__(self, source, path, file_name)
        #webp_transcoder.WEBP_output.__init__(self, source, path, file_name, force_lossless)
        self._animated = False
        self._lossless = False
        self._lossless_data = b''
        self._lossy_data = b''
        self._force_lossless = force_lossless

    def get_converter_type(self):
        return webp_anim_converter.APNGconverter

    def webp_lossy_encode(self, img: PIL.Image.Image) -> None:
        lossy_out_io = io.BytesIO()
        img.save(lossy_out_io, format="WEBP", lossless=False, quality=self._quality, method=6)
        self._lossy_data = lossy_out_io.getbuffer()

    def _encode(self):
        img = self._open_image()
        #self._core_encoder(img)
        self._lossless_encoder: encoders.Encoder = self.lossless_encoder_type(img)
        self._lossy_encoder: encoders.Encoder = self.lossy_encoder_type(img)

        self._lossless = False
        self._animated = False
        #self._apng_test_convert(img)
        if self._animated:
            return
        if img.mode in {'1', 'P', 'PA'}:
            raise base_transcoder.NotOptimizableSourceException()
        self._lossless = True \
            if noise_detection.noise_detection(img) == noise_detection.NoisyImageEnum.NOISELESS else False
        try:
            if (img.width > encoders.webp_encoder.MAX_SIZE) | (img.height > encoders.webp_encoder.MAX_SIZE):
                img.thumbnail(
                    (encoders.webp_encoder.MAX_SIZE, encoders.webp_encoder.MAX_SIZE),
                    PIL.Image.Resampling.LANCZOS
                )
            else:
                img.load()
        except OSError as e:
            self._invalid_file_exception_handle(e)
            raise base_transcoder.NotOptimizableSourceException()
        ratio = 80
        if self._force_lossless:
            self._quality = 100
            self._lossless = True
            self._lossless_data = self._lossless_encoder.encode(100)
            self._output_size = len(self._lossless_data)
        else:
            if self._lossless:
                ratio = 40
                self._lossless_data = self._lossless_encoder.encode(100)
                logging.debug("lossless size", len(self._lossless_data))
            self._lossy_data = self._lossy_encoder.encode(self._quality)
            #self._lossy_encode(img)
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
                    self._lossy_data = self._lossy_encoder.encode(self._quality)
                    #self._lossy_encode(img)
                    self._output_size = len(self._lossy_data)
                    ratio = math.ceil(ratio // config.WEBP_QSCALE)
        img.close()

    def _save(self):
        if self._lossless:
            self._lossless_encoder.save(self._lossless_data, pathlib.Path(self._path), self._file_name)
        else:
            self._lossless_encoder.save(self._lossy_data, pathlib.Path(self._path), self._file_name)


# class PNG_AVIF_Transcode(PNGTranscode, avif_transcoder.AVIF_WEBP_output, metaclass=abc.ABCMeta):
#     def __init__(self, source, path: str, file_name: str, force_lossless):
#         PNGTranscode.__init__(self, source, path, file_name, force_lossless)
#         avif_transcoder.AVIF_WEBP_output.__init__(self, source, path, file_name, force_lossless)
#
#     def _encode(self):
#         img = self._open_image()
#         avif_transcoder.AVIF_WEBP_output._core_encoder(self, img)
#
#     def _save(self):
#         return avif_transcoder.AVIF_WEBP_output._save_image(self)
#
#
# class PNG_SRS_Transcode(PNGTranscode, srs_transcoder.SrsTranscoder, metaclass=abc.ABCMeta):
#     def __init__(self, source, path: str, file_name: str, item_data: dict, metadata):
#         PNGTranscode.__init__(self, source, path, file_name, item_data)
#         srs_transcoder.SrsTranscoder.__init__(self, source, path, file_name, item_data, metadata)
#
#     def _apng_test_convert(self, img):
#         if img.custom_mimetype == "image/apng":
#             self._animated = True
#             self._fext = 'webm'
#             config.VIDEOLOOP_CRF = config.APNG_VIDEOLOOP_CRF
#             srs_video_loop.SrsVideoLoopOutput.animation_encode(self)
#             config.VIDEOLOOP_CRF = config.GIF_VIDEOLOOP_CRF
#             img.close()
#             return None
#
#     def _encode(self):
#         img = self._open_image()
#         srs_transcoder.SrsTranscoder._core_encoder(self, img)
#
#     def _save(self):
#         if self._animated:
#             return srs_video_loop.SrsVideoLoopOutput._save(self)
#         else:
#             return srs_transcoder.SrsTranscoder._save_image(self)


class PNGFileTranscode(base_transcoder.FilePathSource, base_transcoder.SourceRemovable, PNGTranscode):
    def __init__(self, source: str, path: str, file_name: str, force_lossless):
        base_transcoder.FilePathSource.__init__(self, source, path, file_name)
        PNGTranscode.__init__(self, source, path, file_name, force_lossless)

    def _invalid_file_exception_handle(self, e):
        logging.warning('invalid file ' + self._source + ' ({}) has been deleted'.format(e))
        os.remove(self._source)

    def _set_utime(self) -> None:
        os.utime(self._output_file + '.' + self._fext, (self._atime, self._mtime))

    def _optimisations_failed(self):
        if self._animated:
            self.gif_optimisations_failed()
        logging.warning("save " + self._source)
        os.remove(self._output_file + '.webp')
        return self._source

    def _all_optimisations_failed(self):
        logging.warning("save " + self._source)
        os.remove(self._output_file)


# class AVIF_PNGFileTranscode(PNGFileTranscode, PNG_AVIF_Transcode):
#     def __init__(self, source: str, path: str, file_name: str, item_data: dict):
#         PNGFileTranscode.__init__(self, source, path, file_name, item_data)
#         PNG_AVIF_Transcode.__init__(self, source, path, file_name, item_data)
#
#
# class SRS_PNGFileTranscode(PNGFileTranscode, PNG_SRS_Transcode):
#     def __init__(self, source: str, path: str, file_name: str, item_data: dict, metadata):
#         PNGFileTranscode.__init__(self, source, path, file_name, item_data)
#         PNG_SRS_Transcode.__init__(self, source, path, file_name, item_data, metadata)


class PNGInMemoryTranscode(base_transcoder.InMemorySource, PNGTranscode):

    def __init__(self, source: bytearray, path: str, file_name: str, force_lossless):
        base_transcoder.InMemorySource.__init__(self, source, path, file_name)
        PNGTranscode.__init__(self, source, path, file_name, force_lossless)

    def _invalid_file_exception_handle(self, e):
        logging.exception('invalid png data')

    def _optimisations_failed(self):
        if self._animated:
            return self.gif_optimisations_failed()
        else:
            fname = self._output_file + ".png"
            outfile = open(self._output_file + ".png", "bw")
            outfile.write(self._source)
            outfile.close()
            logging.warning("save " + self._output_file + ".png")
            return fname

    def _all_optimisations_failed(self):
        self._animated = False
        self._optimisations_failed()


# class AVIF_PNGInMemoryTranscode(PNGInMemoryTranscode, PNG_AVIF_Transcode):
#     def __init__(self, source, path, file_name, item_data):
#         PNGInMemoryTranscode.__init__(self, source, path, file_name, item_data)
#         PNG_AVIF_Transcode.__init__(self, source, path, file_name, item_data)
#
#
# class SRS_PNGInMemoryTranscode(PNGInMemoryTranscode, PNG_SRS_Transcode):
#     def __init__(self, source, path, file_name, item_data, metadata):
#         PNGInMemoryTranscode.__init__(self, source, path, file_name, item_data)
#         PNG_SRS_Transcode.__init__(self, source, path, file_name, item_data, metadata)
