from . import videoprocessing, srs, ffmpeg
from .utils import run_subprocess


def bit_round(number, precision: int = 0):
    scale = 1

    if precision > 0:
        scale = 2 ** precision
        number *= scale
    elif precision < 0:
        scale = 2 ** (precision * -1)
        number /= scale

    number = round(number)

    if precision > 0:
        number /= scale
    elif precision < 0:
        number *= scale

    return number



