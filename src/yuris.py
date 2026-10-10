from pathlib import Path
import struct
import zlib

KEY = bytes.fromhex('d36fac96')
from paths import ROOT, SOURCE_ROOT

def read_archive(path):
    data = path.read_bytes()
    assert data[:8] == b'YPF\0\xef\x01\0\0'
    pos = 32
    result = {}
    for _ in range(struct.unpack_from('<I', data, 8)[0]):
        start = pos
        pos += 5
        end = data.find(bytes(x ^ 255 for x in b'.ybn'), pos, pos + 64) + 4
        assert end > pos
        name = bytes(x ^ 255 for x in data[pos:end]).decode('cp932')
        pos = end
        kind, compressed, size, packed, offset, crc = struct.unpack_from('<BBIIQI', data, pos)
        pos += 22
        payload = data[offset:offset + packed]
        if compressed:
            payload = zlib.decompress(payload)
        assert len(payload) == size
        result[name] = (payload, data[start:pos])
    return result

def split_ybn(data):
    assert data[:4] == b'YSTB'
    pos = 32
    parts = []
    for size in struct.unpack_from('<4I', data, 12):
        parts.append(bytes(x ^ KEY[i % 4] for i, x in enumerate(data[pos:pos + size])))
        pos += size
    assert pos == len(data)
    return parts

def build_ybn(original, parts):
    header = bytearray(original[:32])
    struct.pack_into('<4I', header, 12, *(len(p) for p in parts))
    return bytes(header) + b''.join(bytes(x ^ KEY[i % 4] for i, x in enumerate(p)) for p in parts)

def args(parts):
    for pos in range(0, len(parts[1]), 12):
        kind, size, offset = struct.unpack_from('<III', parts[1], pos)
        yield pos // 12, kind, offset, parts[2][offset:offset + size]

def current():
    return read_archive(next(ROOT.rglob('update1.ypf')))
