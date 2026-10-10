"""Lossless YPF image export and local translation-review gallery.

YPF length-swap table/format reference: morkt/GARbro ArcFormats/YuRis/ArcYPF.cs
(MIT license; copyright and permission notice in LICENSES/GARbro.txt).
"""
from pathlib import Path, PureWindowsPath
from concurrent.futures import ThreadPoolExecutor
from collections import Counter
from PIL import Image
import csv
import hashlib
import io
import json
import struct
import zlib

PAIRS = bytes.fromhex('034806350c1011191c1e090b0d13151b202326292c2f2e32')
SWAP = {PAIRS[i]: PAIRS[i ^ 1] for i in range(len(PAIRS))}

def index(archive):
    entries = []
    with archive.open('rb') as f:
        header = f.read(32)
        assert header[:4] == b'YPF\0'
        version, count, end = struct.unpack_from('<III', header, 4)
        assert version == 495, version
        for _ in range(count):
            prefix = f.read(5)
            length = SWAP.get(prefix[4] ^ 255, prefix[4] ^ 255)
            name = bytes(x ^ 255 for x in f.read(length)).decode('cp932')
            kind, compressed, size, packed, offset, checksum = struct.unpack('<BBIIQI', f.read(22))
            assert compressed in (0, 1) and offset + packed <= archive.stat().st_size
            entries.append(dict(name=name, kind=kind, compressed=compressed, size=size,
                                packed=packed, offset=offset))
        assert f.tell() == end
    return entries


def safe_relative(name):
    p = PureWindowsPath(name)
    assert not p.is_absolute() and not p.drive and '..' not in p.parts
    return Path(*p.parts)
