from . import ffmpeg_frames_stream


def mp4_header_check(prefix):
    return prefix[4:12] == b"ftypisom" or prefix[4:12] == b"ftypmp42"


MKV_HEADER = b"\x1a\x45\xdf\xa3"


def mkv_header_check(prefix):
    return prefix[:4] == MKV_HEADER


def mpd_check(file_path):
    file = open(file_path, 'r')
    try:
        line = file.readline()
        if "<?xml" in line:
            if "<MPD" in line:
                file.close()
                return True
            line = file.readline()
            if "<MPD" in line:
                file.close()
                return True
    except UnicodeDecodeError:
        pass
    file.close()
    return False


def is_regular_video(file_path):
    file = open(file_path, 'rb')
    header = file.read(16)
    file.close()
    return mkv_header_check(header) or mp4_header_check(header)


def is_video(file_path):
    regular = is_regular_video(file_path)
    return regular or mpd_check(file_path)


def is_webm(file_path):
    file = open(file_path, 'rb')
    header = file.read(16)
    file.close()
    return mkv_header_check(header)


def open_video(file_path):
    if is_regular_video(file_path):
        return ffmpeg_frames_stream.FFmpegFramesStream(file_path)
    elif mpd_check(file_path):
        stream = ffmpeg_frames_stream.FFmpegFramesStream(file_path)
        return stream
    else:
        raise NotImplementedError()
