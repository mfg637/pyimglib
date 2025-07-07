#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import pathlib
import subprocess
import logging
from platform import system

from . import exceptions
from ..utils import InputSourceFacade

if system() == "Windows":
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW


def get_output(commandline):
    global si
    if system() == "Windows":
        try:
            return subprocess.check_output(commandline, startupinfo=si)
        except OSError:
            si = None
            return subprocess.check_output(commandline)
    else:
        return subprocess.check_output(commandline)


def probe(source: bytearray | pathlib.Path | str):
    """
    Probes a media file using ffprobe and returns its metadata as a dictionary.

    Parameters:
        source (bytearray | pathlib.Path | str): The media source to probe.
        Can be a file path (as a string or pathlib.Path)
        or a bytearray containing the file data.

    Returns:
        dict: Parsed JSON output from ffprobe containing media metadata
        (format, streams, chapters, etc.).

    Raises:
        exceptions.InvalidFilename:
        If the source filename contains invalid characters
        or cannot be encoded.

    Notes:
        - If a bytearray is provided,
            it is written to a temporary file for probing.
        - The function ensures temporary files are cleaned up after use.
    """
    source_handler = InputSourceFacade(source)
    input_file = source_handler.get_file_str()

    result = None
    try:
        commandline = ['ffprobe']
        commandline += set_loglevel(logging.root.level)
        commandline += [
            '-print_format', 'json',
            '-show_format',
            '-show_streams',
            '-show_chapters',
            input_file
        ]
        result = json.loads(str(get_output(commandline), 'utf-8'))
    except UnicodeEncodeError:
        raise exceptions.InvalidFilename(source)
    finally:
        source_handler.close()
    return result


def set_loglevel(loglevel):
    commandline = ["-loglevel"]
    match loglevel:
        case logging.DEBUG:
            commandline += ["debug"]
        case logging.INFO:
            commandline += ["info"]
        case logging.WARNING:
            commandline += ["warning", '-hide_banner']
        case logging.ERROR:
            commandline += ["error", '-hide_banner']
        case logging.CRITICAL:
            commandline += ["fatal", '-hide_banner']
        case _:
            commandline += ["quiet", '-hide_banner']
    return commandline
