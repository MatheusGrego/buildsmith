import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "ds2-save" / "scripts"))
sys.path.insert(0, str(ROOT / "skills" / "build-page" / "scripts"))

import hashlib
import struct

from Crypto.Cipher import AES

import ds2save


def encrypt_entry(plain: bytes) -> bytes:
    iv = bytes(range(16))
    body = AES.new(ds2save.KEY, AES.MODE_CBC, iv).encrypt(plain + b"\0" * ((-len(plain)) % 16))
    return hashlib.md5(iv + body).digest() + iv + body


def build_bnd4(entries: dict[str, bytes]) -> bytes:
    names = list(entries)
    header = bytearray(0x40)
    header[:4] = b"BND4"
    struct.pack_into("<i", header, 0x0C, len(names))
    struct.pack_into("<q", header, 0x20, 0x20)
    headers = bytearray(0x20 * len(names))
    names_start = 0x40 + len(headers)
    name_blob, name_offsets = bytearray(), []
    for name in names:
        name_offsets.append(names_start + len(name_blob))
        name_blob += name.encode("utf-16le") + b"\0\0"
    data_start = names_start + len(name_blob)
    data_blob = bytearray()
    for i, name in enumerate(names):
        blob = encrypt_entry(entries[name])
        struct.pack_into("<q", headers, i * 0x20 + 0x08, len(blob))
        struct.pack_into("<i", headers, i * 0x20 + 0x10, data_start + len(data_blob))
        struct.pack_into("<i", headers, i * 0x20 + 0x14, name_offsets[i])
        data_blob += blob
    return bytes(header + headers + name_blob + data_blob)
