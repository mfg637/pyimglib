#!/usr/bin/python3
# -*- coding: utf-8 -*-

import logging
import os
import pathlib

from . import (
    statistics,
    gif_source_transcode,
    png_source_transcode,
    jpeg_source_transcode,
    video_transcoder,
    video_loop_transcoder,
    svg_source_encoder,
    encoders
)

from .. import config
from .. import exceptions
from .. import common
from ..common import file_type

logger = logging.getLogger(__name__)


# derpibooru-dl exclusive
def get_trancoded_file(source: pathlib.Path, path: pathlib.Path, filename: str):
    fname = path.joinpath(filename)
    suffixes: list[str] = ['.webp', '.webm', '.avif', '.mpd', '.srs', ".svg"]
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
        source: bytearray,
        path: pathlib.Path,
        filename: str,
        force_lossless=False,
        rewrite=False,
):
    from ..decoders.video import MKV_HEADER
    if isPNG(source):
        png_transcoder = png_source_transcode.PNGInMemoryTranscode(
            source, path, filename, rewrite, force_lossless
        )
        png_transcoder.animation_encoder_type = config.png_source_encoders["animation_encoder"]
        png_transcoder.lossless_encoder_type = config.png_source_encoders["lossless_encoder"]
        png_transcoder.lossy_encoder_type = config.png_source_encoders["lossy_encoder"]
        return png_transcoder
    elif isJPEG(source):
        jpeg_transcoder = jpeg_source_transcode.JPEGInMemoryTranscode(source, path, filename)
        jpeg_transcoder.lossy_encoder_type = config.jpeg_source_encoders["lossy_encoder"]
        jpeg_transcoder.lossless_jpeg_transcoder_type = config.jpeg_source_encoders["lossless_transcoder"]
        return jpeg_transcoder
    elif isGIF(source):
        gif_transcoder = gif_source_transcode.GIFInMemoryTranscode(source, path, filename, rewrite)
        gif_transcoder.lossy_encoder_type = config.gif_source_encoders["lossy_encoder"]
        gif_transcoder.animation_encoder_type = config.gif_source_encoders["animation_encoder"]
        return gif_transcoder
    elif file_type.is_svg(source):
        if config.render_svg:
            svg_transcoder = svg_source_encoder.InMemorySVGEncoder(
                source, path, filename
            )
            svg_transcoder.animation_encoder_type = \
                config.png_source_encoders["animation_encoder"]
            svg_transcoder.lossless_encoder_type = \
                config.png_source_encoders["lossless_encoder"]
            svg_transcoder.lossy_encoder_type = \
                config.png_source_encoders["lossy_encoder"]
            return svg_transcoder
        else:
            svg_writer = svg_source_encoder.SVGWriter(source, path, filename)
            return svg_writer
    elif bytes(source[:4]) in MKV_HEADER:
        src_metadata = common.ffmpeg.probe(source)
        if common.ffmpeg.parser.test_videoloop(src_metadata):
            if common.ffmpeg.parser.test_video_cl3(src_metadata):
                v_writer = video_transcoder.VideoWriter(
                    source, path, filename, ".webm"
                )
                return v_writer
            else:
                vloop_transcoder = video_loop_transcoder.VideoLoopTranscoder(
                    source, path, filename, rewrite
                )
                return vloop_transcoder
        elif issubclass(
            config.video_encoders["video_encoder"],
            encoders.encoder.FilesEncoder
        ):
            v_transcoder = video_transcoder.VideoTranscoder(
                source, path, filename
            )
            v_transcoder.video_encoder_type = \
                config.video_encoders["video_encoder"]
            return v_transcoder
        else:
            v_writer = video_transcoder.VideoWriter(
                source, path, filename, ".webm"
            )
            return v_writer
    else:
        logger.error("NON IDENTIFIED FILE FORMAT", source[:16])
        raise exceptions.NotIdentifiedFileFormat()
