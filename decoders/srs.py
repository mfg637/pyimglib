from . import ACLMMP, ffmpeg_frames_stream
import pathlib
import PIL.Image

SRS_FILE_HEADER = "{\"ftype\":\"CLSRS\""

def is_ACLMMP_SRS(file_path):
    file = open(file_path, 'r')
    try:
        header = file.read(16)
    except UnicodeDecodeError:
        file.close()
        return False
    file.close()
    return header == SRS_FILE_HEADER

def decode(file_path: pathlib.Path):
    dir = file_path.parent
    fp = open(file_path, "r")
    content_metadata, streams_metadata, minimal_content_compatibility_level = ACLMMP.srs_parser.parseJSON(fp)
    fp.close()
    print(content_metadata)

    if 'poster-image' in content_metadata:
        return PIL.Image.open(dir.joinpath(content_metadata['poster-image']))
    elif 'cover-image' in content_metadata:
        return PIL.Image.open(dir.joinpath(content_metadata['cover-image']))
    else:
        video = streams_metadata[0].get_compatible_files(0)[0]
        return ffmpeg_frames_stream.FFmpegFramesStream(dir.joinpath(video), original_filename=file_path)