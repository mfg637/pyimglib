import io
import pathlib
import subprocess

import PIL.Image

from . import encoder
import tempfile
from ...common import run_subprocess, utils

class ArithmeticJpeg(encoder.BytesEncoder):
    def __init__(self, source, img: PIL.Image.Image):
        super().__init__(file_suffix=".jpg")
        self._source = source
        self._img = img

    def encode(self, quality=None) -> bytes:
        meta_copy = 'all'
        commandline = ['jpegtran', '-copy', meta_copy, '-arithmetic']
        if isinstance(self._source, pathlib.Path):
            commandline += [self._source]
            process = subprocess.Popen(commandline,
                                       stdout=subprocess.PIPE)
        else:
            process = subprocess.Popen(commandline,
                                       stdin=subprocess.PIPE, stdout=subprocess.PIPE)
            if type(self._source) is io.BytesIO:
                process.stdin.write(self._source.getvalue())
            elif type(self._source) is bytes:
                process.stdin.write(self._source)
            else:
                raise ValueError("unexpected type {}".format(type(self._source)))
        process.stdin.close()
        result = process.stdout.read()
        process.stdout.close()
        process.terminate()
        return result


class JpegXlTranscoder(encoder.SingleFileEncoder):
    def __init__(self, source, img: PIL.Image.Image):
        super().__init__(file_suffix=".jxl")
        self._source = source
        self._img = img

    def encode(self, quality, output_file: pathlib.Path) -> pathlib.Path:
        source_handler = utils.InputSourceFacade(self._source, ".jpg")
        input_file = source_handler.get_file_str()
        output_file = output_file.with_suffix(self.file_suffix)
        commandline = [
            'cjxl', '--lossless_jpeg=1', input_file, str(output_file)
        ]
        run_subprocess(commandline, log_stdout=True)
        source_handler.close()
        return output_file
