#!/usr/bin/python3
# -*- coding: utf-8 -*-

import logging
import os
import pathlib

from . import statistics, \
    gif_source_transcode, \
    png_source_transcode, \
    jpeg_source_transcode, \
    common, \
    video_transcoder, \
    encoders

from .. import config
from .. import exceptions

logger = logging.getLogger(__name__)


# derpibooru-dl exclusive
def get_trancoded_file(source: pathlib.Path, path: pathlib.Path, filename: str):
    fname = path.joinpath(filename)
    suffixes: list[str] = ['.webp', '.webm', '.avif', '.mpd', '.srs']
    for suffix in suffixes:
        filepath = fname.with_suffix(suffix)
        if filepath.is_file():
            return filepath
    return None

def get_file_transcoder(
        source: pathlib.Path, path: pathlib.Path, filename: str, force_lossless=False
    ):
    if source.suffix.lower() == '.png':
        png_transcoder = png_source_transcode.PNGFileTranscode(source, path, filename, force_lossless)
        png_transcoder.animation_encoder_type = config.png_source_encoders["animation_encoder"]
        png_transcoder.lossless_encoder_type = config.png_source_encoders["lossless_encoder"]
        png_transcoder.lossy_encoder_type = config.png_source_encoders["lossy_encoder"]
        return png_transcoder
    elif source.suffix.lower() in {'.jpg', '.jpeg'}:
        # if config.jpeg_xl_tools_path is not None:
        jpeg_transcoder = jpeg_source_transcode.JPEGFileTranscode(source, path, filename)
        jpeg_transcoder.lossy_encoder_type = config.jpeg_source_encoders["lossy_encoder"]
        return jpeg_transcoder
    elif source.suffix.lower() == '.gif':
        gif_transcoder = gif_source_transcode.GIFFileTranscode(source, path, filename)
        gif_transcoder.lossy_encoder_type = config.gif_source_encoders["lossy_encoder"]
        gif_transcoder.animation_encoder_type = config.gif_source_encoders["animation_encoder"]
        return gif_transcoder
    elif os.path.splitext(source)[1].lower() in {".webm", ".mp4", ".mkv"}:
        if issubclass(config.video_encoders["video_encoder"], encoders.dash_encoder.DASHEncoder):
            v_transcoder = video_transcoder.VideoTranscoder(source, path, filename)
            v_transcoder.video_encoder_type = config.video_encoders["video_encoder"]
            return v_transcoder
        else:
            v_writer = video_transcoder.VideoWriter(source, path, filename, os.path.splitext(source)[1].lower())
            return v_writer


PNG_HEADER = b'\x89PNG'
JPEG_HEADER = b'\xff\xd8'
GIF_HEADERS = {b'GIF87a', b'GIF89a'}


def isPNG(data: bytearray) -> bool:
    return data[:4] == PNG_HEADER


def isJPEG(data: bytearray) -> bool:
    return data[:2] == JPEG_HEADER


def isGIF(data: bytearray) -> bool:
    return bytes(data[:6]) in GIF_HEADERS


def get_memory_transcoder(
        source: bytearray, path: pathlib.Path, filename: str, force_lossless=False
):
    from ..decoders.video import MKV_HEADER
    if isPNG(source):
        png_transcoder = png_source_transcode.PNGInMemoryTranscode(source, path, filename, force_lossless)
        png_transcoder.animation_encoder_type = config.png_source_encoders["animation_encoder"]
        png_transcoder.lossless_encoder_type = config.png_source_encoders["lossless_encoder"]
        png_transcoder.lossy_encoder_type = config.png_source_encoders["lossy_encoder"]
        return png_transcoder
    elif isJPEG(source):
        jpeg_transcoder = jpeg_source_transcode.JPEGInMemoryTranscode(source, path, filename)
        jpeg_transcoder.lossy_encoder_type = config.jpeg_source_encoders["lossy_encoder"]
        return jpeg_transcoder
    elif isGIF(source):
        gif_transcoder = gif_source_transcode.GIFInMemoryTranscode(source, path, filename)
        gif_transcoder.lossy_encoder_type = config.gif_source_encoders["lossy_encoder"]
        gif_transcoder.animation_encoder_type = config.gif_source_encoders["animation_encoder"]
        return gif_transcoder
    elif bytes(source[:4]) in MKV_HEADER:
        if issubclass(config.video_encoders["video_encoder"], encoders.dash_encoder.DASHEncoder):
            v_transcoder = video_transcoder.VideoTranscoder(source, path, filename)
            v_transcoder.video_encoder_type = config.video_encoders["video_encoder"]
            return v_transcoder
        else:
            v_writer = video_transcoder.VideoWriter(source, path, filename, ".webm")
            return v_writer
    else:
        logger.error("NON IDENTIFIED FILE FORMAT", source[:16])
        raise exceptions.NotIdentifiedFileFormat()
