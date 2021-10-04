import PIL.Image
import subprocess
from . import frames_stream, ffmpeg

from .ffmpeg.parser import fps_calc


class FFmpegFramesStream(frames_stream.FramesStream):
    def __init__(self, file_name, original_filename=None):
        super().__init__(file_name)
        self._original_filename = original_filename
        data = ffmpeg.probe(file_name)

        video = ffmpeg.parser.find_video_stream(data, ffmpeg.parser.SPECIFY_VIDEO_STREAM.LAST)

        fps = ffmpeg.parser.get_fps(video)
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
