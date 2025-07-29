import logging
from . import exif_reader, iptc_reader, png_reader

logger = logging.getLogger(__name__)

supported_formats = {"png", "jpg", "jpeg", "jfif", "webp"}


def get_metadata_from_source(source, _format) -> dict[str, str]:
    if _format == "png":
        return png_reader.read(source)
    elif _format in {"jpg", "jpeg", "jfif", "webp"}:
        metadata = exif_reader.read(source)
        if _format in {"jpg", "jpeg", "jfif"}:
            metadata.update(iptc_reader.read(source))
        return metadata
    else:
        logger.warning(f"Not found reader for format: {_format}")
        return {}
