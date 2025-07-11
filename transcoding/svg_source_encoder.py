from . import base_transcoder
from ..decoders import svg as svg_decoder
from .. import common
from . import encoders
import tempfile
import pathlib


class SVGEncoder(base_transcoder.BaseTranscoder):
    def __init__(self, source, path, file_name):
        super().__init__(source, path, file_name, True)

    def _encode(self):
        img = svg_decoder.decode(self._source)
        temporary_image_source = tempfile.NamedTemporaryFile(suffix=".png")
        img.save(temporary_image_source.name, "PNG", compress_level=0)
        with common.utils.InputSourceFacade(self._source) as source_handler:
            self._encoder = encoders.srs_image_encoder.SrsSvgEncoder(
                90, self._get_source_size(), 1, source_handler.get_bytes()
            )

        self._output_file = self._path.joinpath(self._file_name)
        self._output_file = self._encoder.encode(
            pathlib.Path(temporary_image_source.name), self._output_file)
        self._output_size = self._encoder.calc_file_size()
        temporary_image_source.close()
        img.close()

    def _save(self):
        return self._output_file


@base_transcoder.InMemorySourceDecorator
class InMemorySVGEncoder(SVGEncoder):
    pass
