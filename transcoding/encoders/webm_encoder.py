import pathlib
import subprocess

from ... import config
from ..common import run_subprocess

from .encoder import VideoEncoder


class WEBMEncoder(VideoEncoder):
    def __init__(self, encoder: str, pixel_format: str, crf: int):
        self._encoder = encoder
        self._pixel_format = pixel_format
        self._crf = crf

    def encode(self, input_file: pathlib.Path, output_file: pathlib.Path) -> pathlib.Path:
        output_file = output_file.with_suffix(".webm")
        commandline = [
                'ffmpeg'
        ]
        if config.allow_rewrite:
            commandline += ['-y']
        commandline += [
                '-loglevel', 'error',
                '-i', input_file,
                '-pix_fmt', self._pixel_format,
                '-c:v', self._encoder,
                '-crf', str(self._crf),
                '-b:v', '0',
                '-profile:v', '0',
                '-cpu-used', '4',
                '-row-mt', '1',
                '-threads', str(config.encoding_threads),
                '-f', 'webm',
                output_file
            ]
        run_subprocess(commandline)
        return output_file


class VP9Encoder(WEBMEncoder):
    def __init__(self, crf: int):
        super().__init__("libvpx-vp9", "yuva420p", crf)


class AV1Encoder(WEBMEncoder):
    def __init__(self, crf: int):
        super().__init__("libaom-av1", "yuva420p10le", crf)


