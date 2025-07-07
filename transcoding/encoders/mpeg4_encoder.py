import logging
import pathlib
import tempfile

from ... import config
from ...common import run_subprocess, ffmpeg, videoprocessing, utils

from .encoder import SingleFileEncoder


logger = logging.getLogger(__name__)


class X264Encoder(SingleFileEncoder):
    SUFFIX = ".mp4"

    def __init__(
        self,
        source: bytearray | pathlib.Path,
        downscale: tuple[int, int] | None,
        gop_size: int,
        variable_frame_rate: bool
    ):
        SingleFileEncoder.__init__(self, self.SUFFIX)
        self.downscale = downscale
        self.vfr = variable_frame_rate
        self.source: bytearray | pathlib.Path = source
        self.gop_size = gop_size

    def encode(
        self, quality, output_file_path: pathlib.Path, rewrite: bool
    ) -> pathlib.Path:
        source_handler = utils.InputSourceFacade(self.source)
        input_file = source_handler.get_file_str()
        outfile_path = output_file_path.with_suffix(self.SUFFIX)
        commandline = [
                'ffmpeg'
        ]
        if config.allow_rewrite or rewrite:
            commandline += ['-y']
        vfilters = ""
        if self.downscale is not None:
            vfilters = f"[0:v:0]scale={self.downscale[0]}:{self.downscale[1]}[v]"
        else:
            vfilters = "[0:v:0]scale=trunc(iw/2)*2:trunc(ih/2)*2[v]"
        if self.vfr:
            vfilters += ",[v]fps=60[v]"
        vfilters += (
            f",color=c=white:s={self.downscale[0]}x{self.downscale[1]}[bg],"
            "[bg][v]overlay=shortest=1:format=yuv420"
        )
        commandline += [
            #"-loglevel", "warning",
            "-i", input_file,
            "-movflags", "+faststart",
            "-vf", vfilters,
            "-pix_fmt", "yuv420p",
            "-c:v", "libx264",
            "-crf", str(quality),
            "-preset", "slow",
            "-threads", str(config.encoding_threads),
            "-g", str(self.gop_size),
            "-keyint_min", str(self.gop_size),
            "-sc_threshold", "0",
            str(outfile_path)
        ]
        logger.debug(f"commandline: {commandline}")
        run_subprocess(commandline)
        source_handler.close()
        return outfile_path


def prepare_arguments(
    source: bytearray | pathlib.Path
) -> tuple[tuple[int, int], int, bool]:
    src_metadata = ffmpeg.probe(source)
    video = ffmpeg.parser.find_video_stream(src_metadata)
    estimate_duration, is_vfr = \
        ffmpeg.parser.check_variate_frame_rate_and_estimate_durarion(
            source
        )

    width_orig = video["width"]
    height_orig = video["height"]

    scaled_width, scaled_height, scale_coef = videoprocessing.scale_down(
        (width_orig, height_orig), (1080, 1920)
    )

    if is_vfr:
        gop_size = 120  # 60 * 2
    else:
        gop_size = int(round(ffmpeg.parser.get_fps(video))) * 2

    return (scaled_width, scaled_height), gop_size, is_vfr


class GifProcessingWrapper(X264Encoder):
    def __init__(
        self,
        source: bytearray | pathlib.Path,
    ):
        scaled_size, gop_size, is_vfr = prepare_arguments(source)

        super().__init__(
            source,
            scaled_size,
            gop_size,
            variable_frame_rate=is_vfr
        )


def make_x264_vloop_encoder(source: bytearray | pathlib.Path):
    scaled_size, gop_size, is_vfr = prepare_arguments(source)
    return X264Encoder(source, scaled_size, gop_size, is_vfr)
