import abc


class Encoder(abc.ABC):
    @abc.abstractmethod
    def encode(self, quality) -> memoryview:
        pass