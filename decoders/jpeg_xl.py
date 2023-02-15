import tempfile
import subprocess
from PIL import Image


def is_JPEG_XL(file_path):
    file = open(file_path, 'rb')
    header = file.read(7)
    file.close()
    return header == b'\x00\x00\x00\x0cJXL' or header[:2] == b'\xff\x0a'


def decode(file):
    tmp_file = tempfile.NamedTemporaryFile(mode='rb', delete=True, suffix='.png')
    subprocess.run([
        "djxl",
        str(file),
        tmp_file.name
    ])
    return Image.open(tmp_file)
