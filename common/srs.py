import enum
import json
import pathlib


def write_srs(srs_data, tags, metadata, output_file):
    for key in tags:
        srs_data['content']['tags'][key] = list(tags[key])
    srs_data['content'].update(metadata)
    file_path = None
    if isinstance(output_file, pathlib.Path):
        file_path = output_file.with_suffix(".srs")
    else:
        file_path = output_file + '.srs'
    srs_file = open(file_path, 'w')
    json.dump(srs_data, srs_file)
    srs_file.close()
    return srs_file


class VideoCodecs(enum.IntEnum):
    H264 = 0
    AVC = H264
    VP8 = 1
    VP9 = 2
    AV1 = 3


class AudioCodecs(enum.IntEnum):
    AAC = 0
    Vorbis = 1
    Opus = 2


def codec_name_to_enum(codec_name: str) -> VideoCodecs | int:
    codec_map = {
        "h264": VideoCodecs.H264,
        "avc": VideoCodecs.AVC,
        "vp8": VideoCodecs.VP8,
        "vp9": VideoCodecs.VP9,
        "av1": VideoCodecs.AV1,
    }
    return codec_map.get(codec_name.lower(), 999)


VIDEO_60FPS_LEVELS: dict[int, tuple[VideoCodecs, int, int, int]] = {
    1: (VideoCodecs.AV1, 3840, 2160, 10),
    2: (VideoCodecs.VP9, 2560, 1440, 8),
    3: (VideoCodecs.H264, 1920, 1080, 8),
}

VIDEO_30FPS_LEVELS: dict[int, tuple[VideoCodecs, int, int, int]] = {
    1: (VideoCodecs.AV1, 7680, 4320, 10),
    2: (VideoCodecs.VP9, 3840, 2160, 8),
    3: (VideoCodecs.VP9, 1920, 1080, 8),
    4: (VideoCodecs.H264, 1920, 1080, 8),
}


PIXEL_FORMAT_TO_BITS_PER_CHANNEL = {
    "yuv420p": 8,
    "yuv420p10le": 10
}


BITS_PER_CHANNEL_TO_PIXEL_FORMAT = {
    8: "yuv420p",
    10: "yuv420p10le"
}


class VideoContainers(enum.Enum):
    MPEG_4 = enum.auto()
    WEBM = enum.auto()


class AudioContainers(enum.Enum):
    MPEG_4_AUDIO = enum.auto()
    OGG_AUDIO = enum.auto()
    OGG_OPUS = enum.auto()


MPEG_4_CONTAINER = (VideoContainers.MPEG_4, ".mp4")
WEBM_CONTAINER = (VideoContainers.WEBM, ".webm")

VIDEO_CODEC_PREFERED_CONTAINER: dict[
    VideoCodecs, tuple[VideoContainers, str]
] = {
    VideoCodecs.H264: MPEG_4_CONTAINER,
    VideoCodecs.VP8: WEBM_CONTAINER,
    VideoCodecs.VP9: WEBM_CONTAINER,
    VideoCodecs.AV1: MPEG_4_CONTAINER
}

AUDIO_CODEC_LEVEL = {
    AudioCodecs.AAC: 4,
    AudioCodecs.Vorbis: 3,
    AudioCodecs.Opus: 3
}

AUDIO_CODEC_PREFERED_CONTAINER: dict[
    AudioCodecs, tuple[AudioContainers, str]
] = {
    AudioCodecs.AAC: (AudioContainers.MPEG_4_AUDIO, ".m4a"),
    AudioCodecs.Vorbis: (AudioContainers.OGG_AUDIO, ".oga"),
    AudioCodecs.Opus: (AudioContainers.OGG_OPUS, ".opus")
}

FFMPEG_VIDEO_CONTAINER_FORMAT = {
    VideoContainers.MPEG_4: "mp4",
    VideoContainers.WEBM: "webm"
}
