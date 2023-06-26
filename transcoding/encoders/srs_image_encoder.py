import json
import logging
import math
import pathlib
from abc import ABC
import typing

import png

import PIL.Image

from . import encoder, webp_encoder, avif_encoder
from ... import config

logger = logging.getLogger(__name__)


MEDIA_TYPE_CODE_TO_STREAM_TYPE_KEY = {
    0: "image",
    1: "audio",
    2: "video",
    3: "video"
}


class BaseSrsEncoder(encoder.FilesEncoder, ABC):
    def __init__(self, base_quality_level, source_data_size, ratio):
        self.base_quality_level = base_quality_level
        self.source_data_size = source_data_size
        self.ratio = ratio
        self.cl3_image_data: bytes | None = None
        self.cl1_image_data: bytes | None = None
        self.cl1_encoder: encoder.BytesEncoder | None = None
        self.cl3_encoder: encoder.BytesEncoder | None = None
        self.srs_file_path: pathlib.Path | None = None

    def set_manifest_file(self, manifest_file: pathlib.Path):
        self.srs_file_path = manifest_file

    def get_files(self) -> list[pathlib.Path]:
        srs_data = None
        parent_dir = self.srs_file_path.parent
        with self.srs_file_path.open('r') as f:
            srs_data = json.load(f)

        stream_type_key = MEDIA_TYPE_CODE_TO_STREAM_TYPE_KEY[srs_data["content"]["media-type"]]

        list_files = []
        for level in srs_data["streams"][stream_type_key]["levels"]:
            list_files.append(
                parent_dir.joinpath(srs_data["streams"][stream_type_key]["levels"][level])
            )

        list_files.append(self.srs_file_path)
        return list_files

    def write_image_srs(self, input_file, img, cl1_file_name, cl3_file_name, output_file, cl2_file_name=None):
        srs_data = {
            "ftype": "CLSRS",
            "content": {
                "media-type": 0,
            },
            "streams": {
                "image": {"levels": dict()}
            }
        }
        if cl1_file_name is not None:
            if img.width > config.srs_avif_trigger_size or img.height > config.srs_avif_trigger_size \
                    or cl2_file_name is not None:
                srs_data["streams"]["image"]["levels"]["1"] = cl1_file_name
                if cl2_file_name is not None:
                    srs_data["streams"]["image"]["levels"]["2"] = cl2_file_name
            else:
                srs_data["streams"]["image"]["levels"]["2"] = cl1_file_name
        srs_data["streams"]["image"]["levels"]["3"] = cl3_file_name

        if input_file.suffix == ".png":
            png_file = png.Reader(filename=input_file)
            file_text_metadata: dict[str, str] = dict()
            for chunk_name, chunk_content in png_file.chunks():
                if chunk_name == b"tEXt":
                    raw_keyword, raw_text_content = bytes(chunk_content).split(b'\x00')
                    keyword: str = raw_keyword.decode("utf-8")
                    text_content: str = raw_text_content.decode("utf-8")
                    srs_data["content"][keyword] = text_content

        self.srs_file_path = output_file.with_suffix(".srs")
        with self.srs_file_path.open("w") as f:
            json.dump(srs_data, f)


class SrsLossyImageEncoder(BaseSrsEncoder):
    cl3_encoder_type:  typing.Type[encoder.BytesEncoder] | None = None
    cl2_encoder_type: typing.Type[encoder.BytesEncoder] | None = None
    cl1_encoder_type: typing.Type[encoder.BytesEncoder] | None = None
    cl3_size_limit = config.srs_cl3_size_limit

    def __init__(self, base_quality_level, source_data_size, ratio):
        super().__init__(base_quality_level, source_data_size, ratio)

    def encode(self, input_file: pathlib.Path, output_file: pathlib.Path) -> pathlib.Path:
        img = PIL.Image.open(input_file)
        self.cl1_encoder = self.cl1_encoder_type(input_file, img)
        if isinstance(self.cl1_encoder, avif_encoder.AVIFEncoder):
            self.cl1_encoder.encoding_speed = min(config.avifenc_encoding_speed * 2, 10)
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

        if isinstance(self.cl1_encoder, avif_encoder.AVIFEncoder):
            self.cl1_encoder.encoding_speed = config.avifenc_encoding_speed
            self.cl1_image_data = self.cl1_encoder.encode(self._quality)

        cl1_file_path = output_file.with_suffix(self.cl1_encoder.SUFFIX)
        cl3_file_path = output_file.with_suffix(self.cl3_encoder.SUFFIX)
        cl1_file_name = cl1_file_path.name
        cl2_file_name = None
        cl3_file_name = cl3_file_path.name

        self.cl3_image_data = self.cl3_encoder.encode(self._quality - 5)
        if img.width > config.srs_avif_trigger_size or img.height > config.srs_avif_trigger_size:
            logger.info("generating CL2 image")
            cl2_scaled_img = img.copy()
            cl2_scaled_img.thumbnail(
                (config.srs_avif_trigger_size, config.srs_avif_trigger_size),
                PIL.Image.Resampling.LANCZOS
            )
            cl2_encoder = self.cl2_encoder_type(input_file, cl2_scaled_img)
            cl2_file_path = output_file.with_stem(output_file.stem + '_CL2').with_suffix(cl2_encoder.SUFFIX)
            cl2_file_name = cl2_file_path.name
            cl2_encoded_data = cl2_encoder.encode(self._quality)
            with cl2_file_path.open("bw") as f:
                f.write(cl2_encoded_data)


        with cl1_file_path.open("bw") as f:
            f.write(self.cl1_image_data)
        with cl3_file_path.open("bw") as f:
            f.write(self.cl3_image_data)

        self.write_image_srs(input_file, img, cl1_file_name, cl3_file_name, output_file, cl2_file_name)

        return self.srs_file_path


class SrsLosslessImageEncoder(BaseSrsEncoder):
    cl3_encoder_type:  typing.Type[encoder.BytesEncoder] | None = None
    cl3_lossy_encoder_type: typing.Type[encoder.BytesEncoder] | None = None
    cl1_encoder_type: typing.Type[encoder.BytesEncoder] | None = None
    cl3_size_limit = config.srs_cl3_size_limit

    def __init__(self, base_quality_level, source_data_size, ratio):
        super().__init__(base_quality_level, source_data_size, ratio)
        self.cl3_lossy_encoder: encoder.BytesEncoder | None = None

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
            self.cl3_lossy_encoder = self.cl3_lossy_encoder_type(input_file, cl3_scaled_img)
            self._quality = self.base_quality_level

            self.cl1_image_data = self.cl1_encoder.encode(100)
            self.cl3_image_data = self.cl3_encoder.encode(100)

            self._quality = 100

            while (len(self.cl1_image_data) + len(self.cl3_image_data)) >= self.source_data_size and self._quality > 50:
                self._quality -= 10
                self.cl3_image_data = self.cl3_lossy_encoder.encode(self._quality)

            cl1_file_path = output_file.with_suffix(self.cl1_encoder.SUFFIX)
            cl3_file_path = output_file.with_suffix(self.cl3_encoder.SUFFIX)
            cl1_file_name = cl1_file_path.name
            cl3_file_name = cl3_file_path.name
            with cl1_file_path.open("bw") as f:
                f.write(self.cl1_image_data)
            with cl3_file_path.open("bw") as f:
                f.write(self.cl3_image_data)
            self.write_image_srs(input_file, img, cl1_file_name, cl3_file_name, output_file)
        else:
            self.cl3_encoder = self.cl3_encoder_type(input_file, img)
            self.cl3_image_data = self.cl3_encoder.encode(100)
            cl3_file_path = output_file.with_suffix(self.cl3_encoder.SUFFIX)
            cl3_file_name = cl3_file_path.name
            with cl3_file_path.open("bw") as f:
                f.write(self.cl3_image_data)
            self.write_image_srs(input_file, img, None, cl3_file_name, output_file)

        return self.srs_file_path
