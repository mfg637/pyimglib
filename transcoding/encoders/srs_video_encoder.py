from fractions import Fraction
import logging
import pathlib
import json
import dataclasses
import random
import string
from typing import Union
from ... import common, config
from . import srs_base
from pyimglib.ACLMMP import specification as srs_spec

import abc


logger = logging.getLogger(__name__)


class StreamCopy:
    pass


CodecType = Union[
    srs_spec.video.VideoCodecs, srs_spec.audio.AudioCodecs, StreamCopy
]
ContainerType = Union[
    srs_spec.video.VideoContainers, srs_spec.audio.AudioContainers
]


@dataclasses.dataclass
class Metadata:
    video_stream: dict
    audio_streams: list[dict]


@dataclasses.dataclass(frozen=True)
class StreamSpecification:
    compatibility_level: int
    stream_index: int
    fps: float | Fraction | int | None
    size: tuple[int, int] | None
    codec: CodecType
    crf: int | None
    bitrate: float | int | None
    file_name: pathlib.Path
    container_format: ContainerType
    source_audio_channels: int = 0


@dataclasses.dataclass
class MediaSpecification:
    video_streams: list[StreamSpecification]
    audio_streams: list[StreamSpecification]


class VideoSpecificationBuildStrategy(abc.ABC):
    @abc.abstractmethod
    def build(
        self,
        video_size,
        levels_group,
        level,
        metadata,
        output_fps,
        output_file,
        crf
    ):
        pass


class VideoTranscodingSpecificationBuilder(VideoSpecificationBuildStrategy):
    def build(
        self,
        video_size,
        levels_group,
        level,
        metadata,
        output_fps,
        output_file,
        crf
    ):
        width, height, min_size, max_size = video_size
        cl_size = None
        if (
            min_size > levels_group[level][2] or
            max_size > levels_group[level][1]
        ):
            cl_size = common.videoprocessing.scale_down(
                (width, height),
                (levels_group[level][2], levels_group[level][1])
            )
        container = srs_spec.video.VIDEO_CODEC_PREFERED_CONTAINER[
            levels_group[level][0]
        ]
        output_file = output_file.with_stem(
            f"{output_file.stem}_cl{level}"
        ).with_suffix(container[1])
        return StreamSpecification(
            level,
            metadata.video_stream["index"],
            output_fps,
            cl_size,
            levels_group[level][0],
            crf,
            None,
            output_file,
            container[0]
        )


class VideoDemuxSpecificationBuilder(VideoSpecificationBuildStrategy):
    def build(
        self,
        video_size,
        levels_group,
        level,
        metadata,
        output_fps,
        output_file,
        crf
    ):
        input_codec = metadata.video_stream["codec_name"]
        container = srs_spec.video.VIDEO_CODEC_PREFERED_CONTAINER[
            srs_spec.video.codec_name_to_enum(input_codec)
        ]
        output_file = output_file.with_stem(
            f"{output_file.stem}_cl{level}"
        ).with_suffix(container[1])
        return StreamSpecification(
            level,
            metadata.video_stream["index"],
            None,
            None,
            StreamCopy(),
            None,
            None,
            output_file,
            container[0]
        )


class AudioSpecificationBuilder():
    def build(
        self,
        audio_stream,
        output_file
    ):
        input_codec = srs_spec.video.codec_name_to_enum(
            audio_stream["codec_name"]
        )
        track_index = audio_stream["index"]
        audio_channels = audio_stream["channels"]
        if input_codec in srs_spec.audio.AUDIO_CODEC_LEVEL:
            level = srs_spec.audio.AUDIO_CODEC_LEVEL[input_codec]
            container = srs_spec.audio.AUDIO_CODEC_PREFERED_CONTAINER[
                input_codec
            ]
            output_codec = StreamCopy()
            audio_bitrate = None
        else:
            output_codec = srs_spec.audio.AudioCodecs.Opus
            level = 3
            container = srs_spec.audio.AUDIO_CODEC_PREFERED_CONTAINER[
                output_codec
            ]
            audio_bitrate = 96_000

        output_file = output_file.with_stem(
            f"{output_file.stem}_track{track_index}_cl{level}"
        ).with_suffix(container[1])
        return StreamSpecification(
            level,
            track_index,
            None,
            None,
            output_codec,
            None,
            audio_bitrate,
            output_file,
            container[0],
            audio_channels
        )


class TranscodingStrategy(abc.ABC):
    @abc.abstractmethod
    def transcode(
        self,
        input_file: pathlib.Path,
        metadata: Metadata,
        stream: StreamSpecification,
        rewrite: bool
    ):
        pass


class StreamCopying(TranscodingStrategy):
    def transcode(self, input_file, metadata, stream, rewrite):
        commandline = ["ffmpeg"]
        if rewrite:
            commandline += ["-y"]
        commandline += [
            "-i", str(input_file),
            "-map", f"0:{stream.stream_index}",
            "-c", "copy",
            str(stream.file_name)
        ]
        logger.debug(f"commandline: {commandline.__repr__()}")
        transcoding_result = common.utils.run_subprocess(commandline)
        transcoding_result.check_returncode()


class BasicVideoTranscode(TranscodingStrategy):
    def get_fps(self, stream: StreamSpecification, metadata: Metadata):
        input_fps = common.ffmpeg.parser.get_fps(metadata.video_stream)
        if stream.fps is not None:
            output_fps = stream.fps
        else:
            output_fps = input_fps
        return output_fps

    def vfilters(self, stream: StreamSpecification) -> str | None:
        vfilters = ""
        if stream.size is not None:
            vfilters += f"scale={stream.size[0]}:{stream.size[1]}"
        if stream.fps is not None:
            if vfilters:
                vfilters += ","
            vfilters += f"fps={stream.fps}"
        if vfilters:
            return vfilters
        else:
            return None

    def generate_commandline(
        self,
        input_file,
        stream: StreamSpecification,
        rewrite,
        vfilters,
        output_fps,
        codec_commandline,
        encoding_pass: int | None,
        pass_log_file: str | None,
        zero_bitrate: bool = False
    ) -> list[str]:
        output_file = str(stream.file_name)
        _format = None
        if (
            encoding_pass is not None and
            pass_log_file is not None and
            encoding_pass == 1
        ):
            output_file = "/dev/null"
            rewrite = True
            _format = srs_spec.video.FFMPEG_VIDEO_CONTAINER_FORMAT[
                srs_spec.video.VIDEO_CODEC_PREFERED_CONTAINER[stream.codec][0]
            ]
        commandline = ["ffmpeg"]
        if rewrite:
            commandline += ["-y"]
        commandline += ["-i", str(input_file)]
        if vfilters is not None:
            commandline += [
                "-vf", f"[0:{stream.stream_index}]" + vfilters
            ]
        else:
            commandline += ["-map", f"0:{stream.stream_index}"]
        commandline += codec_commandline
        if stream.crf is not None:
            commandline += ["-crf", str(stream.crf)]
        if stream.bitrate is not None:
            commandline += ["-b:v", str(stream.bitrate)]
        elif zero_bitrate:
            commandline += ["-b:v", "0"]
        if encoding_pass is not None and pass_log_file is not None:
            commandline += [
                "-pass", str(encoding_pass),
                "-passlogfile", str(
                    pathlib.Path('/tmp').joinpath(pass_log_file)
                ),
            ]
            if _format is not None:
                commandline += ["-f", _format]
        commandline += [
            "-g", str(int(output_fps * config.gop_length_seconds)),
            output_file
        ]
        return commandline

    def generate_logfilename(self):
        sequence = string.ascii_letters + string.digits
        return "".join(random.choices(sequence, k=12))


class X264VideoTranscode(BasicVideoTranscode):
    def transcode(self, input_file, metadata, stream, rewrite):
        output_fps = self.get_fps(stream, metadata)
        vfilters = self.vfilters(stream)

        codec_commandline = [
            "-c:v", "libx264",
            "-preset", "veryslow"
        ]

        if stream.bitrate is not None:
            pass_log_file = self.generate_logfilename()
            commandline = self.generate_commandline(
                input_file,
                stream,
                rewrite,
                vfilters,
                output_fps,
                codec_commandline,
                1,
                pass_log_file
            )
            logger.debug(f"1 pass commandline: {commandline.__repr__()}")
            transcoding_result = common.utils.run_subprocess(commandline)
            transcoding_result.check_returncode()
            commandline = self.generate_commandline(
                input_file,
                stream,
                rewrite,
                vfilters,
                output_fps,
                codec_commandline,
                2,
                pass_log_file
            )
            logger.debug(f"2 pass commandline: {commandline.__repr__()}")
            transcoding_result = common.utils.run_subprocess(commandline)
            transcoding_result.check_returncode()
        else:
            commandline = self.generate_commandline(
                input_file,
                stream,
                rewrite,
                vfilters,
                output_fps,
                codec_commandline,
                None,
                None
            )
            logger.debug(f"commandline: {commandline.__repr__()}")
            transcoding_result = common.utils.run_subprocess(commandline)
            transcoding_result.check_returncode()


class SVTAV1VideoTranscode(BasicVideoTranscode):
    def transcode(self, input_file, metadata, stream, rewrite):
        output_fps = self.get_fps(stream, metadata)
        vfilters = self.vfilters(stream)

        codec_commandline = [
            "-c:v", "libsvtav1",
            "-preset", "2"
        ]

        if stream.bitrate is not None:
            pass_log_file = self.generate_logfilename()
            commandline = self.generate_commandline(
                input_file,
                stream,
                rewrite,
                vfilters,
                output_fps,
                codec_commandline,
                1,
                pass_log_file
            )
            logger.debug(f"1 pass commandline: {commandline.__repr__()}")
            transcoding_result = common.utils.run_subprocess(commandline)
            transcoding_result.check_returncode()
            commandline = self.generate_commandline(
                input_file,
                stream,
                rewrite,
                vfilters,
                output_fps,
                codec_commandline,
                2,
                pass_log_file
            )
            logger.debug(f"2 pass commandline: {commandline.__repr__()}")
            transcoding_result = common.utils.run_subprocess(commandline)
            transcoding_result.check_returncode()
        else:
            commandline = self.generate_commandline(
                input_file,
                stream,
                rewrite,
                vfilters,
                output_fps,
                codec_commandline,
                None,
                None
            )
            logger.debug(f"commandline: {commandline.__repr__()}")
            transcoding_result = common.utils.run_subprocess(commandline)
            transcoding_result.check_returncode()


class VP9VideoTranscode(BasicVideoTranscode):
    def transcode(self, input_file, metadata, stream, rewrite):
        output_fps = self.get_fps(stream, metadata)
        vfilters = self.vfilters(stream)

        codec_commandline = [
            "-c:v", "libvpx-vp9",
            "-preset", "1"
        ]

        pass_log_file = self.generate_logfilename()
        commandline = self.generate_commandline(
            input_file,
            stream,
            rewrite,
            vfilters,
            output_fps,
            codec_commandline,
            1,
            pass_log_file,
            True
        )
        logger.debug(f"1 pass commandline: {commandline.__repr__()}")
        transcoding_result = common.utils.run_subprocess(commandline)
        transcoding_result.check_returncode()
        commandline = self.generate_commandline(
            input_file,
            stream,
            rewrite,
            vfilters,
            output_fps,
            codec_commandline,
            2,
            pass_log_file,
            True
        )
        logger.debug(f"2 pass commandline: {commandline.__repr__()}")
        transcoding_result = common.utils.run_subprocess(commandline)
        transcoding_result.check_returncode()


class OpusAudioTranscode(TranscodingStrategy):
    def transcode(self, input_file, metadata, stream, rewrite):
        current_audio_metadata = None
        for audio_stream_metadata in metadata.audio_streams:
            if audio_stream_metadata["index"] == stream.stream_index:
                current_audio_metadata = audio_stream_metadata
        audio_channels = current_audio_metadata["channels"]
        commandline = ["ffmpeg"]
        if rewrite:
            commandline += ["-y"]
        commandline += [
            "-i", str(input_file),
            "-map", f"0:{stream.stream_index}",
        ]
        if audio_channels > 2:
            commandline += ["-ac", "2"]
        commandline += [
            "-c:a", "libopus",
            "-b:a", str(stream.bitrate),
            str(stream.file_name)
        ]
        logger.debug(f"commandline: {commandline.__repr__()}")
        transcoding_result = common.utils.run_subprocess(commandline)
        transcoding_result.check_returncode()


class SrsVideoEncoder(srs_base.SrsEncoderBase):
    def __init__(self, crf):
        self.crf = crf

    def parse(self, input_file: pathlib.Path) -> Metadata:
        src_metadata = common.ffmpeg.probe(input_file)
        video = common.ffmpeg.parser.find_video_stream(src_metadata)
        audio_streams = common.ffmpeg.parser.find_audio_streams(src_metadata)
        return Metadata(video, audio_streams)

    def detect_compatibility_level(self, video_stream):
        check_levels = [3, 2, 1]
        for level in check_levels:
            if common.ffmpeg.parser.test_video_cl(level, video_stream):
                return level
        return 0

    def schedule(
        self, metadata: Metadata, output_file: pathlib.Path
    ) -> MediaSpecification:
        input_fps = common.ffmpeg.parser.get_fps(metadata.video_stream)
        video_size = \
            common.ffmpeg.parser.get_video_size(metadata.video_stream)
        source_compatibility_level = self.detect_compatibility_level(
            metadata.video_stream
        )
        levels_group = srs_spec.video.LEVELS_30FPS
        if input_fps > 30:
            levels_group = srs_spec.video.LEVELS_60FPS
        output_fps = None
        if input_fps > 60:
            output_fps = 60
        output_video_streams = []
        output_audio_streams = []
        compatibility_levels = [1, 2, 3]
        for level in compatibility_levels:
            if source_compatibility_level < level:
                build_strategy = VideoTranscodingSpecificationBuilder()
            elif source_compatibility_level == level:
                build_strategy = VideoDemuxSpecificationBuilder()
            else:
                continue
            output_video_streams.append(
                build_strategy.build(
                    video_size,
                    levels_group,
                    level,
                    metadata,
                    output_fps,
                    output_file,
                    self.crf
                )
            )
        audio_stream_builder = AudioSpecificationBuilder()
        for audio_stream in metadata.audio_streams:
            output_audio_streams.append(
                audio_stream_builder.build(audio_stream, output_file)
            )
        return MediaSpecification(output_video_streams, output_audio_streams)

    def deduplicate_video_streams(
        self, specification: MediaSpecification
    ) -> MediaSpecification:
        cl1_video: StreamSpecification | None = None
        cl2_video: StreamSpecification | None = None
        cl3_video: StreamSpecification | None = None
        for video in specification.video_streams:
            if video.compatibility_level == 1:
                cl1_video = video
            elif video.compatibility_level == 2:
                cl2_video = video
            elif video.compatibility_level == 3:
                cl3_video = video
        if cl3_video is None:
            raise ValueError("Not found video with compatibility level 3")
        if cl1_video is not None and cl2_video is not None:
            if cl1_video.size is None and cl2_video.size is None:
                cl1_video = None
            elif cl1_video.size is not None and cl2_video.size is not None:
                if cl1_video.size == cl2_video.size:
                    cl1_video = None
        if cl2_video is not None:
            if cl2_video.size is None and cl3_video.size is None:
                cl2_video = None
            elif cl2_video.size is not None and cl3_video.size is not None:
                if cl2_video.size == cl3_video.size:
                    cl2_video = None
        video_streams = []
        if cl1_video is not None:
            video_streams.append(cl1_video)
        if cl2_video is not None:
            video_streams.append(cl2_video)
        video_streams.append(cl3_video)
        return MediaSpecification(
            video_streams,
            specification.audio_streams
        )

    def transcode_source(
        self,
        input_file: pathlib.Path,
        specification: MediaSpecification,
        metadata: Metadata
    ):
        for video in specification.video_streams:
            if isinstance(video.codec, StreamCopy):
                transcoder = StreamCopying()
            elif isinstance(video.codec, srs_spec.video.VideoCodecs):
                if video.codec == srs_spec.video.VideoCodecs.H264:
                    transcoder = X264VideoTranscode()
                elif video.codec == srs_spec.video.VideoCodecs.VP9:
                    transcoder = VP9VideoTranscode()
                elif video.codec == srs_spec.video.VideoCodecs.AV1:
                    transcoder = SVTAV1VideoTranscode()
                else:
                    raise NotImplementedError(
                        f"No transcoding for codec {video.codec}"
                    )
            else:
                raise TypeError((
                    "incorrect video codec type "
                    f"{type(video.codec)} ({video.codec})"
                ))
            transcoder.transcode(input_file, metadata, video, True)

        for audio in specification.audio_streams:
            if isinstance(audio.codec, StreamCopy):
                transcoder = StreamCopying()
            else:
                transcoder = OpusAudioTranscode()
            transcoder.transcode(input_file, metadata, audio, True)

    def write_srs(
        self, specification: MediaSpecification, output_file: pathlib.Path
    ) -> pathlib.Path:
        if len(specification.audio_streams):
            srs_data = {
                "ftype": "CLSRS",
                "content": {
                    "media-type": 2,
                    "attachment": dict(),
                },
                "streams": {
                    "video": {"levels": dict()},
                    "audio": list()
                }
            }
        else:
            srs_data = {
                "ftype": "CLSRS",
                "content": {
                    "media-type": 3,
                    "attachment": dict(),
                },
                "streams": {
                    "video": {"levels": dict()}
                }
            }
        video_levels: dict[int, str] = dict()
        for video in specification.video_streams:
            video_levels[str(video.compatibility_level)] = video.file_name.name
        srs_data["streams"]["video"]["levels"] = video_levels
        if len(specification.audio_streams):
            audio_levels_list: list[dict[str, dict[str, str]]] = []
            for audio_stream in specification.audio_streams:
                audio_levels_list.append(
                    {"channels": {
                        str(audio_stream.source_audio_channels): {
                            str(audio_stream.compatibility_level):
                                audio_stream.file_name.name
                        }
                    }}
                )
            srs_data["streams"]["audio"] = audio_levels_list

        srs_output_file = output_file.with_suffix(".srs")
        self.srs_file_path = srs_output_file

        with srs_output_file.open("w") as srs_file:
            json.dump(srs_data, srs_file)

        return srs_output_file

    def encode(
        self, input_file: pathlib.Path, output_file: pathlib.Path
    ) -> pathlib.Path:
        metadata = self.parse(input_file)
        logger.debug(f"extracted metadata: {metadata.__repr__()}")
        specification = self.schedule(metadata, output_file)
        logger.debug(f"generated specification: {specification.__repr__()}")
        specification = self.deduplicate_video_streams(specification)
        logger.debug(f"filtered specification: {specification.__repr__()}")
        self.transcode_source(input_file, specification, metadata)
        return self.write_srs(specification, output_file)
