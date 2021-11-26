import subprocess
import tempfile
import os
import pathlib
from ..decoders import ffmpeg
from .. import config
from . import webm_transcoder
from .common import videoprocessing, srs
from abc import ABC


class SrsVideoLoopOutput(webm_transcoder.WEBM_VideoOutputFormat, ABC):
    def __init__(self, source, path, file_name, item_data, metadata):
        webm_transcoder.WEBM_VideoOutputFormat.__init__(self, source, path, file_name, item_data)
        self._cl3w_filename = self._output_file + '_cl3w.webm'
        self._content_metadata = metadata

    def animation2webm_cl3w(self):
        fname = ""
        f = None
        if type(self._source) is str:
            fname = self._source
        elif isinstance(self._source, (bytes, bytearray)):
            f = tempfile.NamedTemporaryFile()
            fname = f.name
            f.write(self._source)
        src_metadata = ffmpeg.probe(fname)
        video = ffmpeg.parser.find_video_stream(src_metadata)
        fps = ffmpeg.parser.get_fps(video)
        fps, src_fps_valid = videoprocessing.limit_fps(fps)
        commandline = [
            'ffmpeg']
        if config.allow_rewrite:
            commandline += ['-y']
        commandline += [
            '-loglevel', 'error',
            '-i', fname,
            '-pix_fmt', 'yuv420p'
        ]
        if not src_fps_valid:
            commandline += videoprocessing.ffmpeg_set_fps_commandline(fps)
        if not videoprocessing.cl3_size_valid(video):
            commandline += videoprocessing.CL3_FFMPEG_SCALE_COMMANDLINE
        commandline += [
            '-c:v', 'libvpx-vp9',
            '-crf', str(config.VIDEOLOOP_CRF),
            '-b:v', '0',
            '-profile:v', '0',
            '-cpu-used', '4',
            '-g', str(round(fps*config.gop_length_seconds)),
            '-f', 'webm',
            self._cl3w_filename
        ]
        subprocess.call(
            commandline
        )
        if isinstance(self._source, (bytes, bytearray)):
            f.close()

    def animation_encode(self):
        print("SRS ANIMATION ENCODE")
        webm_transcoder.WEBM_VideoOutputFormat.animation_encode(self)
        self.animation2webm_cl3w()
        self._output_size = os.path.getsize(self._cl3w_filename) + self._output_size

    def _optimisations_failed(self):
        os.remove(self._cl0w_filename)
        os.remove(self._cl3w_filename)

    def _save(self):
        srs_data = {
            "ftype": "CLSRS",
            "content": {
                "media-type": 3,
                "tags": dict()
            },
            "streams": {
                "video": {"levels": dict()}
            }
        }
        srs_video_levels = dict()
        if self._cl0w_filename:
            srs_video_levels["0w"] = pathlib.Path(self._cl0w_filename).name
        if self._cl0w_filename:
            srs_video_levels["3w"] = pathlib.Path(self._cl3w_filename).name
        srs_data['streams']['video']['levels'] = srs_video_levels
        self._srs_write_srs(srs_data)

    def _srs_write_srs(self, srs_data):
        srs.write_srs(srs_data, self._item_data, self._content_metadata, self._output_file)
