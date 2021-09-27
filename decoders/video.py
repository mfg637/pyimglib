from . import ffmpeg_frames_stream


def mp4_header_check(prefix):
    return prefix[4:12] == b"ftypisom" or prefix[4:12] == b"ftypmp42"


def mkv_header_check(prefix):
    return prefix[:4] == b"\x1a\x45\xdf\xa3"


def is_video(file_path):
    file = open(file_path, 'rb')
    header = file.read(16)
    file.close()
    return mkv_header_check(header) or mp4_header_check(header)


def open_video(file_path):
    if is_video(file_path):
        return ffmpeg_frames_stream.FFmpegFramesStream(file_path)
    else:
        raise NotImplementedError()
