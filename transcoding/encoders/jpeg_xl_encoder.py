import pathlib
import subprocess
import tempfile

import PIL.Image

from . import encoder
from ... import common
from ... import config


class JpegXlEncoder(encoder.BytesEncoder):
    SUFFIX = ".jxl"
    def __init__(self, source, img: PIL.Image.Image):
        encoder.BytesEncoder.__init__(self, ".jxl")
        self.source = source
        self.img = img

    def encode(self, quality) -> bytes:
        src_tmp_file = None
        if isinstance(self.source, (pathlib.Path, str)):
            src_tmp_file_name = self.source
        else:
            src_tmp_file = tempfile.NamedTemporaryFile(mode='wb', suffix=".png", delete=True)
            src_tmp_file_name = src_tmp_file.name
            self.img.save(src_tmp_file, format="PNG")
        output_tmp_file = tempfile.NamedTemporaryFile(mode='rb', suffix=".jxl", delete=True)
        commandline = [
            "cjxl",
            src_tmp_file_name,
            output_tmp_file.name,
            "-q", str(quality)
        ]
        common.run_subprocess(commandline, log_stdout=True)
        if src_tmp_file is not None:
            src_tmp_file.close()
        encoded_data = output_tmp_file.read()
        output_tmp_file.close()
        return encoded_data


class JpegXlLosslessEncoder(JpegXlEncoder):
    SUFFIX = ".jxl"
    def encode(self, quality) -> bytes:
        return JpegXlEncoder.encode(self, 100)

