import enum

custom_pillow_image_limits = -1


class PREFERRED_CODEC(enum.Enum):
    WEBP = enum.auto()
    AVIF = enum.auto()
    DASH_AVIF = enum.auto()


preferred_codec = PREFERRED_CODEC.WEBP


# if 0 or None, AVIF's multithreading is off
# or, it's enables row-mt
encoding_threads = 1
avifdec_workers_count = 1


class AVIF_DECODING_SPEED(enum.Enum):
    FAST = enum.auto()
    SLOW = enum.auto()


avif_decoding_speed = AVIF_DECODING_SPEED.FAST
avifenc_encoding_speed = 0

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

srs_webp_size_limit = 2048
srs_avif_trigger_size = 2560
srs_thumbnail_for_lossless_trigger_size = 4096

cl3_width = 1280
cl3_height = 720
gop_length_seconds = 10

# Ratio of CL3 transcoded video stream size to original video stream size.
# Lesser is smaller, but worse quality.
# Reasonable range: 0.5-1
cl3_to_orig_ratio = 0.5
VP9_VIDEO_CRF = 24
GIF_VIDEOLOOP_CRF = 32
APNG_VIDEOLOOP_CRF = VP9_VIDEO_CRF
VIDEOLOOP_CRF = GIF_VIDEOLOOP_CRF

avifenc_qdeviation = 5

allow_rewrite = False

WEBP_QSCALE = 1.375
SRS_QSCALE = 1.25

dash_low_tier_crf_gap = 4
