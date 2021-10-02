import tempfile
import subprocess
from . import YUV4MPEG2
from .. import config
import PIL.Image


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
    if config.avif_decoding_speed == config.AVIF_DECODING_SPEEDS.FAST:
        tmp_file = tempfile.NamedTemporaryFile(mode='rb', delete=True, suffix='.y4m')
        subprocess.call(['avifdec', '-j', str(config.avifdec_workers_count), str(file), tmp_file.name])
        return YUV4MPEG2.Y4M_FramesStream(tmp_file.name)
    elif config.avif_decoding_speed == config.AVIF_DECODING_SPEEDS.SLOW:
        tmp_file = tempfile.NamedTemporaryFile(mode='rb', delete=True, suffix='.png')
        subprocess.call(['avifdec', '-j', str(config.avifdec_workers_count), str(file), tmp_file.name])
        return PIL.Image.open(tmp_file.name)