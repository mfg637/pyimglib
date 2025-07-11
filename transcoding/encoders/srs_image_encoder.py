import logging
import math
import pathlib
import tempfile
import typing

import PIL.Image

from .srs_base import BaseSrsEncoder, test_alpha_channel

from ... import config
from ... import common
from . import avif_encoder, encoder

logger = logging.getLogger(__name__)


class SrsLossyImageEncoder(BaseSrsEncoder):
    cl3_encoder_type:  typing.Type[encoder.BytesEncoder] | None = None
    cl2_encoder_type: typing.Type[encoder.BytesEncoder] | None = None
    cl1_encoder_type: typing.Type[encoder.BytesEncoder] | None = None
    cl3_size_limit = config.srs_image_cl_size_limit[3]
    cl1_size_limit = config.srs_image_cl_size_limit[1]

    def __init__(
        self,
        base_quality_level,
        source_data_size,
        ratio,
        multipass: bool = True
    ):
        super().__init__(base_quality_level, source_data_size, ratio)
        self.multipass = multipass

    def encode(
        self, input_file: pathlib.Path, output_file: pathlib.Path
    ) -> pathlib.Path:
        img = PIL.Image.open(input_file)
        cl1_img = img
        if self.check_cl_size_limit(img, 1):
            cl1_img = self.scale_img(img, 1)
            self.cl1_encoder = self.cl1_encoder_type(None, cl1_img)
        else:
            self.cl1_encoder = self.cl1_encoder_type(input_file, cl1_img)

        if isinstance(self.cl1_encoder, avif_encoder.AVIFEncoder):
            self.cl1_encoder.encoding_speed = min(
                config.avifenc_encoding_speed * 2, 10)
        cl3_scaled_img = img
        if self.check_cl_size_limit(img, 3):
            cl3_scaled_img = self.scale_img(img, 3)
        self.cl3_encoder = self.cl3_encoder_type(input_file, cl3_scaled_img)
        self._quality = self.base_quality_level
        self.cl1_image_data = self.cl1_encoder.encode(self._quality)
        cl1_size = len(self.cl1_image_data)
        ratio = self.ratio
        while (
            self.multipass and
            ((cl1_size / self.source_data_size) > ((100 - ratio) * 0.01)) and
            (self._quality >= 60)
        ):
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
        cl2_file_name, cl2_data_len = self.cl2_encode(
            img, input_file, output_file)

        with cl1_file_path.open("bw") as f:
            f.write(self.cl1_image_data)
        with cl3_file_path.open("bw") as f:
            f.write(self.cl3_image_data)

        self.write_image_srs(input_file, img, cl1_file_name,
                             cl3_file_name, output_file, cl2_file_name)

        cl3_scaled_img.close()
        cl1_img.close()

        return self.srs_file_path


class SrsSvgEncoder(SrsLossyImageEncoder):
    def __init__(
        self,
        base_quality_level,
        source_data_size,
        ratio,
        cl0_image_data
    ):
        super().__init__(base_quality_level, source_data_size, ratio, False)
        self.cl0_image_data = cl0_image_data
        self.cl0_file_suffix = ".svg"


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

    def encode_cl2(self, source: PIL.Image.Image, output_file: pathlib.Path):
        jpeg_tmp_file = tempfile.NamedTemporaryFile(suffix=".jpg")
        if config.jpegli_enabled:
            src_tmp_file = tempfile.NamedTemporaryFile(suffix=".png")
            source.save(src_tmp_file, "PNG")
            source_file = src_tmp_file.name
            # use cjpegli encoder to generate libjxl tuned jpeg file
            commandline = [
                "cjpegli",
                source_file,
                jpeg_tmp_file.name
            ]
            common.run_subprocess(commandline, log_stdout=True)
            src_tmp_file.close()
        else:
            if source.mode == "RGBA":
                _source = source.convert(mode="RGB")
                source.close()
                source = _source
            source.save(jpeg_tmp_file, "JPEG", quality=90, subsampling=0)
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

        has_alpha_channel = test_alpha_channel(img)

        logger.debug("has alpha channel: {}".format(
            has_alpha_channel.__repr__()))

        if has_alpha_channel:
            # JPEG can't store transparency
            regular_lossy_encoder = SrsLossyImageEncoder(
                self.base_quality_level, self.source_data_size, self.ratio)
            img.close()
            self.srs_file_path = regular_lossy_encoder.encode(
                input_file, output_file)
            return self.srs_file_path

        cl2_file_name = None
        cl1_file_name = None

        if self.check_cl_size_limit(img, 2):
            logger.debug("cl1 encode")
            cl2_image = img.copy()
            cl2_image.thumbnail(
                (config.srs_cl2_size_limit, config.srs_cl2_size_limit))
            cl2_file_path = output_file.with_stem(
                "{}_cl2".format(output_file.stem)).with_suffix(".jxl")
            cl2_file_name = cl2_file_path.name
            self.encode_cl2(cl2_image, cl2_file_path)
            cl1_file_path = output_file.with_suffix(self._cl1_suffix)
            cl1_file_name = cl1_file_path.name
            cl1_image = img
            if self.check_cl_size_limit(img, 1):
                cl1_image = self.scale_img(img, 1)
            self.encode_cl1(input_file, cl1_file_path, cl1_image)
        else:
            logger.debug("cl2 encode")
            cl2_file_path = output_file.with_suffix(".jxl")
            cl2_file_name = cl2_file_path.name
            self.encode_cl2(img, cl2_file_path)

        self.write_image_srs(input_file, img, cl1_file_name,
                             None, output_file, cl2_file_name)

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
    cl3_size_limit = config.srs_image_cl_size_limit[3]

    def __init__(self, base_quality_level, source_data_size, ratio):
        super().__init__(base_quality_level, source_data_size, ratio)
        self.cl3_lossy_encoder: encoder.BytesEncoder | None = None

    def encode(self, input_file: pathlib.Path, output_file: pathlib.Path) -> pathlib.Path:
        img = PIL.Image.open(input_file)
        cl1_image = img
        if self.check_cl_size_limit(img, 1):
            cl1_image = self.scale_img(img, 1)
        self.cl1_encoder = self.cl1_encoder_type(input_file, cl1_image)
        cl3_scaled_img = img
        if self.check_cl_size_limit(img, 3):
            cl3_scaled_img = self.scale_img(img, 3)
            self.cl3_encoder = self.cl3_encoder_type(
                input_file, cl3_scaled_img)
            self.cl3_lossy_encoder = self.cl3_lossy_encoder_type(
                input_file, cl3_scaled_img)
            self._quality = self.base_quality_level

            cl1_file_path = output_file.with_suffix(self.cl1_encoder.SUFFIX)
            cl3_file_path = output_file.with_suffix(self.cl3_encoder.SUFFIX)
            cl1_file_name = cl1_file_path.name
            cl3_file_name = cl3_file_path.name
            cl2_file_name = None

            self._quality = 100
            self.cl1_image_data = self.cl1_encoder.encode(100)
            self.cl3_image_data = self.cl3_encoder.encode(100)
            cl2_file_name, cl2_data_len = self.cl2_encode(
                img, input_file, output_file)

            while (len(self.cl1_image_data) + len(self.cl3_image_data) + cl2_data_len) >= self.source_data_size \
                    and self._quality > 50:
                self._quality -= 10
                self.cl3_image_data = self.cl3_lossy_encoder.encode(
                    self._quality)
                cl2_file_name, cl2_data_len = self.cl2_encode(
                    img, input_file, output_file)

            with cl1_file_path.open("bw") as f:
                f.write(self.cl1_image_data)
            with cl3_file_path.open("bw") as f:
                f.write(self.cl3_image_data)
            self.write_image_srs(input_file, img, cl1_file_name,
                                 cl3_file_name, output_file, cl2_file_name)
        else:
            self.cl3_encoder = self.cl3_encoder_type(input_file, img)
            self.cl3_image_data = self.cl3_encoder.encode(100)
            cl3_file_path = output_file.with_suffix(self.cl3_encoder.SUFFIX)
            cl3_file_name = cl3_file_path.name
            with cl3_file_path.open("bw") as f:
                f.write(self.cl3_image_data)
            self.write_image_srs(input_file, img, None,
                                 cl3_file_name, output_file)

        return self.srs_file_path
