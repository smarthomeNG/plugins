import hashlib
import os
import socket
import re
from collections import Set


def is_valid_port(port):
    valid_port = re.compile(
        "^(102[4-9]|10[3-9]\d|1[1-9]\d{2}|[2-9]\d{3}|[1-5]\d{4}|6[0-4]\d{3}|65[0-4]\d{2}|655[0-2]\d|6553[0-5])$")
    if valid_port.match(port):
        return True
    return False


def unique_list(seq, idfun=None):
    # order preserving
    if idfun is None:
        def idfun(x): return x
    seen = {}
    result = []
    for item in seq:
        marker = idfun(item)
        # in old Python versions:
        # if seen.has_key(marker)
        # but in new ones:
        if marker in seen: continue
        seen[marker] = 1
        result.append(item)
    return result


def is_open_port(port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", port))
    except socket.error:
        return False
    return True

def get_local_ip_address():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("10.10.10.10", 80))
    return s.getsockname()[0]


def file_size(size):
    _suffixes = ['bytes', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB', 'EiB', 'ZiB', 'YiB']
    # determine binary order in steps of size 10
    # (coerce to int, // still returns a float)
    from math import log2
    order = int(log2(size) / 10) if size else 0
    # format file size
    # (.4g results in rounded numbers for exact matches and max 3 decimals,
    # should never resort to exponent values)
    return '{:.4g} {}'.format(size / (1 << (order * 10)), _suffixes[order])


def get_free_diskspace(folder):
    statvfs = os.statvfs(folder)
    return statvfs.f_frsize * statvfs.f_bfree


def get_folder_size(folder):
    total_size = 0
    for dir_path, dir_names, file_names in os.walk(folder):
        for f in file_names:
            fp = os.path.join(dir_path, f)
            total_size += os.path.getsize(fp)
    return total_size


def get_tts_local_file_path(local_directory, tts_string, tts_language):
    m = hashlib.md5()
    m.update('{}_{}'.format(tts_language, tts_string).encode('utf-8'))
    file_name = '{}.mp3'.format(m.hexdigest())
    return os.path.join(local_directory, file_name)
