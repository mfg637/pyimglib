#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import subprocess, json
from . import exceptions
from platform import system


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
        commandline = ['ffprobe', '-loglevel', '24', '-hide_banner', '-print_format', 'json',
                       '-show_format', '-show_streams', '-show_chapters', source]
        return json.loads(str(get_output(commandline), 'utf-8'))
    except UnicodeEncodeError:
        raise exceptions.InvalidFilename(source)
