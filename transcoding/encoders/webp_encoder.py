import io
import pathlib

import PIL.Image

from .encoder import Encoder


class WEBPEncoder(Encoder):
    def __init__(self, source: PIL.Image.Image):
        self.source = source

    def encode(self, quality) -> memoryview:
        lossy_out_io = io.BytesIO()
        self.source.save(lossy_out_io, format="WEBP", lossless=False, quality=quality, method=6)
        return lossy_out_io.getbuffer()

    def save(self, encoded_data: memoryview, path: pathlib.Path, name: str):
        pass
