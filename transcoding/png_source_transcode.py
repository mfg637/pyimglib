import abc
import io
import logging
import math
import os
import pathlib
import tempfile
import typing

import PIL.Image

from . import base_transcoder, noise_detection
from . import encoders
from .. import config

logger = logging.getLogger(__name__)


class PNGTranscode(base_transcoder.BaseTranscoder):
    __metaclass__ = abc.ABCMeta

    lossy_encoder_type: typing.Type[encoders.encoder.BytesEncoder] | typing.Type[encoders.encoder.FilesEncoder] = None
    lossless_encoder_type: typing.Type[encoders.encoder.BytesEncoder] | typing.Type[encoders.encoder.FilesEncoder] = None
    animation_encoder_type: typing.Type[encoders.encoder.FilesEncoder] = None

    def __init__(self, source, path, file_name, force_lossless=False):
        base_transcoder.BaseTranscoder.__init__(self, source, path, file_name)
        self._animated = False
        self._lossless = False
        self._output_file = self._path.joinpath(self._file_name)
        self._lossless_data = b''
        self._lossy_data = b''
        self._force_lossless = force_lossless
        self._lossless_encoder: encoders.FilesEncoder | None = None
        self.lossy_encoder = None
        self._animation_encoder = None
        self._anim_output_filename = None

    def _apng_test_convert(self, img):
        if img.custom_mimetype == "image/apng":
            self._animated = True
            # self._fext = 'webm'
            self._quality = 100 - config.APNG_VIDEOLOOP_CRF
            self._anim_output_filename = self._path.joinpath(self._file_name)
            self._animation_encoder: encoders.FilesEncoder = self.animation_encoder_type(config.APNG_VIDEOLOOP_CRF)
            tmpfile = None
            if type(self._source) is str:
                input_file = pathlib.Path(self._source)
            elif isinstance(self._source, pathlib.Path):
                input_file = self._source
            else:
                tmpfile = tempfile.NamedTemporaryFile(delete=True)
                input_file = pathlib.Path(tmpfile.name)
                tmpfile.write(self._source)
            self._anim_output_filename = self._animation_encoder.encode(input_file, self._anim_output_filename)
            if tmpfile is not None:
                tmpfile.close()
            try:
                if isinstance(self.animation_encoder_type, encoders.dash_encoder.DASHEncoder):
                    self._output_size = encoders.dash_encoder.DASHEncoder.get_file_size(self._anim_output_filename)
                else:
                    self._output_size = os.path.getsize(self._anim_output_filename)
            except FileNotFoundError:
                raise base_transcoder.NotSupportedSourceException()
            else:
                self._output_file = self._anim_output_filename
            img.close()
            return

    @abc.abstractmethod
    def _invalid_file_exception_handle(self, e):
        pass

    def webp_lossy_encode(self, img: PIL.Image.Image) -> None:
        lossy_out_io = io.BytesIO()
        img.save(lossy_out_io, format="WEBP", lossless=False, quality=self._quality, method=6)
        self._lossy_data = lossy_out_io.getbuffer()

    def anim_transcoding_failed(self):
        if isinstance(self._anim_output_filename, pathlib.Path):
            if isinstance(self.animation_encoder_type, encoders.dash_encoder.DASHEncoder):
                encoders.dash_encoder.DASHEncoder.delete_result(self._output_file)
            else:
                self._anim_output_filename.unlink(missing_ok=True)

    def _encode(self):
        if config.custom_pillow_image_limits != -1:
            PIL.Image.MAX_IMAGE_PIXELS = config.custom_pillow_image_limits
        img = self._open_image()
        if issubclass(self.lossless_encoder_type, encoders.encoder.FilesEncoder):
            self._lossless_encoder = self.lossless_encoder_type(
                100, self._get_source_size(), 1
            )
        elif issubclass(self.lossless_encoder_type, encoders.encoder.BytesEncoder):
            self._lossless_encoder = encoders.encoder.BytesEncoderWrapper(
                self.lossless_encoder_type, 100, self._get_source_size(), 1
            )

        self._lossless = False
        self._animated = False
        self._apng_test_convert(img)
        if self._animated:
            return
        if img.mode in {'1', 'P', 'PA'}:
            raise base_transcoder.NotSupportedSourceException()
        self._lossless = True \
            if noise_detection.noise_detection(img) == noise_detection.NoisyImageEnum.NOISELESS else False
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

        tmpfile = None
        if type(self._source) is str:
            input_file = pathlib.Path(self._source)
        elif isinstance(self._source, pathlib.Path):
            input_file = self._source
        else:
            tmpfile = tempfile.NamedTemporaryFile(delete=True)
            input_file = pathlib.Path(tmpfile.name)
            tmpfile.write(self._source)

        ratio = 80
        if self._force_lossless:
            self._quality = 100
            self._lossless = True
            self._lossless_data = self._lossless_encoder.encode(
                input_file, self._output_file.with_stem("{}_lossless".format(self._output_file.stem))
            )
            self._output_size = self._lossless_encoder.calc_file_size()
        else:
            if self._lossless:
                ratio = 40
                self._lossless_data = self._lossless_encoder.encode(
                    input_file, self._output_file.with_stem("{}_lossless".format(self._output_file.stem))
                )
                logging.debug("lossless size {}".format(self._lossless_encoder.calc_file_size()))
            if issubclass(self.lossy_encoder_type, encoders.encoder.FilesEncoder):
                self.lossy_encoder: encoders.FilesEncoder = self.lossy_encoder_type(
                    self._quality, self._get_source_size(), ratio
                )

                self._output_file = self._path.joinpath(self._file_name)
                self._output_file = self.lossy_encoder.encode(input_file, self._output_file)

                self._output_size = self.lossy_encoder.calc_file_size()
                if self._lossless and self._lossless_encoder.calc_file_size() < self._output_size:
                    self._lossless = True
                    self.lossy_encoder.delete_result()
                    self._output_size = self._lossless_encoder.calc_file_size()
                    self._quality = 100
                else:
                    self._lossless_encoder.delete_result()
                    self._lossless = False
            else:
                self.lossy_encoder: encoders.BytesEncoder = self.lossy_encoder_type(self._source, img)
                self._lossy_data = self.lossy_encoder.encode(self._quality)
                if self._lossless:
                    logging.debug("lossy size {} quality {}".format(len(self._lossy_data), self._quality))
                if self._lossless and self._lossless_encoder.calc_file_size() < len(self._lossy_data):
                    self._lossless = True
                    self._lossy_data = None
                    self._output_size = self._lossless_encoder.calc_file_size()
                    self._quality = 100
                else:
                    self._lossless_encoder.delete_result()
                    self._lossless = False
                    self._output_size = len(self._lossy_data)
                    while ((self._output_size / self._get_source_size()) > ((100 - ratio) * 0.01)) and (
                            self._quality >= 60):
                        self._quality -= 5
                        self._lossy_data = self.lossy_encoder.encode(self._quality)
                        self._output_size = len(self._lossy_data)
                        ratio = math.ceil(ratio // config.WEBP_QSCALE)

        if tmpfile is not None:
            tmpfile.close()

        img.close()

    def _save(self):
        if self._animated:
            pass
        elif self._lossless:
            self._output_file = self._lossless_encoder.get_files()[-1]
        else:
            if issubclass(self.lossy_encoder_type, encoders.encoder.FilesEncoder):
                return self._output_file
            self._output_file = self.lossy_encoder.save(
                self._lossy_data, pathlib.Path(self._path), self._file_name
            )
        return self._output_file


class PNGFileTranscode(base_transcoder.FilePathSource, base_transcoder.SourceRemovable, PNGTranscode):
    def __init__(self, source: pathlib.Path, path: pathlib.Path, file_name: str, force_lossless):
        base_transcoder.FilePathSource.__init__(self, source, path, file_name)
        PNGTranscode.__init__(self, source, path, file_name, force_lossless)

    def _invalid_file_exception_handle(self, e):
        logging.warning('invalid file ' + self._source + ' ({}) has been deleted'.format(e))
        os.remove(self._source)

    def _set_utime(self) -> None:
        os.utime(self._output_file, (self._atime, self._mtime))

    def _optimisations_failed(self):
        if self._animated:
            self.anim_transcoding_failed()
        logging.warning("save {}".format(self._source))
        if issubclass(self.lossy_encoder_type, encoders.encoder.FilesEncoder):
            self.lossy_encoder.delete_result()
        elif self._output_file is not None:
            self._output_file.unlink(missing_ok=True)
        return self._source

    def _all_optimisations_failed(self):
        logging.warning("save {}".format(self._source))
        if self._output_file is not None:
            self._output_file.unlink(missing_ok=True)


class PNGInMemoryTranscode(base_transcoder.InMemorySource, PNGTranscode):

    def __init__(self, source: bytearray, path: pathlib.Path, file_name: str, force_lossless):
        base_transcoder.InMemorySource.__init__(self, source, path, file_name)
        PNGTranscode.__init__(self, source, path, file_name, force_lossless)

    def _invalid_file_exception_handle(self, e):
        logging.exception('invalid png data')

    def _optimisations_failed(self):
        if self._animated:
            return self.anim_transcoding_failed()
        else:
            if not self._lossless and issubclass(self.lossy_encoder_type, encoders.encoder.FilesEncoder) and \
                    self.lossy_encoder is not None:
                self.lossy_encoder.delete_result()
            self._output_file = self._output_file.with_suffix(".png")
            outfile = open(self._output_file, "bw")
            outfile.write(self._source)
            outfile.close()
            logging.warning("save " + str(self._output_file))
            return self._output_file

    def _all_optimisations_failed(self):
        self._animated = False
        self._optimisations_failed()
