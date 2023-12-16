import json
import logging
import math
import pathlib
import tempfile
from abc import ABC
import typing

import png

import PIL.Image

from . import encoder, webp_encoder, avif_encoder
from .. import common
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
            if img.width > config.srs_cl2_size_limit or img.height > config.srs_cl2_size_limit \
                    or cl2_file_name is not None:
                srs_data["streams"]["image"]["levels"]["1"] = cl1_file_name
        if cl2_file_name is not None:
            srs_data["streams"]["image"]["levels"]["2"] = cl2_file_name
        if cl3_file_name is not None:
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

        logger.debug("srs content: {}".format(srs_data.__repr__()))

        self.srs_file_path = output_file.with_suffix(".srs")
        with self.srs_file_path.open("w") as f:
            json.dump(srs_data, f)

    def cl2_encode(self, img, input_file, output_file):
        if img.width > config.srs_cl2_size_limit or img.height > config.srs_cl2_size_limit:
            cl2_scaled_img = img.copy()
            cl2_scaled_img.thumbnail(
                (config.srs_cl2_size_limit, config.srs_cl2_size_limit),
                PIL.Image.Resampling.LANCZOS
            )
            cl2_encoder = self.cl2_encoder_type(input_file, cl2_scaled_img)
            cl2_file_path = output_file.with_stem(output_file.stem + '_CL2').with_suffix(cl2_encoder.SUFFIX)
            cl2_file_name = cl2_file_path.name
            cl2_encoded_data = cl2_encoder.encode(self._quality)
            with cl2_file_path.open("bw") as f:
                f.write(cl2_encoded_data)
            return cl2_file_name, len(cl2_encoded_data)
        return None, 0


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
        cl2_file_name, cl2_data_len = self.cl2_encode(img, input_file, output_file)


        with cl1_file_path.open("bw") as f:
            f.write(self.cl1_image_data)
        with cl3_file_path.open("bw") as f:
            f.write(self.cl3_image_data)

        self.write_image_srs(input_file, img, cl1_file_name, cl3_file_name, output_file, cl2_file_name)

        return self.srs_file_path


class SrsLossyJpegXlEncoder(BaseSrsEncoder):
    """
    JPEG XL format have special features like lossless JPEG recompression, which other not.
    JPEG recompression, and generating JPEG compatible JXL bitstream requires special processing pipeline.
    This encoder makes JPEG compatible bitstream.
    This encoder depends on specified version of libjxl: commit 38b629f and later (approximately 0.9.0).
    """

    def __init__(self, base_quality_level, source_data_size, ratio, cl1_suffix=".jxl"):
        super().__init__(base_quality_level, source_data_size, ratio)
        self._cl1_suffix = cl1_suffix

    def alpha_channel_test(self, img: PIL.Image.Image):
        if img.mode in {"RGB", "L"}:
            return False
        image_size = img.width * img.height
        if img.mode in {"RGBA", "LA"}:
            return img.histogram()[-1] != image_size
        # I don't know how to check transparency in palette mode
        return True

    def encode_cl2(self, source: PIL.Image.Image, output_file: pathlib.Path):
        src_tmp_file = tempfile.NamedTemporaryFile(suffix=".png")
        source.save(src_tmp_file, "PNG")
        source_file = src_tmp_file.name
        jpeg_tmp_file = tempfile.NamedTemporaryFile(suffix=".jpg")
        # use cjpegli encoder to generate libjxl tuned jpeg file
        commandline = [
            "cjpegli",
            source_file,
            jpeg_tmp_file.name
        ]
        common.run_subprocess(commandline, log_stdout=True)
        src_tmp_file.close()
        commandline = [
            "cjxl",
            jpeg_tmp_file.name,
            output_file
        ]
        common.run_subprocess(commandline, log_stdout=True)
        jpeg_tmp_file.close()

    def encode_cl1(self, input_file: pathlib.Path, output_file: pathlib.Path, img: PIL.Image.Image = None):
        commandline = [
            "cjxl",
            input_file,
            output_file,
            "-d", "1",
            "--lossless_jpeg=0"
        ]
        common.run_subprocess(commandline, log_stdout=True)

    def encode(self, input_file: pathlib.Path, output_file: pathlib.Path):
        logger.debug("open image")
        img = PIL.Image.open(input_file)

        has_alpha_channel = self.alpha_channel_test(img)

        logger.debug("has alpha channel: {}".format(has_alpha_channel.__repr__()))

        if has_alpha_channel:
            # JPEG can't store transparency
            regular_lossy_encoder = SrsLossyImageEncoder(self.base_quality_level, self.source_data_size, self.ratio)
            img.close()
            self.srs_file_path = regular_lossy_encoder.encode(input_file, output_file)
            return self.srs_file_path

        cl2_file_name = None
        cl1_file_name = None

        if img.width > config.srs_cl2_size_limit or img.height > config.srs_cl2_size_limit:
            logger.debug("cl1 encode")
            cl2_image = img.copy()
            cl2_image.thumbnail((config.srs_cl2_size_limit, config.srs_cl2_size_limit))
            cl2_file_path = output_file.with_stem("{}_cl2".format(output_file.stem)).with_suffix(".jxl")
            cl2_file_name = cl2_file_path.name
            self.encode_cl2(cl2_image, cl2_file_path)
            cl1_file_path = output_file.with_suffix(self._cl1_suffix)
            cl1_file_name = cl1_file_path.name
            self.encode_cl1(input_file, cl1_file_path, img)
        else:
            logger.debug("cl2 encode")
            cl2_file_path = output_file.with_suffix(".jxl")
            cl2_file_name = cl2_file_path.name
            self.encode_cl2(img, cl2_file_path)

        self.write_image_srs(input_file, img, cl1_file_name, None, output_file, cl2_file_name)

        return self.srs_file_path

class HybridImageEncoder(SrsLossyJpegXlEncoder):
    def __init__(self, base_quality_level, source_data_size, ratio):
        super().__init__(base_quality_level, source_data_size, ratio, cl1_suffix=".avif")

    def encode_cl1(self, input_file: pathlib.Path, output_file: pathlib.Path, img: PIL.Image.Image = None):
        logger.info("jpeg xl cl1 encoder redefined to AVIF encoder")
        if img is None:
            logger.info("img is none. Opening file…")
            img = PIL.Image.open(input_file)
        cl1_encoder = avif_encoder.AVIFEncoder(input_file, img)
        cl1_image_data = cl1_encoder.encode(95)
        with output_file.open("bw") as f:
            f.write(cl1_image_data)

class SrsLosslessImageEncoder(BaseSrsEncoder):
    cl3_encoder_type:  typing.Type[encoder.BytesEncoder] | None = None
    cl2_encoder_type: typing.Type[encoder.BytesEncoder] | None = None
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

            cl1_file_path = output_file.with_suffix(self.cl1_encoder.SUFFIX)
            cl3_file_path = output_file.with_suffix(self.cl3_encoder.SUFFIX)
            cl1_file_name = cl1_file_path.name
            cl3_file_name = cl3_file_path.name
            cl2_file_name = None

            self._quality = 100
            self.cl1_image_data = self.cl1_encoder.encode(100)
            self.cl3_image_data = self.cl3_encoder.encode(100)
            cl2_file_name, cl2_data_len = self.cl2_encode(img, input_file, output_file)

            while (len(self.cl1_image_data) + len(self.cl3_image_data) + cl2_data_len) >= self.source_data_size \
                    and self._quality > 50:
                self._quality -= 10
                self.cl3_image_data = self.cl3_lossy_encoder.encode(self._quality)
                cl2_file_name, cl2_data_len = self.cl2_encode(img, input_file, output_file)

            with cl1_file_path.open("bw") as f:
                f.write(self.cl1_image_data)
            with cl3_file_path.open("bw") as f:
                f.write(self.cl3_image_data)
            self.write_image_srs(input_file, img, cl1_file_name, cl3_file_name, output_file, cl2_file_name)
        else:
            self.cl3_encoder = self.cl3_encoder_type(input_file, img)
            self.cl3_image_data = self.cl3_encoder.encode(100)
            cl3_file_path = output_file.with_suffix(self.cl3_encoder.SUFFIX)
            cl3_file_name = cl3_file_path.name
            with cl3_file_path.open("bw") as f:
                f.write(self.cl3_image_data)
            self.write_image_srs(input_file, img, None, cl3_file_name, output_file)

        return self.srs_file_path
