import tempfile
import subprocess
import pathlib
from PIL import Image

PATH_TO_REFERENCE_DECODER = None


def is_JPEG_XL(file_path):
    file = open(file_path, 'rb')
    header = file.read(7)
    file.close()
    return header == b'\x00\x00\x00\x0cJXL'


def decode(file):
    if PATH_TO_REFERENCE_DECODER is None:
        raise NotADirectoryError("No path to reference JPEG XL decoder")
    if not is_JPEG_XL(file):
        raise Exception
    tmp_file = tempfile.NamedTemporaryFile(mode='rb', delete=True, suffix='.ppm')
    subprocess.call([
        pathlib.Path(PATH_TO_REFERENCE_DECODER).joinpath("djxl"),
        str(file),
        tmp_file.name
    ])
    return Image.open(tmp_file)
