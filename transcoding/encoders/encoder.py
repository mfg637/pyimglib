import abc
import pathlib


class AbstractEncoder(abc.ABC):
    pass


class BytesEncoder(AbstractEncoder):
    def __init__(self, file_suffix):
        self.file_suffix = file_suffix

    @abc.abstractmethod
    def encode(self, quality) -> bytes:
        pass

    def save(self, encoded_data: bytes, path: pathlib.Path, name: str) -> pathlib.Path:
        output_fname = path.joinpath(name + self.file_suffix)
        outfile = open(output_fname, 'wb')
        outfile.write(encoded_data)
        outfile.close()
        return output_fname


class FilesEncoder(AbstractEncoder):
    @abc.abstractmethod
    def encode(self, input_file: pathlib.Path, output_file: pathlib.Path) -> pathlib.Path:
        pass

    @abc.abstractmethod
    def get_files(self) -> list[pathlib.Path]:
        pass

    def calc_file_size(self) -> int:
        files = self.get_files()
        size = 0
        for file in files:
            size += file.stat().st_size
        return size

    def delete_result(self):
        files = self.get_files()
        for file in files:
            file.unlink()
