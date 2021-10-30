import tempfile
import subprocess
from . import YUV4MPEG2
from .. import config
import PIL.Image
import asyncio
import abc


def is_avif(file):
    file = open(file, 'rb')
    file.seek(4)
    header = file.read(8)
    file.close()
    return header in (b'ftypavif', b'ftypavis')


def is_animated_avif(file):
    file = open(file, 'rb')
    file.seek(4)
    header = file.read(8)
    file.close()
    return header == b'ftypavis'


def decode(file):
    return asyncio.run(async_decode(file, None))


async def async_decode(file, process_set_callback):
    if not is_avif(file):
        raise Exception

    class BaseEncode(abc.ABC):
        def __init__(self, callback=None):
            self._tmp_file = None
            self.process = None
            self._suffix = None
            self._callback = callback

        @abc.abstractmethod
        def return_result(self):
            pass

        async def encode(self, file):
            self._tmp_file = tempfile.NamedTemporaryFile(mode='rb', delete=True, suffix=self._suffix)
            commandline = ['avifdec', '-j', str(config.avifdec_workers_count), str(file), self._tmp_file.name]
            self.process = await asyncio.create_subprocess_exec(*commandline)
            if self._callback is not None:
                self._callback(self.process)
            returncode = await self.process.wait()
            return self.return_result()

        def close(self):
            self._tmp_file.close()

    class FastEncode(BaseEncode):
        def return_result(self):
            return YUV4MPEG2.Y4M_FramesStream(self._tmp_file.name)

        def __init__(self, callback):
            BaseEncode.__init__(self, callback)
            self._suffix = '.y4m'

        async def encode(self, file):
            return await BaseEncode.encode(self, file)

    class SlowEncode(BaseEncode):
        def return_result(self):
            return PIL.Image.open(self._tmp_file.name)

        def __init__(self, callback):
            BaseEncode.__init__(self, callback)
            self._suffix = '.png'

        async def encode(self, file):
            return await BaseEncode.encode(self, file)

    async def _encode(encoder, file, callback):
        _encoder = encoder(callback)
        result = await _encoder.encode(file)
        _encoder.close()
        return result

    if config.avif_decoding_speed == config.AVIF_DECODING_SPEEDS.FAST:
        try:
            return await _encode(FastEncode, file, process_set_callback)
        except NotImplementedError:
            return await _encode(SlowEncode, file, process_set_callback)
    elif config.avif_decoding_speed == config.AVIF_DECODING_SPEEDS.SLOW:
        return await _encode(SlowEncode, file, process_set_callback)