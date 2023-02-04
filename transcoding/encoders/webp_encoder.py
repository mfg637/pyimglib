import io
import pathlib

import PIL.Image

from .encoder import BytesEncoder

MAX_SIZE = 16383


class WEBPEncoder(BytesEncoder):
    def __init__(self, source, img: PIL.Image.Image):
        BytesEncoder.__init__(self, ".webp")
        self.source = img

    def encode(self, quality, lossless=False) -> bytes:
        lossy_out_io = io.BytesIO()
        self.source.save(lossy_out_io, format="WEBP", lossless=lossless, quality=quality, method=6)
        return lossy_out_io.getvalue()


class WEBPLosslessEncoder(WEBPEncoder):
    def encode(self, quality) -> bytes:
        return WEBPEncoder.encode(self, quality, True)
