import tempfile
import subprocess
import pathlib
from PIL import Image
from .. import config


def is_JPEG_XL(file_path):
    file = open(file_path, 'rb')
    header = file.read(7)
    file.close()
    return header == b'\x00\x00\x00\x0cJXL'


def decode(file):
    TOOL_NAME = "djxl"
    if config.jpeg_xl_tools_path is not None:
        TOOL_NAME = pathlib.Path(config.jpeg_xl_tools_path).joinpath("djxl")
    if not is_JPEG_XL(file):
        raise Exception
    tmp_file = tempfile.NamedTemporaryFile(mode='rb', delete=True, suffix='.ppm')
    subprocess.call([
        TOOL_NAME,
        str(file),
        tmp_file.name
    ])
    return Image.open(tmp_file)
