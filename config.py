import enum


class PREFERRED_CODEC(enum.Enum):
    WEBP = enum.auto()
    AVIF = enum.auto()


preferred_codec = PREFERRED_CODEC.WEBP


# if 0 or None, AVIF's multithreading is off
# else, it's enables row-mt
avif_encoding_threads = 1
avifdec_workers_count = 1


class AVIF_DECODING_SPEEDS(enum.Enum):
    FAST = enum.auto()
    SLOW = enum.auto()


avif_decoding_speed = AVIF_DECODING_SPEEDS.FAST

# Max image size
# works if image optimisations is enabled
# if value is None, set maximum possible for webp size
MAX_SIZE = None

enable_multiprocessing = True

jpeg_xl_tools_path = None


class YUV4MPEG2_LIMITED_RANGE_CORRENTION_MODES(enum.Enum):
    NONE = enum.auto()
    CLIPPING = enum.auto()
    EXPAND = enum.auto()


yuv4mpeg2_limited_range_correction = YUV4MPEG2_LIMITED_RANGE_CORRENTION_MODES.CLIPPING
