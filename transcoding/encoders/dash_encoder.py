import pathlib
import subprocess
import re
from typing import Iterable

from .encoder import VideoEncoder
from .. import common
from ...decoders import ffmpeg
from ... import config

import xml.dom.minidom

file_template_regex = re.compile("\$[\da-zA-Z\-%]+\$")


class DASHEncoder(VideoEncoder):
    def __init__(self, crf: int, gop_size, pix_fmt, high_tier_encoder):
        self._crf = crf
        self._target_pixel_format = pix_fmt
        self._target_encoder = high_tier_encoder
        self._gop_size = gop_size

    @staticmethod
    def get_files(mpd_file: pathlib.Path):
        list_files = []

        file_templates = set()
        parent_dir = mpd_file.parent
        mpd_document: xml.dom.minidom.Document = xml.dom.minidom.parse(str(mpd_file))
        segment_templates: Iterable[xml.dom.minidom.Element] = mpd_document.getElementsByTagName("SegmentTemplate")
        for template in segment_templates:
            file_templates.add(file_template_regex.sub("*", template.getAttribute("initialization")))
            file_templates.add(file_template_regex.sub("*", template.getAttribute("media")))
        print(file_templates)

        file_templates_iterable: tuple[str] = tuple(file_templates)
        for file_template in file_templates_iterable:
            for file in parent_dir.glob(file_template):
                if file.is_file():
                    list_files.append(file)

        list_files.append(mpd_file)
        return list_files

    @staticmethod
    def get_file_size(mpd_file: pathlib.Path):
        files = DASHEncoder.get_files(mpd_file)
        size = 0

        for file in files:
            size += file.stat().st_size

        return size

    @staticmethod
    def delete_result(mpd_file: pathlib.Path):
        files = DASHEncoder.get_files(mpd_file)
        for file in files:
            file.unlink()

    def encode(self, input_file: pathlib.Path, output_file: pathlib.Path) -> pathlib.Path:
        src_metadata = ffmpeg.probe(input_file)
        video = ffmpeg.parser.find_video_stream(src_metadata)
        fps = ffmpeg.parser.get_fps(video)

        limited_min_size = 720
        if fps > 30:
            limited_min_size = 360

        width_orig = video["width"]
        height_orig = video["height"]
        width_max = 2
        height_max = 2
        width_small = 2
        height_small = 2

        def scale_size(width, height, scale):
            scaled_width = int(round(width * scale))
            scaled_height = int(round(height * scale))
            return scaled_width, scaled_height

        def get_rounded_size(width_small, height_small, scale_coef):
            scale_precission = 6
            rounded_scale_coef = scale_coef
            width_max, height_max = scale_size(width_small, height_small, rounded_scale_coef)
            ar_scaled = width_max / height_max
            while ar_scaled != aspect_ratio:
                scale_precission -= 1
                rounded_scale_coef = common.bit_round(scale_coef, scale_precission)
                width_max, height_max = scale_size(width_small, height_small, rounded_scale_coef)
                ar_scaled = width_max / height_max
            return width_max, height_max, rounded_scale_coef

        if height_orig <= width_orig:
            if height_orig <= limited_min_size:
                width_small = width_max = int(common.bit_round(width_orig, -1))
                height_small = height_max = int(common.bit_round(height_orig, -1))
            else:
                height_small = limited_min_size
                scale_coef = height_orig / limited_min_size
                width_small = int(common.bit_round(width_orig / scale_coef, -1))
                aspect_ratio = width_small / height_small

                width_max, height_max, rounded_scale_coef = get_rounded_size(width_small, height_small, scale_coef)
                if rounded_scale_coef == 1:
                    width_small = width_max = int(common.bit_round(width_orig, -1))
                    height_small = height_max = int(common.bit_round(height_orig, -1))
        if height_orig > width_orig:
            if width_orig <= limited_min_size:
                width_small = width_max = int(common.bit_round(width_orig, -1))
                height_small = height_max = int(common.bit_round(height_orig, -1))
            else:
                width_small = limited_min_size
                scale_coef = width_orig / limited_min_size
                height_small = common.bit_round(width_orig / scale_coef, -1)
                aspect_ratio = width_small / height_small

                width_max, height_max, rounded_scale_coef = get_rounded_size(width_small, height_small, scale_coef)
                if rounded_scale_coef == 1:
                    width_small = width_max = int(common.bit_round(width_orig, -1))
                    height_small = height_max = int(common.bit_round(height_orig, -1))

        gop_size = int(round(self._gop_size * fps))

        commandline = [
            "ffmpeg",
            "-i", input_file,
            "-map", "0:v",
            "-map", "0:v",
            "-map", "0:a?",
            "-s:v:0", f"{width_max}x{height_max}",
            "-s:v:1", f"{width_small}x{height_small}",
            "-pix_fmt:0", self._target_pixel_format,
            "-pix_fmt:1", "yuv420p",
            "-c:v:0", self._target_encoder,
            "-cpu-used", "4",
            "-b:v:0", "0",
            "-crf:0", str(self._crf),
            "-crf:1", str(self._crf - config.dash_low_tier_crf_gap),
            "-c:v:1", "libx264",
            '-threads', str(config.dash_encoding_threads),
            "-preset:v:1", "veryslow",
            "-keyint_min", str(gop_size),
            "-g", str(gop_size),
            "-sc_threshold", "0",
            "-c:a", "copy",
            "-dash_segment_type", "mp4",
            "-seg_duration", "10",
            "-media_seg_name", '{}-chunk-$RepresentationID$-$Number%05d$.$ext$'.format(output_file.name),
            "-init_seg_name", '{}-init-$RepresentationID$.$ext$'.format(output_file.name),
            "-adaptation_sets", "id=0,streams=v id=1,streams=a",
            "-f", "dash"]
        output_file = output_file.with_suffix(".mpd")
        commandline += [
            output_file
        ]
        subprocess.call(
            commandline
        )
        return output_file


class DASHLoopEncoder(DASHEncoder):
    def __init__(self, crf: int):
        super().__init__(crf, 0.5, "yuv444p10le", "libaom-av1")


class DashVideoEncoder(DASHEncoder):
    def __init__(self, crf: int):
        super().__init__(crf, 2, "yuv420p10le", "libaom-av1")

