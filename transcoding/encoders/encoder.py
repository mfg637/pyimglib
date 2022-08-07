import abc
import pathlib


class Encoder(abc.ABC):
    @abc.abstractmethod
    def encode(self, quality) -> bytes:
        pass

    @abc.abstractmethod
    def save(self, encoded_data: bytes, path: pathlib.Path, name: str) -> pathlib.Path:
        pass


class VideoEncoder(abc.ABC):
    @abc.abstractmethod
    def encode(self, input_file: pathlib.Path, output_file: pathlib.Path) -> pathlib.Path:
        pass
