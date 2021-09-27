import abc
import io
import subprocess
import os
from PIL import Image


class Converter():
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def __init__(self, path):
        self._path = ""
        self._images = []
        self._loop = 0
        self._duration = []

    @abc.abstractmethod
    def close(self):
        pass

    def compress(self, quality: int = 90, fast: bool = True, lossless: bool = False) -> memoryview:
        print('try to convert, quality={}, f={}'.format(quality, fast))
        out_io = io.BytesIO()
        kwargs = dict()
        if fast and not lossless:
            kwargs = {
                'method': 3,
                'loop': self._loop,
                'duration': self._duration,
                'quality': quality,
            }
        elif fast and lossless:
            kwargs = {
                'method': 3,
                'loop': self._loop,
                'duration': self._duration,
            }
        elif not fast and not lossless:
            kwargs = {
                'loop': self._loop,
                'duration': self._duration,
                'quality': quality,
                'method': 6
            }
        elif not fast and lossless:
            kwargs = {
                'loop': self._loop,
                'duration': self._duration,
                'method': 6,
                'lossless': True,
                'quality': 100
            }
        if len(self._images) > 1:
            self._images[0].save(
                out_io,
                'WEBP',
                save_all=True,
                append_images=self._images[1:],
                **kwargs
            )
        else:
            self._images[0].save(
                out_io,
                'WEBP',
                **kwargs
            )
        return out_io.getbuffer()


class GIFconverter(Converter):

    def __init__(self, gif):
        in_io = io.BytesIO()
        img = None
        if type(gif) is str:
            img = Image.open(gif)
        elif isinstance(gif, (bytes, bytearray)):
            in_io = io.BytesIO(gif)
            img = Image.open(in_io)
        else:
            raise Exception()
        if 'duration' in img.info:
            self._duration = img.info['duration']
        else:
            self._duration = 0
        if 'loop' in img.info:
            self._loop = img.info['loop']
        else:
            self._loop = 1
        self._width = img.width
        self._height = img.height
        img.close()
        self._images = []
        ffprocess = None
        tmpfilename = None
        if type(gif) is str:
            commandline = ['ffmpeg',
                           '-loglevel', 'error',
                           '-i', gif,
                           '-f', 'image2pipe',
                           '-pix_fmt', 'rgba',
                           '-an',
                           '-vcodec', 'rawvideo', '-']
            ffprocess = subprocess.Popen(commandline, stdout=subprocess.PIPE)
        elif isinstance(gif, (bytes, bytearray)):
            tmpfilename = "ffmpeg_processing.gif"
            tmpfile = open(tmpfilename, 'bw')
            tmpfile.write(gif)
            tmpfile.close()
            commandline = ['ffmpeg',
                           '-loglevel', 'error',
                           '-i', tmpfilename,
                           '-f', 'image2pipe',
                           '-pix_fmt', 'rgba',
                           '-an',
                           '-vcodec', 'rawvideo', '-']
            ffprocess = subprocess.Popen(commandline, stdout=subprocess.PIPE)
        frame_size = self._width * self._height * 4
        buffer = ffprocess.stdout.read(frame_size)
        while len(buffer) == frame_size:
            self._images.append(Image.frombuffer("RGBA", (self._width, self._height), buffer, "raw", "RGBA", 0, 1))
            buffer = ffprocess.stdout.read(frame_size)
        ffprocess.stdout.close()
        if tmpfilename is not None:
            os.remove(tmpfilename)

    def close(self):
        for frame in self._images:
            frame.close()


class APNGconverter(Converter):
    def __init__(self, png_path):
        self._path = png_path
        subprocess.run(['apngdis', png_path])
        os.chdir(os.path.dirname(png_path))
        self._duration = []
        self._loop = 0
        self._images = []
        self._fname = []
        zeroes_count = 0
        i = 1
        test_zeroes = ''
        while not os.path.isfile('apngframe' + test_zeroes + str(i) + '.png'):
            zeroes_count += 1
            test_zeroes += '0'
        file_name = 'apngframe'
        file_name += str(i).zfill(zeroes_count + 1)

        while os.path.isfile(file_name + '.png'):
            try:
                info_file = open(file_name + '.txt')
            except FileNotFoundError:
                break
            info_file.seek(6)
            self._duration.append(int(round(eval(info_file.read()) * 1000)))
            info_file.close()
            self._fname.append(file_name + '.png')
            self._images.append(Image.open(file_name + '.png'))
            os.remove(file_name + '.txt')
            file_name = 'apngframe'
            i += 1
            file_name += str(i).zfill(zeroes_count + 1)

    def close(self):
        for frame in self._fname:
            os.remove(frame)
        for frame in self._images:
            frame.close()