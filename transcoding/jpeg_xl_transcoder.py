import abc
import subprocess
import tempfile
import pathlib
import os
import io

from . import jpeg_source_transcode, config, base_transcoder


class JPEG_XL_Transcoder(jpeg_source_transcode.JPEGTranscode, abc.ABC):
    def lossless_encode(self):
        self._quality = 100
        src_tmp_file = None
        src_tmp_file_name = None
        if type(self._source) is str:
            src_tmp_file_name = self._source
        else:
            src_tmp_file = tempfile.NamedTemporaryFile(mode='wb', suffix=".png", delete=True)
            src_tmp_file_name = src_tmp_file.name
            src_tmp_file.write(bytearray(self._source))
        output_tmp_file = tempfile.NamedTemporaryFile(mode='rb', suffix=".jxl", delete=True)
        subprocess.run([
            str(pathlib.Path(config.jpeg_xl_tools_path).joinpath("cjxl")),
            str(src_tmp_file_name),
            str(output_tmp_file.name),
            "-d", "0"
        ])
        if src_tmp_file is not None:
            src_tmp_file.close()
        self._optimized_data = output_tmp_file.read()
        output_tmp_file.close()
        self._output_size = len(self._optimized_data)

    def _save(self):
        if self._webp_output:
            self._save_webp()
        else:
            outfile = open(self._output_file + ".jxl", 'wb')
            outfile.write(self._optimized_data)
            outfile.close()


class AVIF_JPEG_XL_Transcoder(jpeg_source_transcode.AVIF_JPEG_Transcoder, JPEG_XL_Transcoder):
    def __init__(self, source, path:str, file_name:str, item_data:dict, pipe):
        jpeg_source_transcode.AVIF_JPEG_Transcoder.__init__(self, source, path, file_name, item_data, pipe)
        JPEG_XL_Transcoder.__init__(self, source, path, file_name, item_data, pipe)


class JPEG_XL_FileTranscoder(base_transcoder.FilePathSource, JPEG_XL_Transcoder):
    def _arithmetic_check(self):
        pass

    def _get_source_data(self):
        source_file = open(self._source, 'br')
        raw_data = source_file.read()
        source_file.close()
        return raw_data

    def _set_utime(self) -> None:
        os.utime(self._output_file, (self._atime, self._mtime))

    def _invalid_file_exception_handle(self, e):
        print('invalid file ' + self._source + ' ({}) has been deleted'.format(e))
        self._remove_source()

    def _remove_source(self):
        os.remove(self._source)

    def _optimisations_failed(self):
        print("save " + self._source)

    def __init__(self, source: str, path: str, file_name: str, item_data: dict, pipe):
        base_transcoder.FilePathSource.__init__(self, source, path, file_name, item_data, pipe)
        JPEG_XL_Transcoder.__init__(self, source, path, file_name, item_data, pipe)
        self._quality = 100
        self._optimized_data = b''


class JPEG_XL_BurrefedSourceTranscoder(base_transcoder.InMemorySource, JPEG_XL_Transcoder):
    def _arithmetic_check(self):
        pass

    def _get_source_data(self):
        return io.BytesIO(self._source)

    def _invalid_file_exception_handle(self, e):
        print('invalid jpeg data')

    def _optimisations_failed(self):
        outfile = open(self._output_file + ".jpg", "bw")
        outfile.write(self._source)
        outfile.close()
        print("save " + self._output_file + ".jpg")

    def __init__(self, source:bytearray, path:str, file_name:str, item_data:dict, pipe):
        base_transcoder.InMemorySource.__init__(self, source, path, file_name, item_data, pipe)
        JPEG_XL_Transcoder.__init__(self, source, path, file_name, item_data, pipe)
        self._quality = 100
        self._optimized_data = b''


class AVIF_JPEG_XL_FileTranscode(AVIF_JPEG_XL_Transcoder, JPEG_XL_FileTranscoder):
    def __init__(self, source: str, path: str, file_name: str, item_data: dict, pipe):
        JPEG_XL_FileTranscoder.__init__(self, source, path, file_name, item_data, pipe)
        AVIF_JPEG_XL_Transcoder.__init__(self, source, path, file_name, item_data, pipe)


class AVIF_JPEG_XL_BufferTranscode(AVIF_JPEG_XL_Transcoder, JPEG_XL_BurrefedSourceTranscoder):
    def __init__(self, source: bytearray, path: str, file_name: str, item_data: dict, pipe):
        JPEG_XL_BurrefedSourceTranscoder.__init__(self, source, path, file_name, item_data, pipe)
        AVIF_JPEG_XL_Transcoder.__init__(self, source, path, file_name, item_data, pipe)
