import io
import pathlib
import subprocess

import PIL.Image

from . import encoder
import tempfile
from ..common import run_subprocess

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


class JpegXlTranscoder(encoder.BytesEncoder):
    def __init__(self, source, img: PIL.Image.Image):
        super().__init__(file_suffix=".jxl")
        self._source = source
        self._img = img

    def encode(self, quality=None) -> bytes:
        input_file = None
        in_tmp_file = None
        if isinstance(self._source, pathlib.Path):
            input_file = self._source
        else:
            in_tmp_file = tempfile.NamedTemporaryFile(suffix=".jpg")
            in_tmp_file.write(self._source)
            input_file = in_tmp_file.name
        out_tmp_file = tempfile.NamedTemporaryFile(suffix=".jxl")
        commandline = ['cjxl', '--lossless_jpeg=1', input_file, out_tmp_file.name]
        run_subprocess(commandline, log_stdout=True)
        if in_tmp_file is not None:
            in_tmp_file.close()
        result = out_tmp_file.read()
        out_tmp_file.close()
        return result