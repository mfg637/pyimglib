import pathlib
import PIL.Image
from . import statistics
from ..decoders import svg
from .common import srs


class SVG_WRITER:

    def __init__(self, source, path, file_name, item_data, pipe):
        self._source = source
        self._output_file = pathlib.Path(path).joinpath(file_name)
        self._pipe = pipe

    def transcode(self):
        f = None
        clx = self._output_file.with_suffix(".svg")
        if isinstance(self._source, (bytes, bytearray)):
            f = clx.open("bw")
            f.write(self._source)
            f.close()
        statistics.pipe_send(self._pipe)


class SRS_SVG_Converter:
    def __init__(self, source, path, file_name, item_data, pipe, metadata):
        self._source = source
        self._output_file = pathlib.Path(path).joinpath(file_name)
        self._file_name = file_name
        self._item_data = item_data
        self._content_metadata = metadata
        self._pipe = pipe


    def transcode(self):
        fname = self._output_file.with_suffix(".svg")
        f = None
        cl1 = self._file_name + ".svg"
        if isinstance(self._source, (str, pathlib.Path)):
            fname = self._source
        elif isinstance(self._source, (bytes, bytearray)):
            f = fname.open("bw")
            f.write(self._source)
            f.close()

        if isinstance(self._source, bytearray):
            self._source = bytes(self._source)

        img = svg.decode(self._source, (2048, 2048))
        img.thumbnail((2048, 2048), PIL.Image.LANCZOS)
        cl3 = self._file_name + ".webp"
        fname_cl3 = self._output_file.with_suffix(".webp")
        img.save(fname_cl3)

        srs_data = {
            "ftype": "CLSRS",
            "content": {
                "media-type": 0,
                "tags": dict()
            },
            "streams": {
                "image": {"levels": {"1": cl1, "3": cl3}}
            }
        }
        srs.write_srs(srs_data, self._item_data, self._content_metadata, self._output_file.with_suffix(".srs"))
        statistics.pipe_send(self._pipe)
