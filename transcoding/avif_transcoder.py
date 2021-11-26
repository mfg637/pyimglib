import abc
import tempfile
import subprocess
import io
from . import webp_transcoder
from .. import config
from PIL import Image
from .. import decoders


class AVIF_WEBP_output(webp_transcoder.WEBP_output, metaclass=abc.ABCMeta):
    def __init__(self, source, path: str, file_name: str, item_data: dict):
        webp_transcoder.WEBP_output.__init__(self, source, path, file_name, item_data)
        self._bit_depth = 10
        self._av1_enable_advanced_options = True

    def get_color_profile(self):
        return [
            '-y', '444'
        ]

    def get_color_profile_by_subsampling(self, subsampling):
        if subsampling == decoders.YUV4MPEG2.SUPPORTED_COLOR_SPACES.YUV444:
            return[
                '-y', '444'
            ]
        elif subsampling == decoders.YUV4MPEG2.SUPPORTED_COLOR_SPACES.YUV422:
            return [
                '-y', '422'
            ]
        elif subsampling == decoders.YUV4MPEG2.SUPPORTED_COLOR_SPACES.YUV420:
            return [
                '-y', '420'
            ]

    def _core_encoder(self, img):
        self._lossy_encode = self.avif_lossy_encode
        webp_transcoder.WEBP_output._core_encoder(self, img)

    def avif_lossy_encode(self, img:Image.Image) -> None:
        src_tmp_file = None
        src_tmp_file_name = None
        if type(self._source) is str:
            src_tmp_file_name = self._source
        else:
            src_tmp_file = tempfile.NamedTemporaryFile(mode='wb', suffix=".png", delete=True)
            src_tmp_file_name = src_tmp_file.name
            img.save(src_tmp_file, format="PNG")
        # fix ICPP profiles error
        check_error = subprocess.run(['pngcrush', '-n', '-q', src_tmp_file_name], stderr=subprocess.PIPE)
        if b'pngcrush: iCCP: Not recognizing known sRGB profile that has been edited' in check_error.stderr:
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            proc = subprocess.Popen(['convert', '-', src_tmp_file_name], stdin=subprocess.PIPE)
            proc.communicate(buf.getbuffer())
            proc.wait()
        output_tmp_file = tempfile.NamedTemporaryFile(mode='rb', suffix=".avif", delete=True)
        crf = 100 - self._quality
        commandline = ['avifenc']
        if config.avif_encoding_threads is not None and config.avif_encoding_threads > 0:
            commandline += ['-j', str(config.avif_encoding_threads)]
        commandline += self.get_color_profile()
        commandline += [
            '-d', str(self._bit_depth),
            '-s', str(config.avifenc_encoding_speed),
            '--min', '1',
            '--max', '63',
            '-a', 'end-usage=q',
            '-a', 'cq-level={}'.format(crf)
        ]
        if self._av1_enable_advanced_options:
            commandline += [
                '-a', 'enable-chroma-deltaq=1',
                '-a', 'aq-mode=1'
            ]
        commandline += [
            src_tmp_file_name,
            output_tmp_file.name
        ]
        subprocess.run(commandline)
        if src_tmp_file is not None:
            src_tmp_file.close()
        self._lossy_data = output_tmp_file.read()
        output_tmp_file.close()
        if len(self._lossy_data) == 0 and self._av1_enable_advanced_options:
            self._av1_enable_advanced_options = False
            self.avif_lossy_encode(img)

    def _save_image(self):
        if not self._lossless:
            self.file_suffix = ".avif"
        webp_transcoder.WEBP_output._save_image(self)
