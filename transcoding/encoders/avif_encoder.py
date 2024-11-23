import io
import logging
import pathlib
import subprocess
import tempfile

import PIL.Image

from ... import config
from ..common import run_subprocess
from .encoder import BytesEncoder

MAX_AVIF_YUV444_SIZE = 2**26 + 2**25

logger = logging.getLogger(__name__)


class AVIFEncoder(BytesEncoder):
    SUFFIX = ".avif"
    enable_tune_ssimulacra2 = False

    def __init__(self, source, img: PIL.Image.Image):
        BytesEncoder.__init__(self, self.SUFFIX)
        self._source = source
        self._img = img

        self._bit_depth = 10
        self._av1_enable_advanced_options = True
        self.encoding_speed = config.avifenc_encoding_speed

    def encode(self, quality, lossless=False, force_subsampling=False) -> bytes:
        if quality == 100 and not force_subsampling:
            lossless = True
        else:
            if self._img.width * self._img.height > MAX_AVIF_YUV444_SIZE:
                force_subsampling = True
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
                '-s', str(self.encoding_speed),
                '--min', str(max(crf - config.avifenc_qdeviation, 1)),
                '--max', str(min(crf + config.avifenc_qdeviation, 63)),
                '-a', 'end-usage=q',
                '-a', 'cq-level={}'.format(crf)
            ]
        if force_subsampling:
            commandline += ['-y', '420']
        if self._av1_enable_advanced_options:
            commandline += [
                '-a', 'color:aq-mode=1',
                '-a', 'color:enable-chroma-deltaq=1',
            ]
            if self.enable_tune_ssimulacra2:
                commandline += ['-a', 'color:tune=ssimulacra2']

        output_tmp_file = tempfile.NamedTemporaryFile(
            mode='rb', suffix=".avif", delete=True)

        src_tmp_file = None

        if type(self._source) is str or isinstance(self._source, pathlib.Path) and self._img.format in {"PNG", "JPEG"}:
            commandline += [
                self._source,
                output_tmp_file.name
            ]
        else:
            src_tmp_file_name = None
            if self._img.format == "PNG" and isinstance(self._source, (memoryview, bytes)):
                src_tmp_file = tempfile.NamedTemporaryFile(
                    mode='wb', suffix=".png", delete=True)
                src_tmp_file.write(self._source)
            elif self._img.format == "JPEG" and isinstance(self._source, (memoryview, bytes)):
                src_tmp_file = tempfile.NamedTemporaryFile(
                    mode='wb', suffix=".jpg", delete=True)
                src_tmp_file.write(self._source)
            else:
                src_tmp_file = tempfile.NamedTemporaryFile(
                    mode='wb', suffix=".png", delete=True)
                self._img.save(src_tmp_file, format="PNG")
            src_tmp_file_name = src_tmp_file.name

            if ".png" in src_tmp_file_name:
                # fix ICPP profiles error
                check_error = subprocess.run(
                    ['pngcrush', '-n', '-q', src_tmp_file_name], stderr=subprocess.PIPE)
                if b'pngcrush: iCCP: Not recognizing known sRGB profile that has been edited' in check_error.stderr:
                    buf = io.BytesIO()
                    self._img.save(buf, format="PNG")
                    proc = subprocess.Popen(
                        ['convert', '-', src_tmp_file_name], stdin=subprocess.PIPE)
                    proc.communicate(buf.getbuffer())
                    proc.wait()

            commandline += [
                src_tmp_file_name,
                output_tmp_file.name
            ]
        logger.debug("commandline {}".format(commandline.__repr__()))

        run_subprocess(commandline, log_stdout=True)
        if src_tmp_file is not None:
            src_tmp_file.close()
        encoded_data = output_tmp_file.read()
        output_tmp_file.close()
        if len(encoded_data) == 0 and self._av1_enable_advanced_options:
            self._av1_enable_advanced_options = False
            return self.encode(quality)
        return encoded_data


class AVIFSubsampledEncoder(AVIFEncoder):
    SUFFIX = ".avif"

    def encode(self, quality) -> bytes:
        return AVIFEncoder.encode(self, quality, force_subsampling=True)


class AVIFLosslessEncoder(AVIFEncoder):
    SUFFIX = ".avif"

    def encode(self, quality) -> bytes:
        return AVIFEncoder.encode(self, quality, True)
