import subprocess
import os
import abc
from . import base_transcoder, statistics


def animation2webm(source, out_file, crf=32):
    fname = ""
    if type(source) is str:
        fname = source
    elif isinstance(source, (bytes, bytearray)):
        fname = "transcode"
        file = open(fname, "bw")
        file.write(source)
        file.close()
    subprocess.call(
        [
            'ffmpeg',
            '-loglevel', 'error',
            '-i', fname,
            '-pix_fmt', 'yuva420p',
            '-c:v', 'libvpx-vp9',
            '-crf', str(crf),
            '-b:v', '0',
            '-profile:v', '0',
            '-f', 'webm',
            out_file
        ]
    )
    if isinstance(source, (bytes, bytearray)):
        os.remove(fname)



class WEBM_VideoOutputFormat(base_transcoder.BaseTranscoder):
    def animation_encode(self):
        self._quality = 85
        animation2webm(self._source, self._output_file + '.webm')
        self._output_size = os.path.getsize(self._output_file + '.webm')

    @abc.abstractmethod
    def _all_optimisations_failed(self):
        pass

    @abc.abstractmethod
    def get_converter_type(self):
        pass

    def gif_optimisations_failed(self):
        print("optimisations_failed")
        os.remove(self._output_file + '.webm')
        self._fext = 'webp'
        converter = self.get_converter_type()(self._source)
        out_data = converter.compress(lossless=True)
        self._output_size = len(out_data)
        if self._output_size >= self._size:
            self._all_optimisations_failed()
        else:
            out_data = converter.compress(lossless=True, fast=False)
            self._output_size = len(out_data)
            outfile = open(self._output_file + '.webp', 'wb')
            outfile.write(out_data.tobytes())
            outfile.close()
            print(('save {} kbyte ({}%) quality = {}').format(
                round((self._size - self._output_size) / 1024, 2),
                round((1 - self._output_size / self._size) * 100, 2),
                self._quality
            ))
            self._set_utime()
            self._remove_source()
            statistics.sumsize += self._size
            statistics.sumos += self._output_size
            statistics.avq += self._quality
            statistics.items += 1
        converter.close()
