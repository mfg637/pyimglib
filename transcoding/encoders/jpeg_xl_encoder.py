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
        source_handler = common.utils.InputSourceFacade(
            self.source, ".png", common.utils.pil_writer(self.img)
        )
        src_tmp_file_name = source_handler.get_file_str()
        output_tmp_file = tempfile.NamedTemporaryFile(
            mode='rb', suffix=".jxl", delete=True
        )
        commandline = [
            "cjxl",
            src_tmp_file_name,
            output_tmp_file.name,
            "-q", str(quality)
        ]
        common.run_subprocess(commandline, log_stdout=True)
        source_handler.close()
        encoded_data = output_tmp_file.read()
        output_tmp_file.close()
        return encoded_data


class JpegXlLosslessEncoder(JpegXlEncoder):
    SUFFIX = ".jxl"

    def encode(self, quality) -> bytes:
        return JpegXlEncoder.encode(self, 100)
