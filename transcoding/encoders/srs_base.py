import json
import logging
import pathlib
from abc import ABC
import PIL.Image

from pyimglib import config, metadata
from pyimglib.transcoding.encoders import encoder

logger = logging.getLogger(__name__)


def test_alpha_channel(img: PIL.Image.Image):
    if img.mode in {"RGB", "L"}:
        return False
    image_size = img.width * img.height
    if img.mode in {"RGBA", "LA"}:
        return img.histogram()[-1] != image_size
    # I don't know how to check transparency in palette mode
    return True


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
        self.cl0_image_data: bytes | bytearray | None = None
        self.cl0_file_suffix: str = ""
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

        stream_type_key = MEDIA_TYPE_CODE_TO_STREAM_TYPE_KEY[
            srs_data["content"]["media-type"]
        ]

        list_files = []
        for level in srs_data["streams"][stream_type_key]["levels"]:
            list_files.append(
                parent_dir.joinpath(
                    srs_data["streams"][stream_type_key]["levels"][level])
            )

        list_files.append(self.srs_file_path)
        return list_files

    def write_image_srs(
        self,
        input_file,
        img,
        cl1_file_name,
        cl3_file_name,
        output_file: pathlib.Path,
        cl2_file_name=None
    ):
        srs_data = {
            "ftype": "CLSRS",
            "content": {
                "media-type": 0,
                "attachment": dict()
            },
            "streams": {
                "image": {"levels": dict()}
            }
        }
        if self.cl0_image_data:
            cl0_file_path = output_file.with_stem(
                f"{output_file.stem}_cl0"
            ).with_suffix(self.cl0_file_suffix)
            srs_data["streams"]["image"]["levels"]["0"] = cl0_file_path.name
            cl0_file_path.write_bytes(self.cl0_image_data)
        if cl1_file_name is not None:
            if (
                img.width > config.srs_image_cl_size_limit[2]
                or img.height > config.srs_image_cl_size_limit[2]
                or cl2_file_name is not None
            ):
                srs_data["streams"]["image"]["levels"]["1"] = cl1_file_name
            elif (
                img.width <= config.srs_image_cl_size_limit[2]
                and img.height <= config.srs_image_cl_size_limit[2]
                and cl2_file_name is None
            ):
                srs_data["streams"]["image"]["levels"]["2"] = cl1_file_name
            elif cl2_file_name is not None:
                srs_data["streams"]["image"]["levels"]["1"] = cl1_file_name
        if cl2_file_name is not None:
            srs_data["streams"]["image"]["levels"]["2"] = cl2_file_name
        if cl3_file_name is not None:
            srs_data["streams"]["image"]["levels"]["3"] = cl3_file_name

        if input_file.suffix == ".png":
            srs_data["content"]["attachment"] = \
                metadata.png_reader.read(input_file)
        elif input_file.suffix in {".jpg", ".jpeg", ".jfif"}:
            srs_data["content"]["attachment"] = \
                metadata.jpeg_reader.read(input_file)

        logger.debug("srs content: {}".format(srs_data.__repr__()))

        self.srs_file_path = output_file.with_suffix(".srs")
        with self.srs_file_path.open("w") as f:
            json.dump(srs_data, f)

    @staticmethod
    def check_cl_size_limit(img, compatibility_level: int):
        return (
            (img.width > config.srs_image_cl_size_limit[compatibility_level]) |
            (img.height > config.srs_image_cl_size_limit[compatibility_level])
        )

    @staticmethod
    def scale_img(img, compatibility_level):
        scaled_img = img.copy()
        scaled_img.thumbnail(
            (
                config.srs_image_cl_size_limit[compatibility_level],
                config.srs_image_cl_size_limit[compatibility_level]
            ),
            PIL.Image.Resampling.LANCZOS
        )
        return scaled_img

    def cl2_encode(self, img, input_file, output_file):
        if self.check_cl_size_limit(img, 2):
            cl2_scaled_img = self.scale_img(img, 2)
            cl2_encoder = self.cl2_encoder_type(input_file, cl2_scaled_img)
            cl2_file_path = output_file.with_stem(
                output_file.stem + '_CL2').with_suffix(cl2_encoder.SUFFIX)
            cl2_file_name = cl2_file_path.name
            cl2_encoded_data = cl2_encoder.encode(self._quality)
            if len(cl2_encoded_data) == 0:
                raise ValueError("Empty CL2 representation")
            with cl2_file_path.open("bw") as f:
                f.write(cl2_encoded_data)
            return cl2_file_name, len(cl2_encoded_data)
        return None, 0
