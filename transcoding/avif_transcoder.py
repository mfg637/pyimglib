import abc
import tempfile
import subprocess
import io
from . import webp_transcoder, config
from PIL import Image
import pyimglib_decoders.YUV4MPEG2


class AVIF_WEBP_output(webp_transcoder.WEBP_output, metaclass=abc.ABCMeta):

    def get_color_profile(self):
        return [
            '--profile', '1',
            '--pix-fmt', 'yuv444'
        ]

    def get_color_profile_by_subsampling(self, subsampling):
        if subsampling == pyimglib_decoders.YUV4MPEG2.SUPPORTED_COLOR_SPACES.YUV444:
            return[
                '--profile', '1',
                '--pix-fmt', 'yuv444'
            ]
        elif subsampling == pyimglib_decoders.YUV4MPEG2.SUPPORTED_COLOR_SPACES.YUV422:
            return [
                '--profile', '2',
                '--pix-fmt', 'yuv422'
            ]
        elif subsampling == pyimglib_decoders.YUV4MPEG2.SUPPORTED_COLOR_SPACES.YUV420:
            return [
                '--pix-fmt', 'yuv420'
            ]

    def _lossy_encode(self, img:Image.Image) -> None:
        src_tmp_file = None
        src_tmp_file_name = None
        if type(self._source) is str:
            src_tmp_file_name = self._source
        else:
            src_tmp_file = tempfile.NamedTemporaryFile(mode='wb', suffix=".png", delete=True)
            src_tmp_file_name = src_tmp_file.name
            img.save(src_tmp_file, format="PNG")
        #fix ICPP profiles error
        check_error = subprocess.run(['pngcrush', '-n', '-q', src_tmp_file_name], stderr=subprocess.PIPE)
        if b'pngcrush: iCCP: Not recognizing known sRGB profile that has been edited' in check_error.stderr:
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            proc = subprocess.Popen(['convert', '-', src_tmp_file_name], stdin=subprocess.PIPE)
            proc.communicate(buf.getbuffer())
            proc.wait()
        output_tmp_file = tempfile.NamedTemporaryFile(mode='rb', suffix=".avif", delete=True)
        crf = 100 - self._quality
        crf_low = crf + 5
        commandline = []
        if self._transparency_check(img):
            commandline = [
                'avifenc',
                src_tmp_file_name,
                output_tmp_file.name,
                '-s', '0',
                '--min', str(crf),
                '--max', str(crf_low),
                '--minalpha', '0',
                '-j', str(config.avif_encoding_threads)
            ]
        else:
            commandline = [
                'cavif',
                '-i', src_tmp_file_name,
                '-o', output_tmp_file.name,
                '--encode-target', 'image',
                '--crf', str(100 - self._quality),
                '--cpu-used', '0',
                '--enable-full-color-range',
                '--enable-cdef',
                '--adaptive-quantization', 'variance'
            ]
            if crf >= 20:
                commandline += ['--enable-loop-restoration']
            commandline += self.get_color_profile()
            if config.avif_encoding_threads is not None and config.avif_encoding_threads > 0:
                commandline += ['--enable-row-mt', '--threads', str(config.avif_encoding_threads)]

        subprocess.run(commandline)
        if src_tmp_file is not None:
            src_tmp_file.close()
        self._lossy_data = output_tmp_file.read()
        output_tmp_file.close()

    def _save_webp(self):
        if not self._lossless:
            self.file_suffix = ".avif"
        webp_transcoder.WEBP_output._save_webp(self)
