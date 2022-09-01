import abc
import io
import logging
import math
import os
import pathlib
import subprocess

import PIL.Image

from . import base_transcoder, encoders
from .. import decoders, config

logger = logging.getLogger(__name__)


def is_arithmetic_jpg(file_path):
    jpeg_decoder = decoders.jpeg.JPEGDecoder(file_path)
    return jpeg_decoder.arithmetic_coding()


class JPEGTranscode(base_transcoder.BaseTranscoder):
    __metaclass__ = abc.ABCMeta

    lossy_encoder_type = None

    def __init__(self, source, path: pathlib.Path, file_name: str):
        super().__init__(source, path, file_name)
        self._lossy_encoder: encoders.Encoder = None

    @abc.abstractmethod
    def _arithmetic_check(self):
        pass

    @abc.abstractmethod
    def _invalid_file_exception_handle(self, e):
        pass

    @abc.abstractmethod
    def _get_source_data(self):
        pass

    def _all_optimisations_failed(self):
        pass

    def get_converter_type(self):
        return None

    def lossless_encode(self):
        meta_copy = 'all'
        source_data = self._get_source_data()
        process = subprocess.Popen(['jpegtran', '-copy', meta_copy, '-arithmetic'],
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        if type(source_data) is io.BytesIO:
            process.stdin.write(source_data.getvalue())
        else:
            process.stdin.write(source_data)
        process.stdin.close()
        self._optimized_data = process.stdout.read()
        process.stdout.close()
        process.terminate()
        self._output_size = len(self._optimized_data)
        self._output_file = self._path.joinpath(self._file_name)

    def size_treshold(self, img):
        return img.width > 1024 or img.height > 1024

    def _encode(self):
        self._arithmetic_check()
        img = self._open_image()
        if self.size_treshold(img):
            self._lossy_output = True
            self._lossy_encoder: encoders.Encoder = self.lossy_encoder_type(self._source, img)
            try:
                if isinstance(self.lossy_encoder_type, encoders.webp_encoder.WEBPEncoder) and \
                        (img.width > encoders.webp_encoder.MAX_SIZE) | (img.height > encoders.webp_encoder.MAX_SIZE):
                    img.thumbnail(
                        (encoders.webp_encoder.MAX_SIZE, encoders.webp_encoder.MAX_SIZE),
                        PIL.Image.Resampling.LANCZOS
                    )
                else:
                    img.load()
            except OSError as e:
                self._invalid_file_exception_handle(e)
                raise base_transcoder.NotSupportedSourceException()
            ratio = 80
            self._lossy_data = self._lossy_encoder.encode(self._quality)
            self._output_size = len(self._lossy_data)
            while ((self._output_size / self._get_source_size()) > ((100 - ratio) * 0.01)) \
                    and (self._quality >= 60):
                self._quality -= 5
                self._lossy_data = self._lossy_encoder.encode(self._quality)
                self._output_size = len(self._lossy_data)
                ratio = math.ceil(ratio // config.WEBP_QSCALE)
            img.close()
        else:
            img.close()
            self.lossless_encode()

    def _save(self):
        if self._lossy_output:
            self._output_file = self._lossy_encoder.save(self._lossy_data, self._path, self._file_name)
            return self._output_file
        else:
            fname = self._output_file.with_suffix(".jpg")
            outfile = open(fname, 'wb')
            outfile.write(self._optimized_data)
            outfile.close()
            return fname


# class AVIF_JPEG_Transcoder(JPEGTranscode, avif_transcoder.AVIF_WEBP_output):
#     __metaclass__ = abc.ABCMeta
#
#     def get_color_profile(self):
#         subsampling = decoders.jpeg.read_frame_data(self._get_source_data())[1]
#         return self.get_color_profile_by_subsampling(subsampling)
#
#     def __init__(self, source, path: str, file_name: str, item_data: dict):
#         JPEGTranscode.__init__(self, source, path, file_name, item_data)
#         avif_transcoder.AVIF_WEBP_output.__init__(self, source, path, file_name, item_data)
#
#     def _transparency_check(self, img):
#         return False


# class SRS_JPEG_Transcoder(JPEGTranscode, srs_transcoder.SrsTranscoder):
#     __metaclass__ = abc.ABCMeta
#
#     def get_color_profile(self):
#         subsampling = decoders.jpeg.read_frame_data(self._get_source_data())[1]
#         return self.get_color_profile_by_subsampling(subsampling)
#
#     def __init__(self, source, path: str, file_name: str, item_data: dict, metadata):
#         JPEGTranscode.__init__(self, source, path, file_name, item_data)
#         srs_transcoder.SrsTranscoder.__init__(self, source, path, file_name, item_data, metadata)
#
#     def _transparency_check(self, img):
#         return False
#
#     def _encode(self):
#         img = self._open_image()
#         # disable arithmetic encoding for the wide compatibility (compatibility level 4 limitations)
#         self._webp_output = True
#         self._core_encoder(img)


class JPEGFileTranscode(base_transcoder.FilePathSource, base_transcoder.UnremovableSource, JPEGTranscode):
    def __init__(self, source: str, path: pathlib.Path, file_name: str):
        base_transcoder.FilePathSource.__init__(self, source, path, file_name)
        base_transcoder.UnremovableSource.__init__(self, source, path, file_name)
        JPEGTranscode.__init__(self, source, path, file_name)
        self._quality = 100
        self._optimized_data = b''

    def _invalid_file_exception_handle(self, e):
        logging.warning('invalid file ' + self._source + ' ({}) has been deleted'.format(e))
        os.remove(self._source)

    def _arithmetic_check(self):
        try:
            if is_arithmetic_jpg(self._source):
                raise base_transcoder.AlreadyOptimizedSourceException()
        except OSError:
            raise base_transcoder.NotSupportedSourceException()

    def _get_source_data(self):
        source_file = open(self._source, 'br')
        raw_data = source_file.read()
        source_file.close()
        return raw_data

    def _set_utime(self) -> None:
        os.utime(self._source, (self._atime, self._mtime))

    def _optimisations_failed(self):
        pass

    def _invalid_file_exception_handle(self, e):
        logging.warning('invalid file ' + self._source + ' ({}) has been deleted'.format(e))
        os.remove(self._source)


class JPEGInMemoryTranscode(base_transcoder.InMemorySource, JPEGTranscode):
    def __init__(self, source: bytearray, path: pathlib.Path, file_name: str):
        base_transcoder.InMemorySource.__init__(self, source, path, file_name)
        JPEGTranscode.__init__(self, source, path, file_name)
        self._quality = 100
        self._optimized_data = b''

    def _invalid_file_exception_handle(self, e):
        logging.exception('invalid JPEG data')

    def _optimisations_failed(self):
        fname = self._output_file.with_suffix(".jpg")
        outfile = open(fname, "bw")
        outfile.write(self._source)
        outfile.close()
        logging.warning("save " + str(fname))
        return fname

    def _arithmetic_check(self):
        pass

    def _get_source_data(self):
        return io.BytesIO(self._source)

    def _invalid_file_exception_handle(self, e):
        logging.exception('invalid jpeg data')


# class AVIF_JPEGFileTranscode(AVIF_JPEG_Transcoder, JPEGFileTranscode):
#     def __init__(self, source: str, path: str, file_name: str, item_data: dict):
#         JPEGFileTranscode.__init__(self, source, path, file_name)
#         AVIF_JPEG_Transcoder.__init__(self, source, path, file_name, item_data)
#
#
# class AVIF_JPEGInMemoryTranscode(AVIF_JPEG_Transcoder, JPEGInMemoryTranscode):
#     def __init__(self, source: bytearray, path: str, file_name: str, item_data: dict):
#         JPEGInMemoryTranscode.__init__(self, source, path, file_name)
#         AVIF_JPEG_Transcoder.__init__(self, source, path, file_name, item_data)
#
#
# class SRS_JPEGFileTranscode(SRS_JPEG_Transcoder, JPEGFileTranscode):
#     def __init__(self, source: str, path: str, file_name: str, item_data: dict, metadata):
#         JPEGFileTranscode.__init__(self, source, path, file_name)
#         SRS_JPEG_Transcoder.__init__(self, source, path, file_name, item_data, metadata)
#
#
# class SRS_JPEGInMemoryTranscode(SRS_JPEG_Transcoder, JPEGInMemoryTranscode):
#     def __init__(self, source: bytearray, path: str, file_name: str, item_data: dict, metadata):
#         JPEGInMemoryTranscode.__init__(self, source, path, file_name)
#         SRS_JPEG_Transcoder.__init__(self, source, path, file_name, item_data, metadata)
#
#     def _optimisations_failed(self):
#         JPEGInMemoryTranscode._optimisations_failed(self)
#         srs_data = {
#             "ftype": "CLSRS",
#             "content": {
#                 "media-type": 0,
#                 "tags": dict()
#             },
#             "streams": {
#                 "image": {"levels": {"4": self._file_name + ".jpg"}}
#             }
#         }
#         return self._srs_write_srs(srs_data)
