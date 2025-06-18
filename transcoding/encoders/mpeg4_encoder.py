import pathlib
import tempfile

from ... import config
from ...common import run_subprocess, ffmpeg, videoprocessing

from .encoder import SingleFileEncoder


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

    def encode(self, quality, output_file_path: pathlib.Path) -> bytes:
        tmp_input = None
        if isinstance(self.source, (pathlib.Path, str)):
            input_file = str(self.source)
        else:
            tmp_input = tempfile.NamedTemporaryFile()
            tmp_input.write(self.source)
            input_file = tmp_input.name
        outfile_path = output_file_path.with_suffix(self.SUFFIX)
        commandline = [
                'ffmpeg'
        ]
        if config.allow_rewrite:
            commandline += ['-y']
        vfilters = ""
        if self.downscale is not None:
            vfilters = f"scale={self.downscale[0]}:{self.downscale[1]}"
        else:
            vfilters = "scale=trunc(iw/2)*2:trunc(ih/2)*2"
        if self.vfr:
            vfilters += ",fps=60"
        commandline += [
            "-loglevel", "warning",
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
        run_subprocess(commandline)
        if tmp_input is not None:
            tmp_input.close()
        return outfile_path


class GifProcessingWrapper(X264Encoder):
    def __init__(
        self,
        source: bytearray | pathlib.Path,
    ):
        tmp_input = None
        if isinstance(source, (pathlib.Path, str)):
            input_file = source
        else:
            tmp_input = tempfile.NamedTemporaryFile()
            tmp_input.write(source)
            input_file = tmp_input.name

        src_metadata = ffmpeg.probe(input_file)
        video = ffmpeg.parser.find_video_stream(src_metadata)
        estimate_duration, is_vfr = \
            ffmpeg.parser.check_variate_frame_rate_and_estimate_durarion(
                input_file
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

        if tmp_input is not None:
            tmp_input.close()
        super().__init__(
            source,
            (scaled_width, scaled_height),
            gop_size,
            variable_frame_rate=is_vfr
        )
