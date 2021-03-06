import subprocess
import os
import abc
import tempfile
import logging
from . import base_transcoder, statistics
from .. import config

logger = logging.getLogger(__name__)


class WEBM_VideoOutputFormat(base_transcoder.BaseTranscoder):
    def __init__(self, source, path: str, file_name: str, item_data: dict):
        super().__init__(source, path, file_name, item_data)
        self._cl0w_filename = self._output_file + '_cl0w.webm'

    def animation2webm(self):
        fname = ""
        f = None
        if type(self._source) is str:
            fname = self._source
        elif isinstance(self._source, (bytes, bytearray)):
            f = tempfile.NamedTemporaryFile()
            fname = f.name
            f.write(self._source)
        commandline = [
                'ffmpeg'
        ]
        if config.allow_rewrite:
            commandline += ['-y']
        commandline += [
                '-loglevel', 'error',
                '-i', fname,
                '-pix_fmt', 'yuva420p10le',
                '-c:v', 'libaom-av1',
                '-crf', str(config.VIDEOLOOP_CRF),
                '-b:v', '0',
                '-profile:v', '0',
                '-cpu-used', '4',
                '-row-mt', '1',
                '-threads', str(config.encoding_threads),
                '-f', 'webm',
                self._cl0w_filename
            ]
        subprocess.call(
            commandline
        )
        if isinstance(self._source, (bytes, bytearray)):
            f.close()

    def animation_encode(self):
        self._quality = 68
        self.animation2webm()
        try:
            self._output_size = os.path.getsize(self._cl0w_filename)
        except FileNotFoundError:
            raise base_transcoder.NotOptimizableSourceException()

    @abc.abstractmethod
    def _all_optimisations_failed(self):
        pass

    @abc.abstractmethod
    def get_converter_type(self):
        pass

    def gif_optimisations_failed(self):
        fname = None
        logging.exception("optimisations_failed")
        logging.debug("FILE SIZE", self._output_size)
        self._fext = 'webp'
        converter = self.get_converter_type()(self._source)
        out_data = converter.compress(lossless=True)
        self._output_size = len(out_data)
        if self._output_size >= self._size:
            self._all_optimisations_failed()
        else:
            out_data = converter.compress(lossless=True, fast=False)
            self._output_size = len(out_data)
            fname = self._output_file + '.webp'
            outfile = open(fname, 'wb')
            outfile.write(out_data.tobytes())
            outfile.close()
            logger.info(('save {} kbyte ({}%) quality = {}').format(
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
        return fname
