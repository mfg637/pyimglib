import enum


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
