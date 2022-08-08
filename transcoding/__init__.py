#!/usr/bin/python3
# -*- coding: utf-8 -*-

import os
import pathlib

from . import statistics,\
    gif_source_transcode,\
    png_source_transcode,\
    jpeg_source_transcode,\
    jpeg_xl_transcoder,\
    srs_video,\
    common,\
    srs_svg,\
    encoders

from .. import config, decoders

import logging
from .. import exceptions

logger = logging.getLogger(__name__)


# derpibooru-dl only
def check_exists(source, path, filename):
    fname = os.path.join(path, filename)
    if os.path.splitext(source)[1].lower() == '.png':
        return os.path.isfile(fname + '.webp') \
               or os.path.isfile(fname + '.webm') \
               or os.path.isfile(fname + '.avif')
    elif os.path.splitext(source)[1].lower() in {'.jpg', '.jpeg'}:
        return os.path.isfile(fname + '.webp')
    elif os.path.splitext(source)[1].lower() == '.gif':
        return os.path.isfile(fname + '.webp') or os.path.isfile(fname+'.webm')


def get_file_transcoder(
        source: str, path: pathlib.Path, filename: str, force_lossless=False, tags: dict = dict(), metadata=dict()
    ):
    if os.path.splitext(source)[1].lower() == '.png':
        if config.preferred_codec == config.PREFERRED_CODEC.SRS:
            return png_source_transcode.SRS_PNGFileTranscode(source, path, filename, tags, metadata)
        elif config.preferred_codec == config.PREFERRED_CODEC.AVIF:
            png_transcoder = png_source_transcode.PNGFileTranscode(source, path, filename, force_lossless)
            png_transcoder.lossy_encoder_type = encoders.avif_encoder.AVIFEncoder
            png_transcoder.lossless_encoder_type = encoders.avif_encoder.AVIFLosslessEncoder
            png_transcoder.animation_encoder_type = encoders.webm_encoder.AV1Encoder
            return png_transcoder
        elif config.preferred_codec == config.PREFERRED_CODEC.WEBP or config.preferred_codec is None:
            png_transcoder = png_source_transcode.PNGFileTranscode(source, path, filename, force_lossless)
            png_transcoder.lossless_encoder_type = encoders.webp_encoder.WEBPLosslessEncoder
            png_transcoder.lossy_encoder_type = encoders.webp_encoder.WEBPEncoder
            png_transcoder.animation_encoder_type = encoders.webm_encoder.VP9Encoder
            return png_transcoder
    elif os.path.splitext(source)[1].lower() in {'.jpg', '.jpeg'}:
        # if config.jpeg_xl_tools_path is not None:
        if config.preferred_codec == config.PREFERRED_CODEC.SRS:
            return jpeg_source_transcode.SRS_JPEGFileTranscode(source, path, filename, tags, metadata)
        elif config.preferred_codec == config.PREFERRED_CODEC.AVIF:
            jpeg_transcoder = jpeg_source_transcode.JPEGFileTranscode(source, path, filename)
            jpeg_transcoder.lossy_encoder_type = encoders.avif_encoder.AVIFEncoder
            return jpeg_transcoder
        elif config.preferred_codec == config.PREFERRED_CODEC.WEBP or config.preferred_codec is None:
            jpeg_transcoder = jpeg_source_transcode.JPEGFileTranscode(source, path, filename)
            jpeg_transcoder.lossy_encoder_type = encoders.webp_encoder.WEBPEncoder
            return jpeg_transcoder
        # else:
        #     if config.preferred_codec == config.PREFERRED_CODEC.SRS:
        #         return jpeg_source_transcode.SRS_JPEGFileTranscode(source, path, filename, tags, metadata)
        #     elif config.preferred_codec == config.PREFERRED_CODEC.AVIF:
        #         return jpeg_source_transcode.JPEGFileTranscode(source, path, filename)
        #     elif config.PREFERRED_CODEC.WEBP:
        #         return jpeg_source_transcode.JPEGFileTranscode(source, path, filename)
        #     else:
        #         return jpeg_source_transcode.JPEGFileTranscode(source, path, filename)
    elif os.path.splitext(source)[1].lower() == '.gif':
        return gif_source_transcode.GIFFileTranscode(source, path, filename, tags)


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
        source: bytearray, path: str, filename: str, force_lossless=False, tags: dict = dict(), metadata={}
):
    if isPNG(source):
        if config.preferred_codec == config.PREFERRED_CODEC.SRS:
            return png_source_transcode.SRS_PNGInMemoryTranscode(source, path, filename, tags, metadata)
        elif config.preferred_codec == config.PREFERRED_CODEC.AVIF:
            png_transcoder = png_source_transcode.PNGInMemoryTranscode(source, path, filename, force_lossless)
            png_transcoder.lossy_encoder_type = encoders.avif_encoder.AVIFEncoder
            png_transcoder.lossless_encoder_type = encoders.avif_encoder.AVIFLosslessEncoder
            png_transcoder.animation_encoder_type = encoders.webm_encoder.AV1Encoder
            return png_transcoder
        elif config.preferred_codec == config.PREFERRED_CODEC.WEBP or config.preferred_codec is None:
            png_transcoder = png_source_transcode.PNGInMemoryTranscode(source, path, filename, force_lossless)
            png_transcoder.lossless_encoder_type = encoders.webp_encoder.WEBPLosslessEncoder
            png_transcoder.lossy_encoder_type = encoders.webp_encoder.WEBPEncoder
            return png_transcoder
    elif isJPEG(source):
        if config.jpeg_xl_tools_path is not None:
            if config.preferred_codec == config.PREFERRED_CODEC.SRS:
                return jpeg_source_transcode.SRS_JPEGInMemoryTranscode(source, path, filename, tags, metadata)
            elif config.preferred_codec == config.PREFERRED_CODEC.AVIF:
                return jpeg_xl_transcoder.AVIF_JPEG_XL_BufferTranscode(source, path, filename, tags)
            elif config.PREFERRED_CODEC.WEBP:
                return jpeg_xl_transcoder.JPEG_XL_BurrefedSourceTranscoder(source, path, filename, tags)
            else:
                return jpeg_xl_transcoder.JPEG_XL_BurrefedSourceTranscoder(source, path, filename, tags)
        else:
            if config.preferred_codec == config.PREFERRED_CODEC.SRS:
                return jpeg_source_transcode.SRS_JPEGInMemoryTranscode(source, path, filename, tags, metadata)
            elif config.preferred_codec == config.PREFERRED_CODEC.AVIF:
                return jpeg_source_transcode.AVIF_JPEGInMemoryTranscode(source, path, filename, tags)
            elif config.PREFERRED_CODEC.WEBP:
                return jpeg_source_transcode.JPEGInMemoryTranscode(source, path, filename, tags)
            else:
                return jpeg_source_transcode.JPEGInMemoryTranscode(source, path, filename, tags)
    elif isGIF(source):
        if config.preferred_codec == config.PREFERRED_CODEC.SRS:
            return gif_source_transcode.SRS_GIFInMemoryTranscode(source, path, filename, tags, metadata)
        else:
            return gif_source_transcode.GIFInMemoryTranscode(source, path, filename, tags)
    elif bytes(source[:4]) in decoders.video.MKV_HEADER:
        if config.preferred_codec == config.PREFERRED_CODEC.SRS:
            return srs_video.SRS_WEBM_Converter(source, path, filename, tags, metadata)
        else:
            return srs_video.WEBM_WRITER(source, path, filename, tags)
    elif b"<svg" in source:
        if config.preferred_codec == config.PREFERRED_CODEC.SRS:
            return srs_svg.SRS_SVG_Converter(source, path, filename, tags, metadata)
        else:
            return srs_svg.SVG_WRITER(source, path, filename, tags)
    else:
        logger.error("NON IDENTIFIED FILE FORMAT", source[:16])
        raise exceptions.NotIdentifiedFileFormat()
