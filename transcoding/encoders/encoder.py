import abc
import pathlib


class Encoder(abc.ABC):
    @abc.abstractmethod
    def encode(self, quality) -> memoryview:
        pass

    def save(self, encoded_data: memoryview, path: pathlib.Path, name: str):
        pass
