import json
import math
import pathlib

import PIL.Image

from . import encoder, webp_encoder
from ... import config


class SrsImageEncoder(encoder.FilesEncoder):
    cl3_encoder_type: encoder.BytesEncoder | None = None
    cl1_encoder_type: encoder.BytesEncoder | None = None
    cl3_size_limit = config.srs_cl3_size_limit

    def __init__(self, base_quality_level, source_data_size, ratio):
        self.base_quality_level = base_quality_level
        self.source_data_size = source_data_size
        self.ratio = ratio
        self.cl3_image_data: bytes | None = None
        self.cl1_image_data: bytes | None = None
        self.cl1_encoder: encoder.BytesEncoder | None = None
        self.cl3_encoder: encoder.BytesEncoder | None = None
        self.srs_file_path: pathlib.Path| None = None

    def set_manifest_file(self, manifest_file: pathlib.Path):
        self.srs_file_path = manifest_file

    def encode(self, input_file: pathlib.Path, output_file: pathlib.Path) -> pathlib.Path:
        img = PIL.Image.open(input_file)
        self.cl1_encoder = self.cl1_encoder_type(input_file, img)
        cl3_scaled_img = img.copy()
        if (img.width > self.cl3_size_limit) | (img.height > self.cl3_size_limit):
            cl3_scaled_img.thumbnail(
                    (self.cl3_size_limit, self.cl3_size_limit),
                    PIL.Image.Resampling.LANCZOS
            )
        self.cl3_encoder = self.cl3_encoder_type(input_file, cl3_scaled_img)
        self._quality = self.base_quality_level
        self.cl1_image_data = self.cl1_encoder.encode(self._quality)
        cl1_size = len(self.cl1_image_data)
        ratio = self.ratio
        while ((cl1_size / self.source_data_size) > ((100 - ratio) * 0.01)) and (self._quality >= 60):
            self._quality -= 5
            self.cl1_image_data = self.cl1_encoder.encode(self._quality)
            cl1_size = len(self.cl1_image_data)
            ratio = math.ceil(ratio // config.WEBP_QSCALE)
        self.cl3_image_data = self.cl3_encoder.encode(self._quality)

        cl1_file_path = output_file.with_suffix(self.cl1_encoder.SUFFIX)
        cl3_file_path = output_file.with_suffix(self.cl3_encoder.SUFFIX)
        cl1_file_name = cl1_file_path.name
        cl3_file_name = cl3_file_path.name
        with cl1_file_path.open("bw") as f:
            f.write(self.cl1_image_data)
        with cl3_file_path.open("bw") as f:
            f.write(self.cl3_image_data)

        srs_data = {
            "ftype": "CLSRS",
            "content": {
                "media-type": 0,
            },
            "streams": {
                "image": {"levels": dict()}
            }
        }
        if img.width > self.cl3_size_limit or img.height > self.cl3_size_limit:
            srs_data["streams"]["image"]["levels"]["1"] = cl1_file_name
        else:
            srs_data["streams"]["image"]["levels"]["2"] = cl1_file_name
        srs_data["streams"]["image"]["levels"]["3"] = cl3_file_name

        self.srs_file_path = output_file.with_suffix(".srs")
        with self.srs_file_path.open("w") as f:
            json.dump(srs_data, f)
        return self.srs_file_path

    def get_files(self) -> list[pathlib.Path]:
        srs_data = None
        parent_dir = self.srs_file_path.parent
        with self.srs_file_path.open('r') as f:
            srs_data = json.load(f)

        list_files = []
        for level in srs_data["streams"]["image"]["levels"]:
            list_files.append(parent_dir.joinpath(srs_data["streams"]["image"]["levels"][level]))

        list_files.append(self.srs_file_path)
        return list_files

