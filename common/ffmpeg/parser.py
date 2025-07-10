import enum
import json

from ..utils import (
    run_subprocess,
    InputSourceFacade,
    SourceType,
    check_is_fractions,
    to_fractions_or_float
)


def fps_calc(raw_str):
    _f = raw_str.split("/")
    _f = (int(_f[0]), int(_f[1]))
    if len(_f) != 2 and len(_f) > 0:
        return int(_f[0])
    elif check_is_fractions(_f):
        return to_fractions_or_float(_f)
    else:
        raise ValueError(raw_str)


def get_fps(video_stream):
    fps = None
    if video_stream['avg_frame_rate'] == "0/0":
        fps = fps_calc(video_stream['r_frame_rate'])
    else:
        fps = fps_calc(video_stream['avg_frame_rate'])
    return fps


def get_duration(data):
    return float(data["format"]["duration"])


class SPECIFY_VIDEO_STREAM(enum.Enum):
    FIRST = enum.auto()
    LAST = enum.auto()


def find_video_stream(data, first_or_last=SPECIFY_VIDEO_STREAM.FIRST):
    video = None
    for stream in data['streams']:
        if stream['codec_type'] == "video":
            video = stream
            if first_or_last == SPECIFY_VIDEO_STREAM.FIRST:
                break
    return video


def find_audio_streams(data):
    streams = list()
    for stream in data['streams']:
        if stream['codec_type'] == "audio":
            streams.append(stream)
    return streams


def get_file_bitrate(data):
    return int(data["format"]["bit_rate"])


def get_video_codec(video_stream) -> str:
    return video_stream["codec_name"]


def get_video_pixel_format(video_stream) -> str:
    return video_stream["pix_fmt"]


def check_variate_frame_rate_and_estimate_durarion(
        source: SourceType
) -> tuple[float, bool]:
    with InputSourceFacade(source) as source_handler:
        file_path = source_handler.get_file_str()
        commandline = [
            "ffprobe",
            "-show_entries", "frame=duration_time",
            "-print_format", "json",
            file_path
        ]
        result = run_subprocess(commandline)
    raw_data = result.stdout.decode()
    json_data = json.loads(raw_data)
    first_value = None
    duration_sum = 0.0
    vfr = False
    for frame in json_data["frames"]:
        duration_time_raw = frame["duration_time"]
        if first_value is None:
            first_value = duration_time_raw
        else:
            if duration_time_raw != first_value:
                vfr = True
        duration_time = float(duration_time_raw)
        duration_sum += duration_time
    return duration_sum, vfr


def test_videoloop(src_metadata) -> bool:
    audio_streams = find_audio_streams(src_metadata)
    if len(audio_streams) > 0:
        return False
    else:
        duration = get_duration(src_metadata)
        if duration <= 30.0:
            return True
        else:
            return False


def test_video_cl3(src_metadata) -> bool:
    video = find_video_stream(src_metadata)
    fps = get_fps(video)
    if video["width"] > video["height"]:
        min_size = video["height"]
        max_size = video["width"]
    else:
        min_size = video["width"]
        max_size = video["height"]
    if video["codec_name"] in ("vp9", "vp8"):
        if min_size <= 720 and max_size <= 1280 and fps <= 60:
            return True
        elif min_size <= 1080 and max_size <= 1920 and fps <= 30:
            return True
    elif video["codec_name"] == "h264":
        return min_size <= 1080 and max_size <= 1920 and fps <= 60
    return False


def get_size(src_metadata) -> tuple[int, int]:
    video = find_video_stream(src_metadata)
    return video["width"], video["height"]


def fps(src_metadata):
    video = find_video_stream(src_metadata)
    return get_fps(video)
