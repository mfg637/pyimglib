import io
import pathlib
import subprocess
import tempfile

import PIL.Image

from .encoder import BytesEncoder
from ..common import run_subprocess
from ... import config


class AVIFEncoder(BytesEncoder):
    def __init__(self, source, img: PIL.Image.Image):
        BytesEncoder.__init__(self, ".avif")
        self._source = source
        self._img = img

        self._bit_depth = 10
        self._av1_enable_advanced_options = True

    def encode(self, quality, lossless=False) -> bytes:
        crf = 100 - quality
        commandline = ['avifenc']
        if config.encoding_threads is not None and config.encoding_threads > 0:
            commandline += ['-j', str(config.encoding_threads)]
        if lossless:
            commandline += ["--lossless"]
            self._av1_enable_advanced_options = False
        else:
            commandline += [
                '-d', str(self._bit_depth),
                '-s', str(config.avifenc_encoding_speed),
                '--min', str(max(crf - config.avifenc_qdeviation, 1)),
                '--max', str(min(crf + config.avifenc_qdeviation, 63)),
                '-a', 'end-usage=q',
                '-a', 'cq-level={}'.format(crf)
            ]
        if self._av1_enable_advanced_options:
            commandline += [
                '-a', 'aq-mode=1',
                '-a', 'enable-chroma-deltaq=1',
            ]

        output_tmp_file = tempfile.NamedTemporaryFile(mode='rb', suffix=".avif", delete=True)

        src_tmp_file = None

        if type(self._source) is str or isinstance(self._source, pathlib.Path) and self._img.format in {"PNG", "JPEG"}:
            commandline += [
                self._source,
                output_tmp_file.name
            ]
        else:
            src_tmp_file_name = None
            if self._img.format == "PNG" and isinstance(self._source, (memoryview, bytes)):
                src_tmp_file = tempfile.NamedTemporaryFile(mode='wb', suffix=".png", delete=True)
                src_tmp_file.write(self._source)
            elif self._img.format == "JPEG" and isinstance(self._source, (memoryview, bytes)):
                src_tmp_file = tempfile.NamedTemporaryFile(mode='wb', suffix=".jpg", delete=True)
                src_tmp_file.write(self._source)
            else:
                src_tmp_file = tempfile.NamedTemporaryFile(mode='wb', suffix=".png", delete=True)
                self._img.save(src_tmp_file, format="PNG")
            src_tmp_file_name = src_tmp_file.name

            if ".png" in src_tmp_file_name:
                # fix ICPP profiles error
                check_error = subprocess.run(['pngcrush', '-n', '-q', src_tmp_file_name], stderr=subprocess.PIPE)
                if b'pngcrush: iCCP: Not recognizing known sRGB profile that has been edited' in check_error.stderr:
                    buf = io.BytesIO()
                    self._img.save(buf, format="PNG")
                    proc = subprocess.Popen(['convert', '-', src_tmp_file_name], stdin=subprocess.PIPE)
                    proc.communicate(buf.getbuffer())
                    proc.wait()

            commandline += [
                src_tmp_file_name,
                output_tmp_file.name
            ]

        run_subprocess(commandline, log_stdout=True)
        if src_tmp_file is not None:
            src_tmp_file.close()
        encoded_data = output_tmp_file.read()
        output_tmp_file.close()
        if len(encoded_data) == 0 and self._av1_enable_advanced_options:
            self._av1_enable_advanced_options = False
            return self.encode(quality)
        return encoded_data


class AVIFLosslessEncoder(AVIFEncoder):
    def encode(self, quality) -> bytes:
        return AVIFEncoder.encode(self, quality, True)
