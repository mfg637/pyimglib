import PIL.Image
import os
from PIL import Image, ImageFile
from . import frames_stream
import math

from . import CustomDecoder

import enum

FILE_SIGNATURE = b"YUV4MPEG2"
SIGNATURE_LENGTH = len(FILE_SIGNATURE)
MAX_HEADER_LINE_SIZE = 2048

LIMITED_COLOR_RANGE = "XCOLORRANGE=LIMITED"


class LIMITED_RANGE_CORRENTION_MODES(enum.Enum):
    NONE = enum.auto()
    CLIPPING = enum.auto()
    EXPAND = enum.auto()


limited_range_correction = LIMITED_RANGE_CORRENTION_MODES.CLIPPING


class SUPPORTED_COLOR_SPACES(enum.Enum):
    NONE = 0
    YUV420 = 420
    YUV422 = 422
    YUV444 = 444
    YUVA4444 = 4444


class COLOOR_SPACE(enum.Enum):
    FULL = enum.auto()
    LIMITED = enum.auto()


def is_Y4M(file_path):
    file = open(file_path, 'rb')
    header = file.read(9)
    file.close()
    return header == FILE_SIGNATURE


class Y4M_FramesStream(frames_stream.FramesStream):
    def __init__(self, file_path):
        super().__init__(file_path)
        self._file_path = file_path
        self._file = open(file_path, 'rb')
        header = self._file.readline(MAX_HEADER_LINE_SIZE)
        if header[:SIGNATURE_LENGTH] != FILE_SIGNATURE:
            self._file.close()
            raise Exception
        self._width, self._height = 0, 0
        self._profile = SUPPORTED_COLOR_SPACES.NONE
        self._color_space = COLOOR_SPACE.FULL
        header_raw_data = str(header).split(' ')[1:]
        for raw_data in header_raw_data:
            if raw_data[0] == 'W':
                self._width = int(raw_data[1:])
            elif raw_data[0] == 'H':
                self._height = int(raw_data[1:])
            elif raw_data[0] == 'C':
                if raw_data[1:] == "444":
                    self._profile = SUPPORTED_COLOR_SPACES.YUV444
                elif raw_data[1:] == "444alpha":
                    self._profile = SUPPORTED_COLOR_SPACES.YUVA4444
                elif raw_data[1:] == "422":
                    self._profile = SUPPORTED_COLOR_SPACES.YUV422
                elif raw_data[1:] == "420jpeg":
                    self._profile = SUPPORTED_COLOR_SPACES.YUV420
                else:
                    raise NotImplementedError("color space {} is not supported".format(raw_data))
            elif raw_data[0] == 'I':
                if raw_data != 'Ip':
                    raise NotImplementedError("Interlacing is not supported")
            elif raw_data[0] == 'A':
                if raw_data != "A0:0" and raw_data != "A1:1":
                    raise NotImplementedError("Non square pixel format")
            elif LIMITED_COLOR_RANGE == raw_data[:len(LIMITED_COLOR_RANGE)]:
                self._color_space = COLOOR_SPACE.LIMITED
            elif raw_data[0] == 'F':
                _f = raw_data[1:].split(':')
                fps = int(_f[0])/int(_f[1])
                self._frame_time_ms = int(round(1 / fps * 1000))
        self._size = (self._width, self._height)

        self._plane_size = self._size[0] * self._size[1]
        self._color_size = self._size
        if self._profile == SUPPORTED_COLOR_SPACES.YUV420:
            self._color_size = (self._size[0] // 2, self._size[1] // 2)
        elif self._profile == SUPPORTED_COLOR_SPACES.YUV422:
            self._color_size = (self._size[0] // 2, self._size[1])

        frame_size = self._plane_size + self._color_size[0] * self._color_size[1] * 2
        if self._profile == SUPPORTED_COLOR_SPACES.YUVA4444:
            frame_size += self._plane_size
        if os.path.getsize(file_path) > frame_size * 2:
            self._is_animated = True
        else:
            self._is_animated = False

    @staticmethod
    def expand_limited_color_range(plane):
        result_plane = bytearray(len(plane))
        MIN_INPUT_VALUE = 16
        MAX_INPUT_VALUE = 235
        DIVIDER = 219
        if limited_range_correction == LIMITED_RANGE_CORRENTION_MODES.EXPAND:
            i = 0
            while i < len(plane):
                if plane[i] < MIN_INPUT_VALUE:
                    MIN_INPUT_VALUE = plane[i]
                    DIVIDER = MAX_INPUT_VALUE - MIN_INPUT_VALUE
                    i = 0
                elif plane[i] > MAX_INPUT_VALUE:
                    MAX_INPUT_VALUE = plane[i]
                    DIVIDER = MAX_INPUT_VALUE - MIN_INPUT_VALUE
                    i = 0
                else:
                    value = (plane[i] - MIN_INPUT_VALUE) / DIVIDER * 255
                    result_plane[i] = int(value)
                    i += 1
        else:
            for i in range(len(plane)):
                value = (plane[i] - MIN_INPUT_VALUE) / DIVIDER * 255
                if value < 0:
                    if limited_range_correction == LIMITED_RANGE_CORRENTION_MODES.CLIPPING:
                        value = 0
                    else:
                        raise ValueError(plane[i])
                elif value > 255:
                    if limited_range_correction == LIMITED_RANGE_CORRENTION_MODES.CLIPPING:
                        value = 255
                    else:
                        raise ValueError(plane[i])
                result_plane[i] = int(value)
            return bytes(result_plane)

    def next_frame(self) -> PIL.Image.Image:
        if self._profile != SUPPORTED_COLOR_SPACES.NONE:
            frame_flag = self._file.read(6)
            if frame_flag != b"FRAME\n":
                raise EOFError("frame flag = {}".format(frame_flag))
            Y_plane = self._file.read(self._plane_size)
            if self._color_space == COLOOR_SPACE.LIMITED:
                Y_plane = self.expand_limited_color_range(Y_plane)
            Y_channel = Image.frombytes("L", self._size, Y_plane, "raw", "L", 0, 1)
            Cb_plane = b""
            Cr_plane = b""
            if self._profile == SUPPORTED_COLOR_SPACES.YUV444 or self._profile == SUPPORTED_COLOR_SPACES.YUVA4444:
                Cb_plane = self._file.read(self._plane_size)
                Cr_plane = self._file.read(self._plane_size)
            else:
                current_plane_size = self._color_size[0] * self._color_size[1]
                if (self._size[0] & 1) == 1 or (self._size[1] & 1) == 1:
                    current_plane_size += self._color_size[1]
                color_planes_buffer = self._file.read(current_plane_size * 2)
                Cb_plane = color_planes_buffer[:len(color_planes_buffer)//2]
                Cr_plane = color_planes_buffer[len(color_planes_buffer)//2:]
                if len(color_planes_buffer) > (self._color_size[0] * self._color_size[1] * 2):
                    self._color_size = (self._color_size[0] + 1, self._color_size[1])

            if self._color_space == COLOOR_SPACE.LIMITED:
                Cb_plane = self.expand_limited_color_range(Cb_plane)
                Cr_plane = self.expand_limited_color_range(Cr_plane)

            Cb_channel = Image.frombytes("L", self._color_size, Cb_plane, "raw", "L", 0, 1)
            Cr_channel = Image.frombytes("L", self._color_size, Cr_plane, "raw", "L", 0, 1)
            if self._profile != SUPPORTED_COLOR_SPACES.YUV444 and self._profile != SUPPORTED_COLOR_SPACES.YUVA4444:
                Cb_channel = Cb_channel.resize(self._size)
                Cr_channel = Cr_channel.resize(self._size)

            image = Image.merge("YCbCr", (Y_channel, Cb_channel, Cr_channel))
            if self._profile == SUPPORTED_COLOR_SPACES.YUVA4444:
                alpha_channel = Image.frombytes("L", self._size, self._file.read(self._plane_size), "raw", "L", 0, 1)
                image = image.convert(mode="RGB")
                image.putalpha(alpha_channel)
            return image

    def close(self):
        self._file.close()
