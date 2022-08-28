#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import subprocess
import logging
from platform import system

from . import exceptions, parser

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


def probe(source):
    try:
        commandline = ['ffprobe']
        commandline += set_loglevel(logging.root.level)
        commandline += ['-print_format', 'json', '-show_format', '-show_streams', '-show_chapters', source]
        return json.loads(str(get_output(commandline), 'utf-8'))
    except UnicodeEncodeError:
        raise exceptions.InvalidFilename(source)


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
            commandline += ["quite", '-hide_banner']
    return commandline
