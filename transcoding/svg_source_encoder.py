from . import base_transcoder
from ..decoders import svg as svg_decoder
from .. import common, config
from . import encoders
from .encoders.srs_image_encoder import BaseSrsEncoder
import tempfile
import pathlib
from PIL.Image import DecompressionBombError, Resampling


class SVGEncoder(base_transcoder.BaseTranscoder):
    def __init__(self, source, path, file_name):
        super().__init__(source, path, file_name, True)

    def _encode(self):
        cl2_size_limit = (
            config.srs_image_cl_size_limit[2],
            config.srs_image_cl_size_limit[2]
        )
        try:
            img = svg_decoder.decode(self._source)
            if BaseSrsEncoder.check_cl_size_limit(
                img, 2
            ):
                img = svg_decoder.decode(self._source, cl2_size_limit)
                if BaseSrsEncoder.check_cl_size_limit(
                    img, 2
                ):
                    img.thumbnail(cl2_size_limit, Resampling.LANCZOS)
        except DecompressionBombError:
            img = svg_decoder.decode(self._source, cl2_size_limit)
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
