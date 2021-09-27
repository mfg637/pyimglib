import abc
import PIL.Image


class FramesStream(abc.ABC):
    def __init__(self, file_path):
        self._frame_time_ms = 0
        self._width = 0
        self._height = 0
        self._color_profile = None
        self._duration = None
        self._file_path = file_path
        self._is_animated = True

    def get_duration(self):
        return self._duration

    def get_frame_time_ms(self):
        return self._frame_time_ms

    @property
    def filename(self):
        return self._file_path

    @property
    def is_animated(self):
        return self._is_animated

    @property
    def format(self):
        return "VIDEO"

    @abc.abstractmethod
    def next_frame(self) -> PIL.Image.Image:
        pass

    @abc.abstractmethod
    def close(self):
        pass
