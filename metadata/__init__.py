import logging
from . import png_reader, jpeg_reader

logger = logging.getLogger(__name__)

supported_formats = {"png", "jpg", "jpeg", "jfif", "webp"}


def get_metadata_from_source(source, _format) -> dict[str, str]:
    if _format == "png":
        return png_reader.read(source)
    elif _format in {"jpg", "jpeg", "jfif", "webp"}:
        return jpeg_reader.read(source)
    else:
        logger.warning(f"Not found reader for format: {_format}")
        return {}
