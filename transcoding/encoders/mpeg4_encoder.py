import pathlib
import tempfile

from ... import config
from ...common import run_subprocess, ffmpeg

from .encoder import SingleFileEncoder


class X264Encoder(SingleFileEncoder):
    SUFFIX = ".mp4"

    def __init__(
        self,
        source: bytearray | pathlib.Path,
        downscale: tuple[int, int] | None,
        variable_frame_rate: bool
    ):
        SingleFileEncoder.__init__(self, self.SUFFIX)
        self.downscale = downscale
        self.vfr = variable_frame_rate
        self.source: bytearray | pathlib.Path = source

    def encode(self, quality, output_file_path: pathlib.Path) -> bytes:
        print("prepare to encoding…")
        tmp_input = None
        if isinstance(self.source, (pathlib.Path, str)):
            input_file = self.source
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
        #    '-loglevel', 'warning',
            '-i', input_file,
            '-movflags', '+faststart',
            '-vf', vfilters,
            '-pix_fmt', "yuv420p",
            '-c:v', "libx264",
            '-crf', str(quality),
            '-threads', str(config.encoding_threads),
            str(outfile_path)
        ]
        print("COMMANDLINE", commandline)
        run_subprocess(commandline)
        if tmp_input is not None:
            tmp_input.close()
        return outfile_path


class GifProcessingWrapper(X264Encoder):
    def __init__(
        self,
        source: bytearray | pathlib.Path,
    ):
        estimate_duration, is_vfr = \
            ffmpeg.parser.check_variate_frame_rate_and_estimate_durarion(
                source
            )
        super().__init__(source, None, variable_frame_rate=is_vfr)
