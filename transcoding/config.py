import enum


class PREFERRED_CODEC(enum.Enum):
    WEBP = enum.auto()
    AVIF = enum.auto()


preferred_codec = PREFERRED_CODEC.WEBP


# if 0 or None, AVIF's multithreading is off
# else, it's enables row-mt
avif_encoding_threads = 1

# Max image size
# works if image optimisations is enabled
# if value is None, set maximum possible for webp size
MAX_SIZE = None

enable_multiprocessing = True

jpeg_xl_tools_path = None
