import tempfile
import subprocess
from . import YUV4MPEG2

workers_count = 1


def is_avif(file):
    file = open(file, 'rb')
    file.seek(4)
    header = file.read(8)
    file.close()
    return header in (b'ftypavif', b'ftypavis')


def is_animated_avif(file):
    file = open(file, 'rb')
    file.seek(4)
    header = file.read(8)
    file.close()
    return header == b'ftypavis'


def decode(file):
    if not is_avif(file):
        raise Exception
    tmp_file = tempfile.NamedTemporaryFile(mode='rb', delete=True, suffix='.y4m')
    subprocess.call(['avifdec', '-j', str(workers_count), str(file), tmp_file.name])
    return YUV4MPEG2.Y4M_FramesStream(tmp_file.name)