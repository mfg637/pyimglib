import subprocess
import json
import pathlib
import os
from . import statistics
from .common import videoprocessing
from ..decoders import ffmpeg
from .. import config

CL3_MAX_VIDEO_BITRATE = 5_000_000


class WEBM_WRITER:

    def __init__(self, source, path, file_name, item_data):
        self._source = source
        self._output_file = os.path.join(path, file_name)

    def transcode(self):
        f = None
        clx = self._output_file+".webm"
        if isinstance(self._source, (bytes, bytearray)):
            f = open(clx, "bw")
            f.write(self._source)
            f.close()
        return 0, 0, 0, 0


class SRS_WEBM_Converter:
    def __init__(self, source, path, file_name, item_data, metadata):
        self._source = source
        self._output_file = os.path.join(path, file_name)
        self._file_name = file_name
        self._item_data = item_data
        self._content_metadata = metadata


    def transcode(self):
        fname = self._output_file + ".webm"
        f = None
        clx = self._file_name + ".webm"
        cl1 = None
        if type(self._source) is str:
            fname = self._source
        elif isinstance(self._source, (bytes, bytearray)):
            f = open(fname, "bw")
            f.write(self._source)
            f.close()
        src_metadata = ffmpeg.probe(fname)
        video = ffmpeg.parser.find_video_stream(src_metadata)
        fps = ffmpeg.parser.get_fps(video)
        fps, src_fps_valid = videoprocessing.limit_fps(fps)
        size_valid = videoprocessing.cl3_size_valid(video)
        audio_streams = ffmpeg.parser.find_audio_streams(src_metadata)
        cl3 = None
        cl2 = None
        passfile = videoprocessing.ffmpeg_get_passfile_prefix()
        if not src_fps_valid or not size_valid or video['pix_fmt'] != "yuv420p":
            cl3 = self._file_name + "_cl3.webm"
        audio = list()
        cl3x = None
        bitrate = 0
        if len(audio_streams):
            vstream_file = None
            if cl3 is None:
                cl3x = self._file_name + "_cl3x.webm"
                vstream_file = self._output_file + "_cl3x.webm"
            else:
                cl1 = self._file_name + "_cl1.webm"
                vstream_file = self._output_file + "_cl1.webm"
            commandline = [
                'ffmpeg'
            ]
            if config.allow_rewrite:
                commandline += ['-y']
            commandline += [
                '-i', fname,
                '-map', '0:v:0',
                '-c', 'copy',
                '-f', 'webm',
                vstream_file
            ]
            subprocess.run(commandline)
            vstream_data = ffmpeg.probe(vstream_file)
            bitrate = ffmpeg.parser.get_file_bitrate(vstream_data)
            for stream in audio_streams:
                index = stream['index']
                chanels = stream['channels']
                afname = self._output_file + "_audio{}.webm".format(index)
                aname = self._file_name + "_audio{}.webm".format(index)
                commandline = [
                    'ffmpeg'
                ]
                if config.allow_rewrite:
                    commandline += ['-y']
                commandline += [
                    '-i', fname,
                    '-map', '0:{}'.format(index),
                    '-c', 'copy',
                    '-f', 'webm',
                    afname
                ]
                subprocess.run(commandline)
                channels = dict()
                channels[str(chanels)] = {'3w': aname}
                audio.append({"channels": channels})
        else:
            bitrate = ffmpeg.parser.get_file_bitrate(src_metadata)

        if not src_fps_valid or not size_valid or video['pix_fmt'] != "yuv420p" or bitrate > 4096:
            if cl1 is None:
                cl2 = cl3x
                cl3 = self._file_name + "_cl3.webm"
            for PASS in range(1, 3):
                commandline = [
                    'ffmpeg'
                ]
                if config.allow_rewrite:
                    commandline += ['-y']
                commandline += [
                    '-loglevel', 'error',
                    '-i', fname,
                    '-pix_fmt', 'yuv420p'
                ]
                if not src_fps_valid:
                    commandline += videoprocessing.ffmpeg_set_fps_commandline(fps)
                if not size_valid:
                    commandline += videoprocessing.CL3_FFMPEG_SCALE_COMMANDLINE
                commandline += [
                    '-c:v', 'libvpx-vp9',
                    '-crf', str(config.VP9_VIDEO_CRF),
                    '-b:v', str(min(round(bitrate * config.cl3_to_orig_ratio), CL3_MAX_VIDEO_BITRATE)),
                    '-maxrate', '5M',
                    '-profile:v', '0']
                if len(audio_streams):
                    commandline += [
                        '-an'
                    ]
                commandline += [
                    '-cpu-used', '4',
                    '-pass', str(PASS),
                    '-passlogfile', passfile,
                    '-g', str(round(fps*config.gop_length_seconds))
                ]
                if PASS == 1:
                    commandline += [
                        '-f', 'null',
                        os.devnull
                    ]
                elif PASS == 2:
                    commandline += [
                        '-f', 'webm',
                        self._output_file + "_cl3.webm"
                    ]
                subprocess.call(
                    commandline
                )

        srs_data = None
        if len(audio):
            srs_data = {
                "ftype": "CLSRS",
                "content": {
                    "media-type": -1,
                    "tags": dict()
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
                    "media-type": -1,
                    "tags": dict()
                },
                "streams": {
                    "video": {"levels": dict()}
                }
            }
        if len(audio_streams):
            srs_data['content']['media-type'] = 2
        else:
            srs_data['content']['media-type'] = 3
        srs_video_levels = dict()
        if cl3 is None:
            if cl3x is not None:
                srs_video_levels["3w"] = cl3x
            else:
                srs_video_levels["3w"] = clx
        else:
            if cl1:
                srs_video_levels["1w"] = cl1
            elif cl2:
                srs_video_levels["2w"] = cl2
            else:
                srs_video_levels["1w"] = clx
            srs_video_levels["3w"] = pathlib.Path(cl3).name
        srs_data['streams']['video']['levels'] = srs_video_levels
        for key in self._item_data:
            srs_data['content']['tags'][key] = list(self._item_data[key])
        srs_data['content'].update(self._content_metadata)
        if len(audio):
            srs_data['streams']['audio'].extend(audio)
        srs_file = open(self._output_file + '.srs', 'w')
        json.dump(srs_data, srs_file)
        srs_file.close()
        if len(audio):
            os.remove(fname)
        return 0, 0, 0, 0
