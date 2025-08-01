import pathlib
import tempfile

from . import encoders, base_transcoder
from .. import config, common


class VideoWriter:
    def __init__(self, source, path: pathlib.Path, file_name: str, suffix):
        self._source = source
        self._output_file = path.joinpath(file_name)
        self._suffix = suffix

    def transcode(self):
        f = None
        self._output_file = self._output_file.with_suffix(self._suffix)
        if isinstance(self._source, (bytes, bytearray)):
            f = open(self._output_file, "bw")
            f.write(self._source)
            f.close()
        return 0, 0, 0, 0, self._output_file


class VideoTranscoder:
    video_encoder_type = None

    def __init__(self, source, path: pathlib.Path, file_name):
        self._source = source
        self._path = path
        self._output_file = None
        self._file_name = file_name
        self._video_encoder: encoders.FilesEncoder = None
        self.encoded_data = None

    def transcode(self):
        self._output_file = self._path.joinpath(self._file_name)

        self._quality = 100 - config.VIDEO_CRF

        if issubclass(self.video_encoder_type, encoders.encoder.FilesEncoder):
            self._video_encoder: encoders.FilesEncoder = \
                self.video_encoder_type(config.VIDEO_CRF)
            with common.utils.InputSourceFacade(self._source) as sh:
                input_file = sh.get_file_path()
                self._output_file = self._video_encoder.encode(
                    input_file, self._output_file
                )
            try:
                self._output_size = self._video_encoder.calc_file_size()
            except FileNotFoundError:
                raise base_transcoder.NotSupportedSourceException()
        elif issubclass(
            self.video_encoder_type, encoders.encoder.BytesEncoder
        ):
            self._video_encoder: encoders.encoder.BytesEncoder = \
                self.video_encoder_type(self._source)
            self.encoded_data = self._video_encoder.encode(config.VIDEO_CRF)
            self._output_file = self._video_encoder.save(
                self.encoded_data, pathlib.Path(self._path), self._file_name
            )
        else:
            raise NotImplementedError(self.video_encoder_type)

        return (
            self._output_size,
            len(self._source),
            self._quality,
            1,
            self._output_file
        )
