import abc
import pathlib


class Encoder(abc.ABC):
    @abc.abstractmethod
    def encode(self, quality) -> bytes:
        pass

    def save(self, encoded_data: bytes, path: pathlib.Path, name: str):
        pass
