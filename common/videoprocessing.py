from .. import config
from .utils import bit_round
import logging
import tempfile
import enum

logger = logging.getLogger(__name__)


CL3_FFMPEG_SCALE_COMMANDLINE = [
    '-vf', 'scale=\'min({},iw)\':\'min({},ih)\':force_original_aspect_ratio=decrease'.format(
        config.cl3_width, config.cl3_height
    )
]


def ffmpeg_set_fps_commandline(fps):
    return ['-r', str(fps)]


def limit_fps(fps, limit_value=30):
    src_fps_valid = True
    if fps > limit_value:
        src_fps_valid = False
        while fps > limit_value:
            fps /= 2
    return fps, src_fps_valid


def cl3_size_valid(video):
    return video["width"] <= config.cl3_width and video["height"] <= config.cl3_height


def ffmpeg_get_passfile_prefix():
    passfilename = ""
    with tempfile.NamedTemporaryFile() as f:
        passfilename = f.name
    return passfilename


class ScaleStrategy(enum.Enum):
    FIT_IN = enum.auto()
    FIT_BY_SMALL = enum.auto()


def it_fits_in(value, limit):
    return value <= limit


def scale_down_to_fill(
        source_size: tuple[int, int], min_size: int, size_precision: int = -1
) -> tuple[int, int, float]:
    """
    Scales down a source size (width, height) so that the smallest dimension
    becomes at least `min_size`, preserving the aspect ratio and
    rounding the result to the specified precision.

    If the original smallest dimension is already less than or equal to
    `min_size`, the original size is returned (possibly rounded). Otherwise,
    the image is scaled down so that the smallest dimension equals `min_size`.

    Args:
        source_size (tuple[int, int]):
            The original (width, height) of the image.
        min_size (int):
            The minimum allowed size for the smallest dimension after scaling.
        size_precision (int, optional): The precision for rounding the scaled
            dimensions. If zero, no rounding is applied.
            If negative, n digits before comma is rounded
            (useful for some codecs).

    Returns:
        tuple[int, int, float]: The (width, height) of the scaled image,
            and scale coefficient (<= 1).
    """
    width_orig, height_orig = source_size
    width_scaled = 2
    height_scaled = 2
    scale_coef = 1

    if height_orig <= width_orig:
        logging.debug("width > height or width = height")
        if it_fits_in(height_orig, min_size):
            width_scaled = int(
                bit_round(width_orig, size_precision)
            )
            height_scaled = int(
                bit_round(height_orig, size_precision)
            )
        else:
            height_scaled = min_size
            scale_coef = height_orig / min_size
            width_scaled = int(
                bit_round(width_orig / scale_coef, size_precision)
            )
    # elif height_orig > width_orig
    else:
        logging.debug("height > width")
        if it_fits_in(width_orig, min_size):
            width_scaled = int(
                bit_round(width_orig, size_precision)
            )
            height_scaled = int(
                bit_round(height_orig, size_precision)
            )
        else:
            width_scaled = min_size
            scale_coef = width_orig / min_size
            height_scaled = int(bit_round(
                height_orig / scale_coef, size_precision
            ))
    return width_scaled, height_scaled, scale_coef


def scale_down_fit_in(
    source_size: tuple[int, int], max_size: int, size_precision: int = -1
) -> tuple[int, int, float]:
    """
    Scales down a source size (width, height) to fit within a maximum size,
    preserving aspect ratio.

    Args:
        source_size (tuple[int, int]):
            The original (width, height) of the source.
        max_size (int): The maximum allowed size for the largest dimension
            (width or height).
        size_precision (int, optional):
            The precision for rounding the scaled
            dimensions. If zero, no rounding is applied.
            If negative, n digits before comma is rounded
            (useful for some codecs).

    Returns:
        tuple[int, int, float]: A tuple containing:
            - width_scaled (int): The scaled width.
            - height_scaled (int): The scaled height.
            - scale_coef (float):
                The scaling coefficient used to resize the original dimensions.

    Notes:
        - The function preserves the aspect ratio of the source.
        - If the original size already fits within max_size,
            the original dimensions are returned (optionally rounded).
    """
    width_orig, height_orig = source_size
    width_scaled = 2
    height_scaled = 2
    scale_coef = 1

    if height_orig <= width_orig:
        logging.debug("width > height or width = height")
        if it_fits_in(width_orig, max_size):
            width_scaled = int(
                bit_round(width_orig, size_precision)
            )
            height_scaled = int(
                bit_round(height_orig, size_precision)
            )
        else:
            width_scaled = max_size
            scale_coef = width_orig / max_size
            height_scaled = int(
                bit_round(height_orig / scale_coef, size_precision)
            )
    # elif height_orig > width_orig
    else:
        logging.debug("height > width")
        if it_fits_in(height_orig, max_size):
            width_scaled = int(
                bit_round(width_orig, size_precision)
            )
            height_scaled = int(
                bit_round(height_orig, size_precision)
            )
        else:
            height_scaled = max_size
            scale_coef = height_orig / max_size
            width_scaled = int(bit_round(
                width_orig / scale_coef, size_precision
            ))
    return width_scaled, height_scaled, scale_coef


def check_size_fills_in(
    current_size: tuple[int, int], max_side_size: tuple[int, int]
) -> bool:
    """
    Checks if the given current size fits within
    the specified maximum side size.

    Args:
        current_size (tuple[int, int]):
            The current size as a (width, height) tuple.
        max_side_size (tuple[int, int]):
            The maximum allowed size as a (width, height) tuple.

    Returns:
        bool: True if both width and height of current_size are
            less than or equal to those of max_side_size, False otherwise.
    """
    return (current_size[0] <= max_side_size[0] and
            current_size[1] <= max_side_size[1])


def scale_down(
    source_size: tuple[int, int],
    size_limit: tuple[int, int],
    size_precision: int = -1
) -> tuple[int, int]:
    """
    Scales down the given source size to fit
    within specified minimum and maximum size limits.

    The function first attempts to scale the source size
    so that it fills the minimum size limit.
    If the resulting size also fits within the maximum size limit,
    it is returned.
    Otherwise, the function scales the source size
    to fit within the maximum size limit.

    Args:
        source_size (tuple[int, int]):
            The original (width, height) of the source.
        size_limit (tuple[int, int]):
            A tuple (min_size, max_size)
            specifying the minimum and maximum size limits.
        size_precision (int, optional):
            The precision for rounding the scaled
            dimensions. If zero, no rounding is applied.
            If negative, n digits before comma is rounded
            (useful for some codecs).

    Returns:
        tuple[int, int]:
            The scaled (width, height) that fits
            within the specified size limits.
    """
    width_orig, height_orig = source_size
    min_size, max_size = size_limit

    filled_in_size = scale_down_to_fill(source_size, min_size, size_precision)
    fills_in = False

    if height_orig <= width_orig:
        fills_in = check_size_fills_in(
            (filled_in_size[0], filled_in_size[1]), (max_size, min_size)
        )
    else:
        fills_in = check_size_fills_in(
            (filled_in_size[0], filled_in_size[1]), (min_size, max_size)
        )

    if fills_in:
        return filled_in_size
    else:
        return scale_down_fit_in(source_size, max_size, size_precision)
