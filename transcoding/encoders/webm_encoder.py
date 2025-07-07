import pathlib
import tempfile

from ... import config
from ...common import run_subprocess, utils

from .encoder import BytesEncoder


class WEBMEncoder(BytesEncoder):
    SUFFIX = ".webm"
    def __init__(self, encoder: str, pixel_format: str, source: bytearray | pathlib.Path):
        BytesEncoder.__init__(self, self.SUFFIX)
        self._encoder = encoder
        self._pixel_format = pixel_format
        self.source: bytearray | pathlib.Path = source

    def encode(self, quality) -> bytes:
        source_handler = utils.InputSourceFacade(self.source)
        input_file = source_handler.get_file_str()
        commandline = [
                'ffmpeg'
        ]
        if config.allow_rewrite:
            commandline += ['-y']
        commandline += [
            '-loglevel', 'warning',
            '-i', input_file,
            '-pix_fmt', self._pixel_format,
            '-c:v', self._encoder,
            '-crf', str(quality),
            '-b:v', '0',
            '-profile:v', '0',
            '-cpu-used', '4',
            '-row-mt', '1',
            '-threads', str(config.encoding_threads),
            '-f', 'webm',
            '-'
        ]
        encoding_results = run_subprocess(commandline)
        source_handler.close()
        return encoding_results.stdout


class VP8Encoder(WEBMEncoder):
    def __init__(self, source):
        super().__init__("libvpx-vp8", "yuv420p", source)


class VP9Encoder(WEBMEncoder):
    def __init__(self, source):
        super().__init__("libvpx-vp9", "yuva420p", source)


class AV1Encoder(WEBMEncoder):
    def __init__(self, source):
        super().__init__("libaom-av1", "yuva420p10le", source)


