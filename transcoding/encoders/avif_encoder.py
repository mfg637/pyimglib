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

    def encode(self, quality, lossless=False, force_subsampling=False, reencode_source=False) -> bytes:
        def check_source_acceptable(self, reencode_source):
            source_is_file: bool = type(self._source) is str or isinstance(self._source, pathlib.Path)
            format_acceptable: bool = self._img.format in {"PNG", "JPEG"}
            return not reencode_source and source_is_file and format_acceptable
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

        if check_source_acceptable(self, reencode_source):
            commandline += [
                self._source,
                output_tmp_file.name
            ]
        else:
            src_tmp_file_name = None
            is_source_byteslike = isinstance(self._source, (memoryview, bytes))
            if not reencode_source and self._img.format == "PNG" and is_source_byteslike:
                src_tmp_file = tempfile.NamedTemporaryFile(
                    mode='wb', suffix=".png", delete=True)
                src_tmp_file.write(self._source)
            elif not reencode_source and self._img.format == "JPEG" and is_source_byteslike:
                src_tmp_file = tempfile.NamedTemporaryFile(
                    mode='wb', suffix=".jpg", delete=True)
                src_tmp_file.write(self._source)
            else:
                src_tmp_file = tempfile.NamedTemporaryFile(
                    mode='wb', suffix=".png", delete=True)
                self._img.save(src_tmp_file, format="PNG", compress_level=0)
            src_tmp_file_name = src_tmp_file.name

            if ".png" in src_tmp_file_name:
                # fix ICPP profiles error
                check_error = subprocess.run(
                    ['pngcrush', '-n', '-q', src_tmp_file_name], stderr=subprocess.PIPE)
                if b'pngcrush: iCCP: Not recognizing known sRGB profile that has been edited' in check_error.stderr:
                    buf = io.BytesIO()
                    self._img.save(buf, format="PNG")
                    proc = subprocess.Popen(
                        ['magick', '-', src_tmp_file_name], stdin=subprocess.PIPE)
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
        if len(encoded_data) == 0 and not reencode_source:
            logger.warning("Encoded file is empty. Try again with resaved source file.")
            # This code temporary disabled.
            # If options such as aq-mode or enable-chroma-deltaq causing errors, enable it.
            # self._av1_enable_advanced_options = False
            return self.encode(quality, reencode_source=True)
        return encoded_data


class AVIFSubsampledEncoder(AVIFEncoder):
    SUFFIX = ".avif"

    def encode(self, quality) -> bytes:
        return AVIFEncoder.encode(self, quality, force_subsampling=True)


class AVIFLosslessEncoder(AVIFEncoder):
    SUFFIX = ".avif"

    def encode(self, quality) -> bytes:
        return AVIFEncoder.encode(self, quality, True)
