import abc
import os
import io
from . import webm_transcoder, base_transcoder, webp_anim_converter
from PIL import Image


class GIFTranscode(webm_transcoder.WEBM_VideoOutputFormat):
    __metaclass__ = abc.ABCMeta

    def _encode(self):
        img = self._open_image()
        self._animated = img.is_animated
        if not self._animated:
            raise base_transcoder.NotOptimizableSourceException()
        self._quality = 85
        webm_transcoder.animation2webm(self._source, self._output_file + '.webm')
        self._output_size = os.path.getsize(self._output_file + '.webm')

    def _save(self):
        pass

    @abc.abstractmethod
    def _all_optimisations_failed(self):
        pass

    def get_converter_type(self):
        return webp_anim_converter.GIFconverter

    def _optimisations_failed(self):
        self.gif_optimisations_failed()


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


class GIFInMemoryTranscode(base_transcoder.InMemorySource, GIFTranscode):

    def __init__(self, source:bytearray, path:str, file_name:str, item_data:dict, pipe):
        base_transcoder.InMemorySource.__init__(self, source, path, file_name, item_data, pipe)
        in_io = io.BytesIO(self._source)
        img = Image.open(in_io)
        self._animated = img.is_animated
        img.close()
        self._quality = 85

    def _all_optimisations_failed(self):
        outfile = open(self._output_file + ".gif", "bw")
        outfile.write(self._source)
        outfile.close()
        print("save " + self._output_file + ".gif")
