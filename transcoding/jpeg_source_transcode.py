import abc
import io
import logging
import math
import os
import pathlib
import subprocess
import tempfile

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
    lossless_jpeg_transcoder_type = None

    def __init__(self, source, path: pathlib.Path, file_name: str):
        super().__init__(source, path, file_name)
        self._lossy_encoder: encoders.BytesEncoder | encoders.FilesEncoder = None
        self.lossless_transcoder = None
        self.lossless_data = None

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

    def size_treshold(self, img):
        return img.width > 1024 or img.height > 1024

    def _encode(self):
        self._arithmetic_check()
        img = self._open_image()

        self.lossless_transcoder: encoders.BytesEncoder = self.lossless_jpeg_transcoder_type(self._source, img)
        self.lossless_data = self.lossless_transcoder.encode(100)

        if self.size_treshold(img):
            self._lossy_output = True
            if issubclass(self.lossy_encoder_type, encoders.encoder.FilesEncoder):
                self._lossy_encoder: encoders.FilesEncoder = self.lossy_encoder_type(
                    self._quality, self._get_source_size(), 80
                )

                tmpfile = None
                if type(self._source) is str:
                    input_file = pathlib.Path(self._source)
                elif isinstance(self._source, pathlib.Path):
                    input_file = self._source
                else:
                    tmpfile = tempfile.NamedTemporaryFile(delete=True)
                    input_file = pathlib.Path(tmpfile.name)
                    tmpfile.write(self._source)

                self._output_file = self._path.joinpath(self._file_name)
                self._output_file = self._lossy_encoder.encode(input_file, self._output_file)
                if tmpfile is not None:
                    tmpfile.close()
                self._output_size = self._lossy_encoder.calc_file_size()
            else:
                self._lossy_encoder: encoders.BytesEncoder = self.lossy_encoder_type(self._source, img)
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

        logging.debug("lossy size: {}".format(self._output_size))
        logging.debug("lossless size: {}".format(len(self.lossless_data)))

        if self._lossy_output and len(self.lossless_data) > self._output_size:
            self._lossy_output = True
        else:
            self._lossy_output = False
            if isinstance(self._lossy_encoder, encoders.FilesEncoder):
                self._lossy_encoder.delete_result()
            self._output_size = len(self.lossless_data)

    def _save(self):
        if self._lossy_output:
            if issubclass(self.lossy_encoder_type, encoders.encoder.FilesEncoder):
                return self._output_file
            self._output_file = self._lossy_encoder.save(self._lossy_data, self._path, self._file_name)
            return self._output_file
        else:
            self._output_file = self.lossless_transcoder.save(self.lossless_data, self._path, self._file_name)
            return self._output_file


class JPEGFileTranscode(base_transcoder.FilePathSource, base_transcoder.UnremovableSource, JPEGTranscode):
    def __init__(self, source: pathlib.Path, path: pathlib.Path, file_name: str):
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
        if isinstance(self._lossy_encoder, encoders.encoder.FilesEncoder):
            self._lossy_encoder.delete_result()

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
        if isinstance(self._lossy_encoder, encoders.encoder.FilesEncoder):
            self._lossy_encoder.delete_result()
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
