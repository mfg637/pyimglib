import abc
import pathlib
import typing
import PIL.Image


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

    @abc.abstractmethod
    def set_manifest_file(self, manifest_file: pathlib.Path):
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
            file.unlink(missing_ok=True)


class BytesEncoderWrapper(FilesEncoder):
    def __init__(self, bytes_encoder_type: typing.Type[BytesEncoder], base_quality_level, source_data_size, ratio):
        self.encoder_type: typing.Type[BytesEncoder] = bytes_encoder_type
        self.quality = base_quality_level
        self.output_file_path: pathlib.Path | None = None
        self.encoded_data: bytes | None = None

    def encode(self, input_file: pathlib.Path, output_file: pathlib.Path) -> pathlib.Path:
        img = PIL.Image.open(input_file)
        encoder = self.encoder_type(input_file, img)
        self.encoded_data = encoder.encode(self.quality)
        self.output_file_path = output_file.with_suffix(encoder.SUFFIX)
        with self.output_file_path.open("bw") as f:
            f.write(self.encoded_data)
        return self.output_file_path

    def get_files(self) -> list[pathlib.Path]:
        return [self.output_file_path]

    def set_manifest_file(self, manifest_file: pathlib.Path):
        self.output_file_path = manifest_file