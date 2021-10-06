from ... import config


CL3_FFMPEG_SCALE_COMMANDLINE = [
    '-vf', 'scale=\'min({},iw)\':\'min({},ih)\':force_original_aspect_ratio=decrease'.format(
        config.cl3_width, config.cl3_height
    )
]


def ffmpeg_set_fps_commandline(fps):
    return ['-r', str(fps)]


def limit_fps(fps):
    src_fps_valid = True
    if fps > 30:
        src_fps_valid = False
        while fps > 30:
            fps /= 2
    return fps, src_fps_valid


def cl3_size_valid(video):
    return video["width"] <= config.cl3_width and video["height"] <= config.cl3_height
