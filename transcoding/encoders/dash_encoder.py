import io
import json
import logging
import pathlib
import random
import shlex
import string
import subprocess
import re
import tempfile
from typing import Iterable, Final

from .encoder import FilesEncoder
from .. import common
from ...decoders import ffmpeg
from ... import config

import xml.dom.minidom

file_template_regex = re.compile("\$[\da-zA-Z\-%]+\$")

logger = logging.getLogger(__name__)


class DASHEncoder(FilesEncoder):
    def __init__(self, crf: int, gop_size, pix_fmt):
        self._crf = crf
        self._target_pixel_format = pix_fmt
        self._gop_size = gop_size
        self.mpd_manifest_file: pathlib.Path | None = None

    def set_manifest_file(self, manifest_file: pathlib.Path):
        self.mpd_manifest_file = manifest_file

    @staticmethod
    def calc_size(width_orig, height_orig, min_size, size_precision = -1):
        width_max = 2
        height_max = 2
        width_small = 2
        height_small = 2
        scale_coef = 1

        def get_rounded_size(width_small, height_small, scale_coef):
            def scale_size(width, height, scale):
                scaled_width = int(round(width * scale))
                scaled_height = int(round(height * scale))
                return scaled_width, scaled_height

            scale_precission = 6
            rounded_scale_coef = scale_coef
            width_max, height_max = scale_size(width_small, height_small, rounded_scale_coef)
            ar_scaled = width_max / height_max
            while ar_scaled != aspect_ratio:
                scale_precission -= 1
                rounded_scale_coef = common.bit_round(scale_coef, scale_precission)
                logger.debug("scale precission = {}, scale_coef = {}".format(scale_precission, rounded_scale_coef))
                width_max, height_max = scale_size(width_small, height_small, rounded_scale_coef)
                ar_scaled = width_max / height_max
            return width_max, height_max, rounded_scale_coef

        if height_orig <= width_orig:
            logging.debug("width > height or width = height")
            if height_orig <= min_size:
                width_small = width_max = int(common.bit_round(width_orig, size_precision))
                height_small = height_max = int(common.bit_round(height_orig, size_precision))
            else:
                height_small = min_size
                scale_coef = height_orig / min_size
                width_small = int(common.bit_round(width_orig / scale_coef, size_precision))
        elif height_orig > width_orig:
            logging.debug("height > width")
            if width_orig <= min_size:
                width_small = width_max = int(common.bit_round(width_orig, size_precision))
                height_small = height_max = int(common.bit_round(height_orig, size_precision))
            else:
                width_small = min_size
                scale_coef = width_orig / min_size
                height_small = common.bit_round(height_orig / scale_coef, size_precision)

        logger.debug("width small = {}, height small = {}".format(width_small, height_small))

        if width_small != width_max or height_small != height_max:
            aspect_ratio = width_small / height_small
            width_max, height_max, rounded_scale_coef = get_rounded_size(width_small, height_small, scale_coef)
            if rounded_scale_coef == 1:
                width_small = width_max = int(common.bit_round(width_orig, size_precision))
                height_small = height_max = int(common.bit_round(height_orig, size_precision))
        return width_small, height_small, width_max, height_max

    def get_files(self):
        if self.mpd_manifest_file is None:
            return []

        list_files = []

        file_templates = set()
        parent_dir = self.mpd_manifest_file.parent
        try:
            mpd_document: xml.dom.minidom.Document = xml.dom.minidom.parse(str(self.mpd_manifest_file))
        except xml.parsers.expat.ExpatError:
            return []
        segment_templates: Iterable[xml.dom.minidom.Element] = mpd_document.getElementsByTagName("SegmentTemplate")
        for template in segment_templates:
            file_templates.add(file_template_regex.sub("*", template.getAttribute("initialization")))
            file_templates.add(file_template_regex.sub("*", template.getAttribute("media")))
        logger.debug(file_templates.__repr__())

        file_templates_iterable: tuple[str] = tuple(file_templates)
        for file_template in file_templates_iterable:
            for file in parent_dir.glob(file_template):
                if file.is_file():
                    list_files.append(file)

        list_files.append(self.mpd_manifest_file)
        return list_files

    def calc_encoding_params(self, input_file: pathlib.Path, strict=False, size_precision = -1):
        src_metadata = ffmpeg.probe(input_file)
        video = ffmpeg.parser.find_video_stream(src_metadata)
        fps = ffmpeg.parser.get_fps(video)

        limited_min_size = 720
        lt_gap = config.dash_low_tier_crf_gap
        max_lt_fps = 31
        if strict:
            max_lt_fps = 30
        if fps > max_lt_fps:
            lt_gap = max(int(lt_gap / 2), 1)
            limited_min_size = 360

        width_orig = video["width"]
        height_orig = video["height"]

        crf = self._crf

        def calc_crf(min_size, crf, lt_gap):
            tier = 0
            while height_orig < config.tiers_min_size[tier]:
                tier += 1
                crf -= lt_gap
            return crf

        if height_orig <= width_orig:
            crf = calc_crf(height_orig, crf, lt_gap)
        elif height_orig > width_orig:
            crf = calc_crf(width_orig, crf, lt_gap)

        width_small, height_small, width_max, height_max = DASHEncoder.calc_size(
            width_orig, height_orig, limited_min_size, size_precision
        )

        gop_size = int(round(self._gop_size * fps))
        return width_max, height_max, width_small, height_small, gop_size, crf, lt_gap, fps


class DASHLoopEncoder(DASHEncoder):
    def __init__(self, crf: int):
        super().__init__(crf, 2, "yuva420p")

    def encode(self, input_file: pathlib.Path, output_file: pathlib.Path) -> pathlib.Path:
        width_max, height_max, width_small, height_small, gop_size, crf, lt_gap, fps = \
            self.calc_encoding_params(input_file, strict=True, size_precision=0)

        commandline = [
            "ffmpeg",
            "-i", input_file,
            "-filter_complex",
            f"[0]scale={width_max}x{height_max}[v1],[0]scale={width_small}x{height_small}[v2],[v1]setsar=1[v1],[v2]setsar=1[v2]",
            "-map", "[v1]",
            "-map", "[v2]",
            "-pix_fmt:0", "yuva420p10le",
            "-pix_fmt:1", "yuva420p",
            "-c:v:0", "libaom-av1",
            "-cpu-used", str(config.av1_cpu_usage),
            "-b:v:0", "0",
            "-crf:0", str(crf - lt_gap),
            "-crf:1", str(crf + lt_gap * 2),
            "-c:v:1", "libvpx-vp9",
            '-threads', str(config.dash_encoding_threads),
            "-keyint_min", str(gop_size),
            "-g", str(gop_size),
            "-sc_threshold", "0",
            "-c:a", "copy",
            "-dash_segment_type", "webm",
            "-seg_duration", str(self._gop_size),
            "-media_seg_name", '{}-chunk-$RepresentationID$-$Number%05d$.$ext$'.format(output_file.name),
            "-init_seg_name", '{}-init-$RepresentationID$.$ext$'.format(output_file.name),
            "-adaptation_sets", "id=0,streams=v id=1,streams=a",
            "-f", "dash"
        ]
        output_file = output_file.with_suffix(".mpd")
        commandline += [
            output_file
        ]
        if config.show_output_in_console:
            subprocess.run(commandline)
        else:
            common.run_subprocess(commandline)
        self.mpd_manifest_file = output_file
        return output_file


class DashVideoEncoder(DASHEncoder):
    def __init__(self, crf: int):
        super().__init__(crf, 10, "yuv420p10le")
        self.av1an_workers = config.dash_encoding_threads

    @staticmethod
    def get_keyframes(ffprobe_json_output):
        key_frames = []

        frames = json.loads(str(ffprobe_json_output, "utf-8"))["frames"]
        for frame_num, frame in enumerate(frames):
            if frame["key_frame"] == 1:
                key_frames.append(frame_num)

        return key_frames

    def get_av1an_commandline(self, input_file, ht_video_file, gop_size, width_max, height_max, crf, av1an_scenes_file):
        av1an_commandline = "av1an -i \"{}\" -o \"{}\" -v \"--cpu-used={} --kf-max-dist={} --kf-min-dist={} ".format(
            input_file, ht_video_file.name, config.av1_cpu_usage, gop_size, gop_size
        )

        if width_max <= 1920 and height_max <= 1920:
            av1an_commandline += "--sb-size=64 "
        if config.av1an_aomenc_threads >= 2 and 1024 <= width_max <= 1920:
            av1an_commandline += "--tile-columns=1 "

        av1an_commandline += "--threads={} --end-usage=q --cq-level={}".format(
            config.av1an_aomenc_threads, crf
        )
        if config.av1_cpu_usage <= 4:
            av1an_commandline += " --lag-in-frames=48 --enable-qm=1 --enable-fwd-kf=0 --enable-chroma-deltaq=0 --enable-keyframe-filtering=1 --arnr-strength=1"
        av1an_commandline += "\" -w {} -s {} -a=\"-an\" --passes=1".format(
            self.av1an_workers, av1an_scenes_file.name
        )
        av1an_commandline += " --ffmpeg=\"-vf scale={}x{}\" ".format(width_max, height_max)
        if logging.root.level >= logging.ERROR:
            av1an_commandline += " --quiet"
        return shlex.split(av1an_commandline)

    def encode(self, input_file: pathlib.Path, output_file: pathlib.Path) -> pathlib.Path:
        width_max, height_max, width_small, height_small, gop_size, crf, lt_gap, fps = \
            self.calc_encoding_params(input_file)

        lt_video_file = tempfile.NamedTemporaryFile(suffix=".mp4")

        low_tier_transcoding_commandline = [
            "ffmpeg"]
        low_tier_transcoding_commandline += ['-loglevel', 'info']
        low_tier_transcoding_commandline += [
            "-y",
            "-i", input_file,
            "-map", "0:v",
            "-vf", f"scale={width_small}:{height_small},setsar=1",
            "-pix_fmt", "yuv420p",
            "-crf", str(crf),
            "-c:v", "libx264",
            "-level:v:0", "4.1",
            '-threads', str(config.encoding_threads),
            "-preset:v:0", "veryslow",
            "-g", str(gop_size),
            "-keyint_min", str(int(round(fps * 0.5))),
            lt_video_file.name
        ]

        ht_video_file = None
        av1an_scenes_file = None
        commandline = [
            "ffmpeg",
        ]
        commandline += ['-loglevel', 'info']

        av1_rfc_codec_string = None

        common.run_subprocess(low_tier_transcoding_commandline)

        if width_max <= 720 or height_max <= 720:
            commandline += [
                "-i", lt_video_file.name,
                "-i", input_file,
                "-map", "0:v",
                "-map", "1:a:0?",
                "-c:v", "copy"
            ]
        else:
            lt_keyframes_json = subprocess.check_output(
                ["ffprobe"] + ffmpeg.set_loglevel(logging.root.level) + [
                    "-print_format", "json",
                    "-show_frames",
                    "-show_entries", "frame=key_frame",
                    lt_video_file.name
                ]
            )

            scenes = DashVideoEncoder.get_keyframes(lt_keyframes_json)

            logger.info("SCENES: {}".format(", ".join(str(scene) for scene in scenes)))

            orig_keyframes_json = subprocess.check_output(
                ["ffprobe"] + ffmpeg.set_loglevel(logging.root.level) + [
                    "-print_format", "json",
                    "-show_frames",
                    "-show_entries", "frame=stream_index",
                    str(input_file)
                ]
            )

            origin_frames = json.loads(str(orig_keyframes_json, "utf-8"))['frames']
            frames_count = 0
            for frame in origin_frames:
                if frame["stream_index"] == 0:
                    frames_count += 1

            av1an_scenes = {"scenes": scenes, "frames": frames_count}

            ht_video_file = pathlib.Path(
                ''.join(random.choice(string.ascii_lowercase) for i in range(16))
            ).with_suffix(".mkv")

            av1an_scenes_file = pathlib.Path(
                ''.join(random.choice(string.ascii_lowercase) for i in range(16))
            ).with_suffix(".json")
            with av1an_scenes_file.open("w") as f:
                json.dump(av1an_scenes, f)

            av1an_commandline = self.get_av1an_commandline(
                input_file, ht_video_file, gop_size, width_max, height_max, crf, av1an_scenes_file
            )
            logger.debug(av1an_commandline.__repr__())
            subprocess.run(av1an_commandline)

            commandline += [
                "-i", ht_video_file.name,
                "-i", lt_video_file.name,
                "-i", input_file,
                "-map", "0:v",
                "-map", "1:v",
                "-map", "2:a:0?",
                "-c:v", "copy"
            ]
        source_data = ffmpeg.probe(input_file)
        audio = ffmpeg.parser.find_audio_streams(source_data)
        if not config.force_audio_transcode and \
                len(audio) and audio[0]["codec_name"] in {"aac", "vorbis", "opus"} and audio[0]["channels"] <= 2:
            commandline += ["-c:a", "copy"]
        elif len(audio):
            commandline += ["-ac", "2", "-c:a", "libopus", "-b:a", "{}k".format(config.opus_stereo_bitrate_kbps)]
        commandline += [
            "-dash_segment_type", "mp4",
            "-seg_duration", "10",
            "-media_seg_name", '{}-chunk-$RepresentationID$-$Number%05d$.$ext$'.format(output_file.name),
            "-init_seg_name", '{}-init-$RepresentationID$.$ext$'.format(output_file.name),
            "-adaptation_sets", "id=0,streams=v id=1,streams=a",
            "-f", "dash"
        ]
        ht_init = output_file.with_name("{}-init-0.m4s".format(output_file.name))
        output_file = output_file.with_suffix(".mpd")
        commandline += [
            output_file
        ]
        common.run_subprocess(
            commandline
        )
        lt_video_file.close()
        if ht_video_file is not None:
            mp4box_info_process = subprocess.run(["MP4Box", "-info", ht_init], stderr=subprocess.PIPE)
            mp4box_output = io.StringIO(str(mp4box_info_process.stderr, "utf-8"))
            rfc_codec_params_label: Final[str] = "RFC6381 Codec Parameters: "
            for line in mp4box_output:
                if rfc_codec_params_label in line:
                    av1_rfc_codec_string = line.strip()[len(rfc_codec_params_label):]

            ht_video_file.unlink()
        if av1an_scenes_file is not None:
            av1an_scenes_file.unlink()
        if av1_rfc_codec_string is not None:
            mpd_document: xml.dom.minidom.Document = xml.dom.minidom.parse(str(output_file))
            av1_representation_element: xml.dom.minidom.Element = mpd_document.getElementsByTagName("Representation")[0]
            av1_representation_element.setAttribute("codecs", av1_rfc_codec_string)
            with output_file.open(mode="w") as f:
                mpd_document.writexml(f)

        self.mpd_manifest_file = output_file
        return output_file


class SVTAV1DashVideoEncoder(DASHEncoder):
    def __init__(self, crf: int):
        super().__init__(crf, 10, "yuv420p10le")
        self.av1an_workers = config.dash_encoding_threads

    def encode(self, input_file: pathlib.Path, output_file: pathlib.Path) -> pathlib.Path:
        width_max, height_max, width_small, height_small, gop_size, crf, lt_gap, fps = \
            self.calc_encoding_params(input_file)
        if width_max != width_small or height_max != height_small:
            commandline = [
                "ffmpeg",
                "-i", input_file,
                "-filter_complex",
                f"[0]scale={width_max}x{height_max}[v1],[0]scale={width_small}x{height_small}[v2],[v1]setsar=1[v1],[v2]setsar=1[v2]",
                "-map", "[v1]",
                "-map", "[v2]",
                "-map", "0:a?",
                "-pix_fmt:0", "yuv420p10le",
                "-pix_fmt:1", "yuv420p",
                "-c:v:0", "libsvtav1",
                "-cpu-used", str(config.av1_cpu_usage),
                "-b:v:0", "0",
                "-crf:0", str(crf),
                "-crf:1", str(crf),
                "-c:v:1", "libx264",
                "-preset:v:1", "veryslow",
                '-threads', str(config.dash_encoding_threads),
                "-keyint_min", str(gop_size),
                "-g", str(gop_size),
                "-sc_threshold", "0",
                "-c:a", "copy",
                "-dash_segment_type", "auto",
                "-seg_duration", str(self._gop_size),
                "-media_seg_name", '{}-chunk-$RepresentationID$-$Number%05d$.$ext$'.format(output_file.name),
                "-init_seg_name", '{}-init-$RepresentationID$.$ext$'.format(output_file.name),
                "-adaptation_sets", "id=0,streams=v id=1,streams=a",
                "-f", "dash"
            ]
        else:
            commandline = [
                "ffmpeg",
                "-i", input_file,
                "-filter_complex",
                f"[0]scale={width_max}x{height_max}[v1]",
                "-map", "[v1]",
                "-map", "0:a?",
                "-pix_fmt", "yuv420p",
                "-crf", str(crf),
                "-c:v", "libx264",
                "-preset:v", "veryslow",
                '-threads', str(config.dash_encoding_threads),
                "-g", str(gop_size),
                "-c:a", "copy",
                "-dash_segment_type", "auto",
                "-seg_duration", str(self._gop_size),
                "-media_seg_name", '{}-chunk-$RepresentationID$-$Number%05d$.$ext$'.format(output_file.name),
                "-init_seg_name", '{}-init-$RepresentationID$.$ext$'.format(output_file.name),
                "-adaptation_sets", "id=0,streams=v id=1,streams=a",
                "-f", "dash"
            ]
        output_file = output_file.with_suffix(".mpd")
        commandline += [
            output_file
        ]
        if config.show_output_in_console:
            subprocess.run(commandline)
        else:
            common.run_subprocess(commandline)
        self.mpd_manifest_file = output_file
        return output_file

