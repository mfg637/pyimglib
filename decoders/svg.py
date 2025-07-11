#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import io
import subprocess

import PIL.Image
from ..common.utils import InputSourceFacade
from ..common.file_type import svg_tag, is_svg

attributes = re.compile(r'[a-zA-Z\:]+\s?=\s?[\'\"][^\'\"]+[\'\"]')


def get_resolution(file_path):
    data = None
    if isinstance(file_path, (bytes, bytearray)):
        data = file_path.decode()
    else:
        file = open(file_path, 'r')
        data = file.read()
        file.close()
    svg_tag_data = svg_tag.search(data).group(0)
    svg_raw_attributes = attributes.findall(svg_tag_data)
    svg_attributes = dict()
    for raw_attribute in svg_raw_attributes:
        attribute_name, attribute_value = raw_attribute.split('=')
        if attribute_name[-1] == ' ':
            attribute_name = attribute_name[:-1]
        if attribute_value[0] == ' ':
            attribute_value = attribute_value[1:]
        if (attribute_value[0] == '\'' and attribute_value[-1] == '\'') or \
                (attribute_value[0] == '\"' and attribute_value[-1] == '\"'):
            attribute_value = attribute_value[1:-1]
        svg_attributes[attribute_name] = attribute_value
    if 'width' in svg_attributes and 'height' in svg_attributes:
        return (float(svg_attributes['width']), float(svg_attributes['height']))
    elif 'viewBox' in svg_attributes:
        values = svg_attributes['viewBox'].split(' ')
        return (float(values[2]), float(values[3]))
    else:
        return None


def decode(source, required_size=None):
    scale = 1
    source_handler = InputSourceFacade(source, ".svg")
    input_file = source_handler.get_file_str()
    try:
        if required_size is not None:
            width, height = get_resolution(source_handler.get_bytes())
            if (required_size[0] / width * height) <= required_size[1]:
                scale = required_size[0] / width
            else:
                scale = required_size[1] / height
    except ValueError:
        pass
    buffer = None
    buffer = io.BytesIO(subprocess.run(
        ['rsvg-convert', '--format=png', '-z', str(scale), input_file],
        capture_output=True
    ).stdout)
    source_handler.close()
    return PIL.Image.open(buffer)
