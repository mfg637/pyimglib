import subprocess
import tempfile
import os
import json
import pathlib
from ..decoders import ffmpeg
from .. import config
from . import webm_transcoder
from abc import ABC


class SrsVideoLoopOutput(webm_transcoder.WEBM_VideoOutputFormat, ABC):
    def __init__(self, source, path, file_name, item_data, pipe, metadata):
        webm_transcoder.WEBM_VideoOutputFormat.__init__(self, source, path, file_name, item_data, pipe)
        self._cl3w_filename = self._output_file + '_cl3w.webm'
        self._content_metadata = metadata

    def animation2webm_cl3w(self, crf=32):
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
        src_fps_valid = True
        if fps > 30:
            src_fps_valid = False
            while fps > 30:
                fps /= 2
        commandline = [
            'ffmpeg',
            '-loglevel', 'error',
            '-i', fname,
            '-pix_fmt', 'yuv420p'
        ]
        if not src_fps_valid:
            commandline += [
                '-r', str(fps)
            ]
        if video["width"] > config.cl3_width or video["height"] > config.cl3_height:
            commandline += [
                '-vf', 'scale=\'min({},iw)\':\'min({},ih)\':force_original_aspect_ratio=decrease'.format(
                    config.cl3_width, config.cl3_height
                )
            ]
        commandline += [
            '-c:v', 'libvpx-vp9',
            '-crf', str(crf),
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
        for key in self._item_data:
            srs_data['content']['tags'][key] = list(self._item_data[key])
        srs_data['content'].update(self._content_metadata)
        srs_file = open(self._output_file + '.srs', 'w')
        json.dump(srs_data, srs_file)
        srs_file.close()
