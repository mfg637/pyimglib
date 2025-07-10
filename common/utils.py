from collections.abc import Iterable
from fractions import Fraction
import numbers
import pathlib
import subprocess
import logging
import tempfile
from typing import Union
import PIL.Image


logger = logging.getLogger(__name__)


def run_subprocess(commandline: list[str], log_stdout=False, capture_out=True):
    logger.debug("starting process")
    result = subprocess.run(commandline, capture_output=capture_out)
    logger.debug("process executed and done")
    if capture_out:
        stderr_message = result.stderr.decode("utf-8").splitlines()
        for line in stderr_message:
            logger.debug("stderr: {}".format(line))
        if log_stdout:
            stdout_message = result.stdout.decode("utf-8").splitlines()
            for line in stdout_message:
                logger.debug("stdout: {}".format(line))
    logger.debug("all logging is done")
    return result


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


SourceType = Union[str, pathlib.Path, bytes, bytearray]


class InputSourceFacade:
    def __init__(self, source: SourceType, suffix=None, writer=None):
        self._source = source
        self._tmpfile = None
        self.suffix = suffix
        self.writer = writer

    def get_file_path(self) -> pathlib.Path:
        file_path = pathlib.Path()
        if type(self._source) is str:
            file_path = pathlib.Path(self._source)
        elif isinstance(self._source, pathlib.Path):
            file_path = self._source
        else:
            self._tmpfile = tempfile.NamedTemporaryFile(
                delete=True, suffix=self.suffix
            )
            file_path = pathlib.Path(self._tmpfile.name)
            if self.writer is None:
                self._tmpfile.write(self._source)
            else:
                self.writer(self._tmpfile)
        return file_path

    def get_file_str(self) -> str:
        file_path = ""
        if type(self._source) is str:
            file_path = self._source
        elif isinstance(self._source, pathlib.Path):
            file_path = str(self._source)
        else:
            self._tmpfile = tempfile.NamedTemporaryFile(
                delete=True, suffix=self.suffix
            )
            file_path = self._tmpfile.name
            if self.writer is None:
                self._tmpfile.write(self._source)
            else:
                self.writer(self._tmpfile)
        return file_path

    def close(self):
        if self._tmpfile is not None:
            self._tmpfile.close()
            self._tmpfile = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            return False
        self.close()
        return True


def pil_writer(img: PIL.Image.Image, format="PNG"):
    def writer(fobj):
        img.save(fobj, format=format)
    return writer


def check_is_fractions(value):
    return isinstance(value, Fraction) or (
        isinstance(value, Iterable) and
        len(value) == 2 and
        isinstance(value[0], numbers.Rational) and
        isinstance(value[1], numbers.Rational)
    )


def fractions_to_float(fraction: Fraction | tuple[int, int]) -> float:
    if isinstance(fraction, Fraction):
        return fraction.numerator / fraction.denominator
    elif isinstance(fraction, Iterable):
        return fraction[0]/fraction[1]
    else:
        return float(fraction)


def to_fractions_or_float(value):
    if check_is_fractions(value):
        if isinstance(value, Fraction):
            return value
        return Fraction(*value)
    elif isinstance(value, (int, float)):
        return value
    else:
        return float(value)


def to_float(value):
    if check_is_fractions(value):
        return fractions_to_float(value)
    elif isinstance(value, (int, float)):
        return value
    else:
        return float(value)


def format_number(value):
    value = to_fractions_or_float(value)
    if isinstance(value, Fraction):
        return str(value)
    else:
        return f"{value:.3f}"
