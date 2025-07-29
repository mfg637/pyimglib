import pathlib
import png
import abc
import zlib
from . import exif_reader, iptc_reader


class EmptyContentError(ValueError):
    pass


class EXIF_Data(Exception):
    pass


EXIF_KEYWORD = "Raw profile type exif"
IPTC_KEYWORD = "Raw profile type iptc"


class AbstractTextReading(abc.ABC):
    def __init__(self, charset):
        self.charset = charset

    @abc.abstractmethod
    def read(self, chunk_content) -> tuple[str, str]:
        pass


class BaseTextReading(AbstractTextReading):
    @abc.abstractmethod
    def decode_content(self, raw_data) -> str:
        pass

    @abc.abstractmethod
    def decode_iptc(self, raw_data) -> dict[str, str]:
        pass

    def read(self, chunk_content) -> tuple[str, str] | dict[str, str]:
        raw_keyword, raw_data = bytes(chunk_content).split(b"\x00", maxsplit=1)
        if not raw_data:
            raise EmptyContentError("Empty content")
        keyword = raw_keyword.decode("latin-1")
        if keyword == EXIF_KEYWORD:
            raise EXIF_Data()
        elif keyword == IPTC_KEYWORD:
            return self.decode_iptc(raw_data)
        text_content = self.decode_content(raw_data)
        return keyword, text_content


class tEXt_Reading(BaseTextReading):
    def __init__(self):
        super().__init__("latin-1")

    def decode_content(self, raw_data):
        return raw_data.decode(self.charset)

    def decode_iptc(self, raw_data) -> dict[str, str]:
        return iptc_reader.read_png_chunk(raw_data)


def decode_ztxt(compression_method, compressed_text_data):
    if compression_method == 0:
        try:
            decompressed_text = zlib.decompress(compressed_text_data)
            return decompressed_text
        except zlib.error as e:
            raise ValueError(f"Failed to decompress zTXt data: {e}")
    else:
        raise ValueError(
            "Unsupported compression method for zTXt chunk: "
            + str(compression_method)
        )


class zTXt_Reading(BaseTextReading):
    def __init__(self):
        super().__init__("latin-1")

    def decode_content(self, raw_data):
        compression_method = raw_data[0]
        compressed_text_data = raw_data[1:]
        return decode_ztxt(compression_method, compressed_text_data).decode(
            self.charset
        )

    def decode_iptc(self, raw_data) -> dict[str, str]:
        compression_method = raw_data[0]
        compressed_text_data = raw_data[1:]
        return iptc_reader.read_png_chunk(
            decode_ztxt(compression_method, compressed_text_data)
        )


class iTXt_Reading(AbstractTextReading):
    def __init__(self):
        super().__init__("utf-8")

    def read(self, chunk_content):
        raw_keyword, packed_data, translated_keyword, text_data = bytes(
            chunk_content
        ).split(b"\x00", maxsplit=3)
        keyword = raw_keyword.decode("latin-1")

        if keyword == "XML:com.adobe.xmp":
            keyword = "XML::XMP"
            text = text_data.replace(b"\x00", b"", 2).decode(self.charset)
            return keyword, text
        elif keyword == EXIF_KEYWORD:
            raise EXIF_Data()

        if not len(packed_data):
            raise EmptyContentError()

        compression_flag = packed_data[0]
        compression_method = packed_data[1]
        language_tag = packed_data[2:]

        if language_tag:
            keyword += f" ({language_tag.decode('ascii')})"
        elif translated_keyword:
            keyword += f"/{translated_keyword.decode(self.charset)}"
        if compression_flag:
            if keyword == IPTC_KEYWORD:
                return iptc_reader.read_png_chunk(
                    decode_ztxt(compression_method, text_data)
                )
            text = decode_ztxt(compression_method, text_data).decode(
                self.charset
            )
        else:
            if keyword == IPTC_KEYWORD:
                return iptc_reader.read_png_chunk(text_data)
            text = text_data.decode(self.charset)

        return keyword, text


def read(png_source):
    SUPPORTED_CHUNKS = {
        b"tEXt": tEXt_Reading,
        b"zTXt": zTXt_Reading,
        b"iTXt": iTXt_Reading,
    }

    if isinstance(png_source, (str, pathlib.Path)):
        reader = png.Reader(filename=png_source)
    else:
        reader = png.Reader(bytes=png_source)
    metadata: dict[str, str] = {}
    for chunk_name, chunk_content in reader.chunks():
        if chunk_name in SUPPORTED_CHUNKS:
            chunk_reader = SUPPORTED_CHUNKS[chunk_name]()
            try:
                value = chunk_reader.read(chunk_content)
                if isinstance(value, tuple):
                    keyword, text_content = value
                elif isinstance(value, dict):
                    metadata.update(value)
                    continue
            except EmptyContentError:
                continue
            except EXIF_Data:
                metadata.update(exif_reader.read(png_source))
                continue
            metadata[keyword] = text_content
    return metadata
