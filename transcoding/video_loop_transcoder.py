import pathlib

from . import encoders
from .. import config


class VideoLoopTranscoder:
    video_encoder_type = None

    def __init__(self, source, path: pathlib.Path, file_name, rewrite:bool):
        self._source = source
        self._path = path
        self._output_file = path.joinpath(file_name)
        self._file_name = file_name
        self.encoded_data = None
        self.rewrite = rewrite

    def transcode(self):
        self._output_file = self._path.joinpath(self._file_name)

        self._quality = 100 - config.GIF_VIDEOLOOP_CRF

        x264_vloop_encoder = \
            encoders.mpeg4_encoder.make_x264_vloop_encoder(self._source)
        self._output_file = x264_vloop_encoder.encode(
            config.GIF_VIDEOLOOP_CRF, self._output_file, self.rewrite
        )
        self._output_size = self._output_file.stat().st_size

        return (
            self._output_size,
            len(self._source),
            self._quality,
            1,
            self._output_file
        )
