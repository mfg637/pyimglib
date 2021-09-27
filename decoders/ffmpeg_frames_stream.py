import PIL.Image
import subprocess
from . import frames_stream, ffmpeg


def fps_calc(raw_str):
    _f = raw_str.split("/")
    if len(_f) != 2 and len(_f) > 0:
        return int(_f[0])
    elif len(_f) == 2:
        return int(_f[0])/int(_f[1])
    else:
        raise ValueError(raw_str)


class FFmpegFramesStream(frames_stream.FramesStream):
    def __init__(self, file_name, original_filename=None):
        super().__init__(file_name)
        self._original_filename = original_filename
        data = ffmpeg.probe(file_name)

        video = None
        for stream in data['streams']:
            if stream['codec_type'] == "video":
                video = stream

        fps = None
        if video['avg_frame_rate'] == "0/0":
            fps = fps_calc(video['r_frame_rate'])
        else:
            fps = fps_calc(video['avg_frame_rate'])
        self._frame_time_ms = int(round(1 / fps * 1000))

        self._width = video["width"]
        self._height = video["height"]

        self._color_profile = "RGBA"

        self._duration = float(data['format']['duration'])
        self._is_animated = self._duration > (1 / fps)

        commandline = ['ffmpeg',
                       '-i', file_name,
                       '-f', 'image2pipe',
                       '-map', "0:{}".format(video['index']),
                       '-pix_fmt', 'rgba',
                       '-an',
                       '-r', str(fps),
                       '-vcodec', 'rawvideo', '-']
        self.process = subprocess.Popen(commandline, stdout=subprocess.PIPE)

    def next_frame(self) -> PIL.Image.Image:
        frame_size = 0
        if self._color_profile == "RGBA":
            frame_size = self._width * self._height * 4
        else:
            raise NotImplementedError("color profile not supported", self._color_profile)

        if frame_size == 0:
            raise ValueError()

        buffer = self.process.stdout.read(frame_size)

        if len(buffer) > 0:
            return PIL.Image.frombytes(
                self._color_profile,
                (self._width, self._height),
                buffer,
                "raw",
                self._color_profile,
                0,
                1
            )
        else:
            raise EOFError()

    def close(self):
        self.process.stdout.close()
        self.process.terminate()

    @property
    def filename(self):
        if self._original_filename is not None:
            return self._original_filename
        return self._file_path
