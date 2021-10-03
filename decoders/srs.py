import config
from . import ffmpeg_frames_stream
from .common import open_image
import pathlib
import PIL.Image
from .. import ACLMMP

SRS_FILE_HEADER = "CLSRS"


class ClImage:
    def __init__(self, dir: pathlib.Path, content, img_metadata, levels):
        self._dir = dir
        self.content = content
        self.img_metadata = img_metadata
        self._levels = levels
        self._levels_sorted = list(self._levels.keys())
        self._levels_sorted.sort(reverse=True)

    def load_thumbnail(self, required_size=None):
        min_level = self._levels_sorted[0]
        return open_image(self._dir.joinpath(self._levels[min_level]), required_size)

    def progressive_lods(self):
        lods = list()
        for level in self._levels_sorted:
            lods.append(self._dir.joinpath(self._levels[level]))
        return lods

    def get_image_file_list(self):
        files = list()
        for level in self._levels:
            files.append(self._dir.joinpath(self._levels[level]))
        return files



def is_ACLMMP_SRS(file_path):
    file = open(file_path, 'r')
    try:
        header = file.read(16)
    except UnicodeDecodeError:
        file.close()
        return False
    file.close()
    return SRS_FILE_HEADER in header

def cover_image_parser(dir, content_metadata, stream_metadata, original_filename):
    content_metadata['original_filename'] = original_filename
    tags = dict()
    levels = None
    for tag in stream_metadata:
        if tag == "levels":
            levels = stream_metadata['levels']
        else:
            tags['tag'] = stream_metadata[tag]
    return ClImage(dir, content_metadata, tags, levels)

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
        video = streams_metadata[0].get_compatible_files(config.ACLMMP_COMPATIBILITY_LEVEL)[0]
        if 'poster-image' in content_metadata:
            return cover_image_parser(dir, content_metadata, content_metadata['poster-image'], file_path)
        elif 'cover-image' in content_metadata:
            return cover_image_parser(dir, content_metadata, content_metadata['cover-image'], file_path)
        else:
            return ffmpeg_frames_stream.FFmpegFramesStream(dir.joinpath(video), original_filename=file_path)

def get_file_paths(file_path):
    if type(file_path) is str:
        file_path = pathlib.Path(file_path)
    dir = file_path.parent
    fp = open(file_path, "r")
    content_metadata, streams_metadata, minimal_content_compatibility_level = ACLMMP.srs_parser.parseJSON(fp)
    fp.close()

    if content_metadata["media-type"] == ACLMMP.srs_parser.MEDIA_TYPE.IMAGE.value:
        return ClImage(
            dir, content_metadata, streams_metadata[3].tags, streams_metadata[3].levels
        ).get_image_file_list()
    elif content_metadata["media-type"] == ACLMMP.srs_parser.MEDIA_TYPE.VIDEO.value:
        file_list = list()
        file_list_raw = list()
        if 'poster-image' in content_metadata:
            file_list_raw.extend(
                cover_image_parser(
                    dir, content_metadata, content_metadata['poster-image'], file_path
                ).get_image_file_list()
            )
        elif 'cover-image' in content_metadata:
            file_list_raw.extend(
                cover_image_parser(
                    dir, content_metadata, content_metadata['cover-image'], file_path
                ).get_image_file_list()
            )
        for f in file_list_raw:
            file_list.append(dir.joinpath(f))
        video = streams_metadata[0].levels
        for level in video:
            file_list.append(dir.joinpath(video[level]))
        return file_list

def type_detect(file_path):
    if type(file_path) is str:
        file_path = pathlib.Path(file_path)
    dir = file_path.parent
    fp = open(file_path, "r")
    content_metadata, streams_metadata, minimal_content_compatibility_level = ACLMMP.srs_parser.parseJSON(fp)
    fp.close()

    return ACLMMP.srs_parser.MEDIA_TYPE(content_metadata["media-type"])
