from . import ffmpeg_frames_stream
from .common import open_image
import pathlib
import PIL.Image
from .. import ACLMMP

SRS_FILE_HEADER = "{\"ftype\":\"CLSRS\""


class ClImage:
    def __init__(self, dir: pathlib.Path, content, img_metadata, levels):
        self._dir = dir
        self._content = content
        self._img_metadata = img_metadata
        self._levels = levels
        self._levels_sorted = list(self._levels.keys())
        self._levels_sorted.sort(reverse=True)

    def load_thumbnail(self, required_size=None):
        min_level = self._levels_sorted[0]
        return open_image(self._dir.joinpath(self._levels[min_level]), required_size)

    def progressive_lods(self):
        lods = list()
        for level in self._levels_sorted:
            lods.append(self._levels[level])
        return lods

    def get_image_file_list(self):
        files = list()
        for level in self._levels:
            files.append(self._levels[level])
        return files



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
    if type(file_path) is str:
        file_path = pathlib.Path(file_path)
    dir = file_path.parent
    fp = open(file_path, "r")
    content_metadata, streams_metadata, minimal_content_compatibility_level = ACLMMP.srs_parser.parseJSON(fp)
    fp.close()

    if content_metadata["media-type"] == ACLMMP.srs_parser.MEDIA_TYPE.IMAGE.value:
        return ClImage(dir, content_metadata, streams_metadata[3].tags, streams_metadata[3].levels)
    elif content_metadata["media-type"] == ACLMMP.srs_parser.MEDIA_TYPE.VIDEO.value:
        if 'poster-image' in content_metadata:
            return PIL.Image.open(dir.joinpath(content_metadata['poster-image']))
        elif 'cover-image' in content_metadata:
            return PIL.Image.open(dir.joinpath(content_metadata['cover-image']))
        else:
            video = streams_metadata[0].get_compatible_files(0)[0]
            return ffmpeg_frames_stream.FFmpegFramesStream(dir.joinpath(video), original_filename=file_path)

def get_file_paths(file_path):
    if type(file_path) is str:
        file_path = pathlib.Path(file_path)
    dir = file_path.parent
    fp = open(file_path, "r")
    content_metadata, streams_metadata, minimal_content_compatibility_level = ACLMMP.srs_parser.parseJSON(fp)
    fp.close()

    if content_metadata["media-type"] == ACLMMP.srs_parser.MEDIA_TYPE.IMAGE.value:
        return ClImage(dir, content_metadata, streams_metadata[3].tags, streams_metadata[3].levels).get_image_file_list()
    elif content_metadata["media-type"] == ACLMMP.srs_parser.MEDIA_TYPE.VIDEO.value:
        file_list = list()
        if 'poster-image' in content_metadata:
            file_list.append(dir.joinpath(content_metadata['poster-image']))
        elif 'cover-image' in content_metadata:
            file_list.append(dir.joinpath(content_metadata['cover-image']))
        video = streams_metadata[0].levels
        for level in video:
            file_list.append(video[level])
        return file_list