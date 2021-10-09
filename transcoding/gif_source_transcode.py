import abc
import os
import io
from . import webm_transcoder, base_transcoder, webp_anim_converter, srs_video_loop
from PIL import Image


class GIFTranscode(webm_transcoder.WEBM_VideoOutputFormat):
    __metaclass__ = abc.ABCMeta

    def __init__(self, source, path: str, file_name: str, item_data: dict, pipe):
        webm_transcoder.WEBM_VideoOutputFormat.__init__(self, source, path, file_name, item_data, pipe)

    def _encode(self):
        img = self._open_image()
        self._animated = img.is_animated
        if not self._animated:
            raise base_transcoder.NotOptimizableSourceException()
        webm_transcoder.WEBM_VideoOutputFormat.animation_encode(self)

    def _save(self):
        pass

    @abc.abstractmethod
    def _all_optimisations_failed(self):
        pass

    def get_converter_type(self):
        return webp_anim_converter.GIFconverter

    def _optimisations_failed(self):
        self.gif_optimisations_failed()


class SRS_GIFTranscode(srs_video_loop.SrsVideoLoopOutput):
    __metaclass__ = abc.ABCMeta

    def __init__(self, source, path: str, file_name: str, item_data: dict, pipe, metadata):
        super().__init__(source, path, file_name, item_data, pipe, metadata)

    def _encode(self):
        img = self._open_image()
        self._animated = img.is_animated
        if not self._animated:
            raise base_transcoder.NotOptimizableSourceException()
        srs_video_loop.SrsVideoLoopOutput.animation_encode(self)

    @abc.abstractmethod
    def _all_optimisations_failed(self):
        pass

    def get_converter_type(self):
        return webp_anim_converter.GIFconverter

    def _optimisations_failed(self):
        srs_video_loop.SrsVideoLoopOutput._optimisations_failed(self)
        outfile = open(self._output_file + ".gif", "bw")
        outfile.write(self._source)
        outfile.close()
        print("save " + self._output_file + ".gif")
        srs_data = {
            "ftype": "CLSRS",
            "content": {
                "media-type": 0,
                "tags": dict()
            },
            "streams": {
                "image": {"levels": {"4": self._file_name + ".gif"}}
            }
        }
        self._srs_write_srs(srs_data)


class GIFFileTranscode(base_transcoder.FilePathSource, base_transcoder.SourceRemovable, GIFTranscode):

    def __init__(self, source: str, path: str, file_name: str, item_data: dict, pipe):
        base_transcoder.FilePathSource.__init__(self, source, path, file_name, item_data, pipe)
        img = Image.open(source)
        self._animated = img.is_animated
        img.close()

    def _set_utime(self) -> None:
        os.utime(self._output_file+'.webm', (self._atime, self._mtime))

    def _all_optimisations_failed(self):
        print("save " + self._source)
        os.remove(self._output_file)


class SRS_GIFFileTranscode(GIFFileTranscode, SRS_GIFTranscode):
    def __init__(self, source: str, path: str, file_name: str, item_data: dict, pipe, metadata):
        GIFFileTranscode.__init__(self, source, path, file_name, item_data, pipe)
        SRS_GIFTranscode.__init__(self, source, path, file_name, item_data, pipe, metadata)


class GIFInMemoryTranscode(base_transcoder.InMemorySource, GIFTranscode):

    def __init__(self, source:bytearray, path:str, file_name:str, item_data:dict, pipe):
        base_transcoder.InMemorySource.__init__(self, source, path, file_name, item_data, pipe)
        GIFTranscode.__init__(self, source, path, file_name, item_data, pipe)
        in_io = io.BytesIO(self._source)
        img = Image.open(in_io)
        self._animated = img.is_animated
        img.close()

    def _all_optimisations_failed(self):
        outfile = open(self._output_file + ".gif", "bw")
        outfile.write(self._source)
        outfile.close()
        print("save " + self._output_file + ".gif")


class SRS_GIFInMemoryTranscode(GIFInMemoryTranscode, SRS_GIFTranscode):
    def __init__(self, source: bytearray, path: str, file_name: str, item_data: dict, pipe, metadata):
        GIFInMemoryTranscode.__init__(self, source, path, file_name, item_data, pipe)
        SRS_GIFTranscode.__init__(self, source, path, file_name, item_data, pipe, metadata)

    def _encode(self):
        SRS_GIFTranscode._encode(self)

    def _save(self):
        SRS_GIFTranscode._save(self)

    def _optimisations_failed(self):
        SRS_GIFTranscode._optimisations_failed(self)
