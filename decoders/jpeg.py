#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import struct
import subprocess
import threading
import io

from .YUV4MPEG2 import SUPPORTED_COLOR_SPACES

from . import CustomDecoder

START_OF_FRAME_MARKERS = {
    b'\xff\xc0',
    b'\xff\xc1',
    b'\xff\xc2',
    b'\xff\xc3',
    b'\xff\xc5',
    b'\xff\xc6',
    b'\xff\xc7',
    b'\xff\xc8',
    b'\xff\xc9',
    b'\xff\xca',
    b'\xff\xcb',
    b'\xff\xcd',
    b'\xff\xce',
    b'\xff\xcf',
}


is_arithmetic_SOF = {
    b'\xff\xc0': False,
    b'\xff\xc1': False,
    b'\xff\xc2': False,
    b'\xff\xc3': False,
    b'\xff\xc5': False,
    b'\xff\xc6': False,
    b'\xff\xc7': False,
    b'\xff\xc8': True,
    b'\xff\xc9': True,
    b'\xff\xca': True,
    b'\xff\xcb': True,
    b'\xff\xcd': True,
    b'\xff\xce': True,
    b'\xff\xcf': True
}


def read_frame_data(seekable_binary_stream: io.BufferedRandom):
    seekable_binary_stream.seek(0)
    header = seekable_binary_stream.read(2)
    if header != b'\xff\xd8':
        raise Exception
    size = None
    while size is None:
        marker = seekable_binary_stream.read(2)
        # fix marker reading position
        if marker[0] != 255 and marker[1] == 255:
            seekable_binary_stream.seek(-1, 1)
            marker = seekable_binary_stream.read(2)
        if marker == b'\xff\x00':
            raise ValueError("jpeg marker not found")
        if marker in START_OF_FRAME_MARKERS:
            seekable_binary_stream.seek(3, 1)
            size = struct.unpack('>HH', seekable_binary_stream.read(4))
            components = seekable_binary_stream.read(1)[0]
            component_scales = []
            subsampling = SUPPORTED_COLOR_SPACES.NONE
            for component in range(components):
                component_id = seekable_binary_stream.read(1)[0]
                colorspace_struct = seekable_binary_stream.read(1)[0]
                h = (colorspace_struct & 0xf0) >> 4
                v = colorspace_struct & 0x0f
                component_scales.append((h, v))
                seekable_binary_stream.seek(1, 1)
            if component_scales[0] == (2, 2):
                subsampling = SUPPORTED_COLOR_SPACES.YUV420
            elif component_scales[0] == (2, 1) or component_scales[0] == (1, 2):
                subsampling = SUPPORTED_COLOR_SPACES.YUV422
            else:
                subsampling = SUPPORTED_COLOR_SPACES.YUV444
            return (size, subsampling)
        else:
            frame_len = struct.unpack('>H', seekable_binary_stream.read(2))[0]
            seekable_binary_stream.seek(frame_len - 2, 1)


def is_JPEG(file_path):
    file = open(file_path, 'rb')
    header = file.read(2)
    file.close()
    return header == b'\xff\xd8'


class JPEGDecoder(CustomDecoder.CustomDecoder):
    def __init__(self, file_path):
        self._file_path = file_path
        self._file = open(file_path, 'rb')
        header = self._file.read(2)
        if header != b'\xff\xd8':
            self._file.close()
            raise Exception
        self._size = None
        self._process = None

    def get_size(self):
        self._size = read_frame_data(self._file)[0]
        return self._size

    def arithmetic_coding(self):
        if self._size is None:
            while self._size is None:
                marker = self._file.read(2)
                # fix marker reading position
                if marker[0] != 255 and marker[1] == 255:
                    self._file.seek(-1, 1)
                    marker = self._file.read(2)
                if marker == b'\xff\x00':
                    raise ValueError("jpeg marker not found")
                if marker in START_OF_FRAME_MARKERS:
                    return is_arithmetic_SOF[marker]

    def load_image(self):
        self._file.seek(0, 0)
        data = self._file.read(1024)
        while len(data):
            self._process.stdin.write(data)
            data = self._file.read(1024)
        self._process.stdin.close()

    def decode(self, required_size=None):
        commandline = ['djpeg']
        if required_size is not None:
            if self._size is None:
                self.get_size()
            commandline += ['-scale']
            if (required_size[0]/self._size[1]*self._size[0]) <= required_size[1]:
                commandline += ["{}/{}".format(required_size[0], self._size[1])]
            else:
                commandline += ["{}/{}".format(required_size[1], self._size[0])]
        self._process = subprocess.Popen(
            commandline,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE
        )
        threading.Thread(target=self.load_image).start()
        return self._process

    def __del__(self):
        self._file.close()
