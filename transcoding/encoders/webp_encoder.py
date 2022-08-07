import io
import pathlib

import PIL.Image

from .encoder import Encoder

MAX_SIZE = 16383


class WEBPEncoder(Encoder):
    def __init__(self, source, img: PIL.Image.Image):
        self.source = img

    def encode(self, quality, lossless=False) -> bytes:
        lossy_out_io = io.BytesIO()
        self.source.save(lossy_out_io, format="WEBP", lossless=lossless, quality=quality, method=6)
        return lossy_out_io.getvalue()

    def save(self, encoded_data: bytes, path: pathlib.Path, name: str) -> pathlib.Path:
        output_fname = path.joinpath(name + ".webp")
        outfile = open(output_fname, 'wb')
        outfile.write(encoded_data)
        outfile.close()
        return output_fname


class WEBPLosslessEncoder(WEBPEncoder):
    def encode(self, quality) -> bytes:
        return WEBPEncoder.encode(self, quality, True)
