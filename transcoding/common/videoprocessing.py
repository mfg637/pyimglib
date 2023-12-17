from ... import config
import tempfile


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
