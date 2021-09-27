import abc
import os
import io
from . import statistics, config
from PIL import Image


class AlreadyOptimizedSourceException(Exception):
    pass


class NotOptimizableSourceException(Exception):
    pass


class BaseTranscoder:
    __metaclass__ = abc.ABCMeta

    def __init__(self, source, path:str, file_name:str, item_data:dict, pipe):
        self._source = source
        self._path = path
        self._file_name = file_name
        self._item_data = item_data
        self._pipe = pipe
        self._size = 0
        self._output_file = os.path.join(path, file_name)
        self._output_size = 0
        self._quality = 95
        self._fext = 'webp'
        self._webp_output = False

    @abc.abstractmethod
    def _encode(self):
        pass

    @abc.abstractmethod
    def _save(self):
        pass

    def _record_timestamps(self):
        pass

    @abc.abstractmethod
    def _remove_source(self):
        pass

    @abc.abstractmethod
    def _optimisations_failed(self):
        pass

    @abc.abstractmethod
    def _open_image(self) -> Image.Image:
        pass

    @abc.abstractmethod
    def _get_source_size(self) -> int:
        pass

    @abc.abstractmethod
    def _set_utime(self) -> None:
        pass

    def transcode(self):
        global sumsize
        global sumos
        global avq
        global items
        self._size = self._get_source_size()
        try:
            self._encode()
        except (
            AlreadyOptimizedSourceException,
            NotOptimizableSourceException
        ):
            statistics.pipe_send(self._pipe)
            return
        self._record_timestamps()
        if (self._size > self._output_size) and (self._output_size > 0):
            self._save()
            self._set_utime()
            print(('save {} kbyte ({}%) quality = {}').format(
                round((self._size - self._output_size) / 1024, 2),
                round((1 - self._output_size / self._size) * 100, 2),
                self._quality
            ))
            statistics.sumsize += self._size
            statistics.sumos += self._output_size
            statistics.avq += self._quality
            statistics.items += 1
            self._remove_source()
        else:
            self._optimisations_failed()
        if config.enable_multiprocessing:
            statistics.pipe_send(self._pipe)


class SourceRemovable(BaseTranscoder):
    __metaclass__ = abc.ABCMeta

    def _remove_source(self):
        os.remove(self._source)


class UnremovableSource(BaseTranscoder):
    __metaclass__ = abc.ABCMeta

    def _remove_source(self):
        pass


class FilePathSource(BaseTranscoder):
    __metaclass__ = abc.ABCMeta

    def __init__(self, source: str, path: str, file_name: str, item_data: dict, pipe):
        BaseTranscoder.__init__(self, source, path, file_name, item_data, pipe)
        self._tmp_src = None

    def _record_timestamps(self):
        self._atime = os.path.getatime(self._source)
        self._mtime = os.path.getmtime(self._source)

    def _open_image(self) -> Image.Image:
        return Image.open(self._source)

    def _get_source_size(self) -> int:
        return os.path.getsize(self._source)


class InMemorySource(UnremovableSource):
    __metaclass__ = abc.ABCMeta

    def __init__(self, source:bytearray, path:str, file_name:str, item_data:dict, pipe):
        BaseTranscoder.__init__(self, source, path, file_name, item_data, pipe)

    def _open_image(self) -> Image.Image:
        src_io = io.BytesIO(self._source)
        return Image.open(src_io)

    def _get_source_size(self) -> int:
        return len(self._source)

    def _set_utime(self) -> None:
        pass