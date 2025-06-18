import enum
import pathlib
import json
import tempfile

from ..utils import run_subprocess


def fps_calc(raw_str):
    _f = raw_str.split("/")
    if len(_f) != 2 and len(_f) > 0:
        return int(_f[0])
    elif len(_f) == 2:
        return int(_f[0])/int(_f[1])
    else:
        raise ValueError(raw_str)


def get_fps(video_stream):
    fps = None
    if video_stream['avg_frame_rate'] == "0/0":
        fps = fps_calc(video_stream['r_frame_rate'])
    else:
        fps = fps_calc(video_stream['avg_frame_rate'])
    return fps


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
        source: pathlib.Path | bytearray
) -> tuple[float, bool]:
    print("start checking…")
    tmpfile = None
    if isinstance(source, pathlib.Path):
        file_path = source
    else:
        tmpfile = tempfile.NamedTemporaryFile(delete_on_close=True)
        file_path = tmpfile.name
        tmpfile.write(source)
    commandline = [
        "ffprobe",
        "-show_entries", "frame=duration_time",
        "-print_format", "json",
        str(file_path)
    ]
    result = run_subprocess(commandline)
    if tmpfile is not None:
        tmpfile.close()
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
    print("results is", duration_sum, vfr)
    return duration_sum, vfr
