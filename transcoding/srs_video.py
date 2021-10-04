import subprocess
import json
import pathlib
import os
from . import statistics
from ..decoders import ffmpeg


class WEBM_WRITER:

    def __init__(self, source, path, file_name, item_data, pipe):
        self._source = source
        self._output_file = os.path.join(path, file_name)
        self._pipe = pipe

    def transcode(self):
        f = None
        clx = self._output_file+".webm"
        if isinstance(self._source, (bytes, bytearray)):
            f = open(clx, "bw")
            f.write(self._source)
            f.close()
        statistics.pipe_send(self._pipe)


class SRS_WEBM_Converter:
    def __init__(self, source, path, file_name, item_data, pipe, metadata):
        self._source = source
        self._output_file = os.path.join(path, file_name)
        self._file_name = file_name
        self._item_data = item_data
        self._content_metadata = metadata
        self._pipe = pipe


    def transcode(self):
        fname = self._output_file + ".webm"
        f = None
        crf = 24
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
        src_fps_valid = True
        if fps > 30:
            src_fps_valid = False
            while fps > 30:
                fps /= 2
        size_valid = (video["width"] <= 1920 or video["height"] <= 1280)
        audio_streams = ffmpeg.parser.find_audio_streams(src_metadata)
        cl3 = None
        if not src_fps_valid or not size_valid or video['pix_fmt'] != "yuv420p":
            cl3 = self._file_name + "_cl3.webm"
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
            if not size_valid:
                commandline += ['-vf', 'scale=\'min(1280,iw)\':\'min(1280,ih)\'']
            commandline += [
                '-c:v', 'libvpx-vp9',
                '-crf', str(crf),
                '-b:v', '0',
                '-profile:v', '0']
            if len(audio_streams):
                commandline += [
                    '-an'
                ]
            commandline += [
                '-cpu-used', '4',
                '-f', 'webm',
                self._output_file + "_cl3.webm"
            ]
            subprocess.call(
                commandline
            )
        audio = list()
        cl3x = None
        if len(audio_streams):
            vstream_file = None
            if cl3 is None:
                cl3x = self._file_name + "_cl3.webm"
                vstream_file = self._output_file + "_cl3.webm"
            else:
                cl1 = self._file_name + "_cl1.webm"
                vstream_file = self._output_file + "_cl1.webm"
            commandline = [
                'ffmpeg',
                '-i', fname,
                '-map', '0:v:0',
                '-c', 'copy',
                '-f', 'webm',
                vstream_file
            ]
            subprocess.run(commandline)
            for stream in audio_streams:
                index = stream['index']
                chanels = stream['channels']
                afname = self._output_file + "_audio{}.webm.cl3w".format(index)
                aname = self._file_name + "_audio{}.webm.cl3w".format(index)
                commandline = [
                    'ffmpeg',
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
        statistics.pipe_send(self._pipe)
