import abc
import io
import logging
import math
import os
import pathlib
import tempfile

import PIL.Image
from PIL import Image

from . import base_transcoder, encoders
from .. import config

logger = logging.getLogger(__name__)


class GIFTranscode(base_transcoder.BaseTranscoder):
    __metaclass__ = abc.ABCMeta

    lossy_encoder_type = None
    animation_encoder_type = None

    def __init__(self, source, path: pathlib.Path, file_name: str):
        super().__init__(source, path, file_name)

    @abc.abstractmethod
    def _invalid_file_exception_handle(self, e):
        pass

    def _encode(self):
        img = self._open_image()
        #self._animated = img.is_animated
        if self._animated:
            self._quality = 100 - config.GIF_VIDEOLOOP_CRF
            self._output_file = self._path.joinpath(self._file_name)
            self._animation_encoder: encoders.VideoEncoder = self.animation_encoder_type(config.GIF_VIDEOLOOP_CRF)
            tmpfile = None
            if type(self._source) is str:
                input_file = pathlib.Path(self._source)
            elif isinstance(self._source, pathlib.Path):
                input_file = self._source
            else:
                tmpfile = tempfile.NamedTemporaryFile(delete=True)
                input_file = pathlib.Path(tmpfile.name)
                tmpfile.write(self._source)
            self._output_file = self._animation_encoder.encode(input_file, self._output_file)
            if tmpfile is not None:
                tmpfile.close()
            try:
                if isinstance(self.animation_encoder_type, encoders.dash_encoder.DASHEncoder):
                    self._output_size = encoders.dash_encoder.DASHEncoder.get_file_size(self._output_file)
                else:
                    self._output_size = os.path.getsize(self._output_file)
            except FileNotFoundError:
                raise base_transcoder.NotOptimizableSourceException()
        else:
            self._lossy_encoder: encoders.Encoder = self.lossy_encoder_type(self._source, img)

            self._animated = False
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
                raise base_transcoder.NotOptimizableSourceException()
            ratio = 80
            self._lossy_data = self._lossy_encoder.encode(self._quality)
            self._output_size = len(self._lossy_data)
            while ((self._output_size / self._get_source_size()) > ((100 - ratio) * 0.01)) and (
                    self._quality >= 60):
                self._quality -= 5
                self._lossy_data = self._lossy_encoder.encode(self._quality)
                self._output_size = len(self._lossy_data)
                ratio = math.ceil(ratio // config.WEBP_QSCALE)
        img.close()

    def _save(self):
        if self._animated:
            pass
        else:
            self._output_file = self._lossy_encoder.save(
                self._lossy_data, pathlib.Path(self._path), self._file_name
            )

    @abc.abstractmethod
    def _all_optimisations_failed(self):
        pass

    def _optimisations_failed(self):
        return self._all_optimisations_failed()


class GIFFileTranscode(base_transcoder.FilePathSource, base_transcoder.SourceRemovable, GIFTranscode):

    def __init__(self, source: str, path: pathlib.Path, file_name: str):
        GIFTranscode.__init__(self, source, path, file_name)
        base_transcoder.FilePathSource.__init__(self, source, path, file_name)
        img = Image.open(source)
        self._animated = img.is_animated
        img.close()

    def _set_utime(self) -> None:
        os.utime(self._output_file, (self._atime, self._mtime))

    def _all_optimisations_failed(self):
        logger.warning("save " + self._source)
        if isinstance(self.animation_encoder_type, encoders.dash_encoder.DASHEncoder):
            encoders.dash_encoder.DASHEncoder.delete_result(self._output_file)
        else:
            os.remove(self._output_file)
        return self._source

    def _invalid_file_exception_handle(self, e):
        logging.warning('invalid file ' + self._source + ' ({}) has been deleted'.format(e))
        os.remove(self._source)


class GIFInMemoryTranscode(base_transcoder.InMemorySource, GIFTranscode):

    def __init__(self, source: bytearray, path: pathlib.Path, file_name: str):
        base_transcoder.InMemorySource.__init__(self, source, path, file_name)
        GIFTranscode.__init__(self, source, path, file_name)
        in_io = io.BytesIO(self._source)
        img = Image.open(in_io)
        self._animated = img.is_animated
        img.close()

    def _all_optimisations_failed(self):
        if isinstance(self.animation_encoder_type, encoders.dash_encoder.DASHEncoder):
            encoders.dash_encoder.DASHEncoder.delete_result(self._output_file)
        self._output_file = self._path.joinpath(self._file_name).with_suffix(".gif")
        outfile = open(self._output_file, "bw")
        outfile.write(self._source)
        outfile.close()
        logger.warning("save " + str(self._output_file))
        return self._output_file

    def _invalid_file_exception_handle(self, e):
        logging.exception('invalid GIF data')
