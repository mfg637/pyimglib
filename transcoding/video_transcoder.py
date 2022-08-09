import os
import pathlib
import tempfile

from . import encoders
from .. import config


class VideoWriter:
    def __init__(self, source, path, file_name, suffix):
        self._source = source
        self._output_file = os.path.join(path, file_name)
        self._suffix = suffix

    def transcode(self):
        f = None
        clx = self._output_file+self._suffix
        if isinstance(self._source, (bytes, bytearray)):
            f = open(clx, "bw")
            f.write(self._source)
            f.close()
        return 0, 0, 0, 0


class VideoTranscoder:
    video_encoder_type = None

    def __init__(self, source, path: pathlib.Path, file_name):
        self._source = source
        self._path = path
        self._output_file = None
        self._file_name = file_name
        self._video_encoder: encoders.VideoEncoder = None

    def transcode(self):
        self._output_file = self._path.joinpath(self._file_name)
        self._video_encoder: encoders.VideoEncoder = self.video_encoder_type(config.VIDEO_CRF)
        tmpfile = None
        if type(self._source) is str:
            input_file = pathlib.Path(self._source)
        elif isinstance(self._source, pathlib.Path):
            input_file = self._source
        else:
            tmpfile = tempfile.NamedTemporaryFile(delete=True)
            input_file = pathlib.Path(tmpfile.name)
            tmpfile.write(self._source)
        self._output_file = self._video_encoder.encode(input_file, self._output_file)
        if tmpfile is not None:
            tmpfile.close()
        return 0, 0, 0, 0, self._output_file
