import abc
import subprocess
import os
import io
import logging
from . import webp_transcoder, base_transcoder, avif_transcoder, srs_transcoder
from .. import decoders
from PIL import Image

logger = logging.getLogger(__name__)


def is_arithmetic_jpg(file_path):
    jpeg_decoder = decoders.jpeg.JPEGDecoder(file_path)
    return jpeg_decoder.arithmetic_coding()


class JPEGTranscode(webp_transcoder.WEBP_output):
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def _arithmetic_check(self):
        pass

    @abc.abstractmethod
    def _get_source_data(self):
        pass

    def _transparency_check(self, img: Image.Image) -> bool:
        return False

    def _apng_test_convert(self, img):
        pass

    def _all_optimisations_failed(self):
        pass

    def get_converter_type(self):
        return None

    def lossless_encode(self):
        meta_copy = 'all'
        source_data = self._get_source_data()
        process = subprocess.Popen(['jpegtran', '-copy', meta_copy, '-arithmetic'],
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        process.stdin.write(source_data.getvalue())
        process.stdin.close()
        self._optimized_data = process.stdout.read()
        process.stdout.close()
        process.terminate()
        self._output_size = len(self._optimized_data)

    def size_treshold(self, img):
        return img.width > 1024 or img.height > 1024

    def _encode(self):
        self._arithmetic_check()
        img = self._open_image()
        if self.size_treshold(img):
            self._webp_output = True
            self._core_encoder(img)
        else:
            img.close()
            self.lossless_encode()

    def _save(self):
        if self._webp_output:
            return self._save_image()
        else:
            fname = self._output_file + ".jpg"
            outfile = open(fname, 'wb')
            outfile.write(self._optimized_data)
            outfile.close()
            return fname


class AVIF_JPEG_Transcoder(JPEGTranscode, avif_transcoder.AVIF_WEBP_output):
    __metaclass__ = abc.ABCMeta

    def get_color_profile(self):
        subsampling = decoders.jpeg.read_frame_data(self._get_source_data())[1]
        return self.get_color_profile_by_subsampling(subsampling)

    def __init__(self, source, path: str, file_name: str, item_data: dict):
        JPEGTranscode.__init__(self, source, path, file_name, item_data)
        avif_transcoder.AVIF_WEBP_output.__init__(self, source, path, file_name, item_data)

    def _transparency_check(self, img):
        return False


class SRS_JPEG_Transcoder(JPEGTranscode, srs_transcoder.SrsTranscoder):
    __metaclass__ = abc.ABCMeta

    def get_color_profile(self):
        subsampling = decoders.jpeg.read_frame_data(self._get_source_data())[1]
        return self.get_color_profile_by_subsampling(subsampling)

    def __init__(self, source, path: str, file_name: str, item_data: dict, metadata):
        JPEGTranscode.__init__(self, source, path, file_name, item_data)
        srs_transcoder.SrsTranscoder.__init__(self, source, path, file_name, item_data, metadata)

    def _transparency_check(self, img):
        return False

    def _encode(self):
        img = self._open_image()
        # disable arithmetic encoding for the wide compatibility (compatibility level 4 limitations)
        self._webp_output = True
        self._core_encoder(img)


class JPEGFileTranscode(base_transcoder.FilePathSource, base_transcoder.UnremovableSource, JPEGTranscode):
    def __init__(self, source: str, path: str, file_name: str):
        base_transcoder.FilePathSource.__init__(self, source, path, file_name)
        base_transcoder.UnremovableSource.__init__(self, source, path, file_name)
        JPEGTranscode.__init__(self, source, path, file_name)
        self._quality = 100
        self._optimized_data = b''

    def _arithmetic_check(self):
        try:
            if is_arithmetic_jpg(self._source):
                raise base_transcoder.AlreadyOptimizedSourceException()
        except OSError:
            raise base_transcoder.NotOptimizableSourceException()

    def _get_source_data(self):
        source_file = open(self._source, 'br')
        raw_data = source_file.read()
        source_file.close()
        return raw_data

    def _set_utime(self) -> None:
        os.utime(self._source, (self._atime, self._mtime))

    def _optimisations_failed(self):
        pass

    def _invalid_file_exception_handle(self, e):
        logging.warning('invalid file ' + self._source + ' ({}) has been deleted'.format(e))
        os.remove(self._source)


class JPEGInMemoryTranscode(base_transcoder.InMemorySource, JPEGTranscode):
    def __init__(self, source: bytearray, path: str, file_name: str):
        base_transcoder.InMemorySource.__init__(self, source, path, file_name)
        JPEGTranscode.__init__(self, source, path, file_name)
        self._quality = 100
        self._optimized_data = b''

    def _optimisations_failed(self):
        fname = self._output_file + ".jpg"
        outfile = open(fname, "bw")
        outfile.write(self._source)
        outfile.close()
        logging.warning("save " + fname)
        return fname

    def _arithmetic_check(self):
        pass

    def _get_source_data(self):
        return io.BytesIO(self._source)

    def _invalid_file_exception_handle(self, e):
        logging.exception('invalid jpeg data')


class AVIF_JPEGFileTranscode(AVIF_JPEG_Transcoder, JPEGFileTranscode):
    def __init__(self, source: str, path: str, file_name: str, item_data: dict):
        JPEGFileTranscode.__init__(self, source, path, file_name)
        AVIF_JPEG_Transcoder.__init__(self, source, path, file_name, item_data)


class AVIF_JPEGInMemoryTranscode(AVIF_JPEG_Transcoder, JPEGInMemoryTranscode):
    def __init__(self, source: bytearray, path: str, file_name: str, item_data: dict):
        JPEGInMemoryTranscode.__init__(self, source, path, file_name)
        AVIF_JPEG_Transcoder.__init__(self, source, path, file_name, item_data)


class SRS_JPEGFileTranscode(SRS_JPEG_Transcoder, JPEGFileTranscode):
    def __init__(self, source: str, path: str, file_name: str, item_data: dict, metadata):
        JPEGFileTranscode.__init__(self, source, path, file_name)
        SRS_JPEG_Transcoder.__init__(self, source, path, file_name, item_data, metadata)


class SRS_JPEGInMemoryTranscode(SRS_JPEG_Transcoder, JPEGInMemoryTranscode):
    def __init__(self, source: bytearray, path: str, file_name: str, item_data: dict, metadata):
        JPEGInMemoryTranscode.__init__(self, source, path, file_name)
        SRS_JPEG_Transcoder.__init__(self, source, path, file_name, item_data, metadata)

    def _optimisations_failed(self):
        JPEGInMemoryTranscode._optimisations_failed(self)
        srs_data = {
            "ftype": "CLSRS",
            "content": {
                "media-type": 0,
                "tags": dict()
            },
            "streams": {
                "image": {"levels": {"4": self._file_name + ".jpg"}}
            }
        }
        return self._srs_write_srs(srs_data)
