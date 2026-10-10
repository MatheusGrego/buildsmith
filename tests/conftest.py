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


def build_bnd4(entries: dict[str, bytes], encrypt: bool = True, unicode: bool = True) -> bytes:
    names = list(entries)
    header = bytearray(0x40)
    header[:4] = b"BND4"
    struct.pack_into("<i", header, 0x0C, len(names))
    struct.pack_into("<q", header, 0x20, 0x20)
    header[0x30] = 1 if unicode else 0
    headers = bytearray(0x20 * len(names))
    names_start = 0x40 + len(headers)
    name_blob, name_offsets = bytearray(), []
    for name in names:
        name_offsets.append(names_start + len(name_blob))
        name_blob += name.encode("utf-16le") + b"\0\0" if unicode else name.encode("ascii") + b"\0"
    data_start = names_start + len(name_blob)
    data_blob = bytearray()
    for i, name in enumerate(names):
        blob = encrypt_entry(entries[name]) if encrypt else entries[name]
        struct.pack_into("<q", headers, i * 0x20 + 0x08, len(blob))
        struct.pack_into("<i", headers, i * 0x20 + 0x10, data_start + len(data_blob))
        struct.pack_into("<i", headers, i * 0x20 + 0x14, name_offsets[i])
        data_blob += blob
    return bytes(header + headers + name_blob + data_blob)


import pytest


@pytest.fixture(scope="session")
def names():
    return ds2save.load_item_names()


def id_of(names, wanted: str) -> int:
    return next(item_id for item_id, (_, name) in names.items() if name == wanted)


def make_slot(name="Teste", level=65, souls=1234, soul_memory=221118, stats=(9, 6, 5, 30, 10, 18, 26, 6, 8)) -> bytearray:
    slot = bytearray(0x11000)
    struct.pack_into("<9H", slot, ds2save.OFF_STATS, *stats)
    struct.pack_into("<3I", slot, ds2save.OFF_LEVEL, level, souls, soul_memory)
    encoded = name.encode("utf-16le")
    slot[ds2save.OFF_NAME : ds2save.OFF_NAME + len(encoded)] = encoded
    for off, count in ((ds2save.OFF_HANDS, 6), (ds2save.OFF_ARMOR, 4), (ds2save.OFF_RINGS, 4), (ds2save.OFF_SPELLS, ds2save.SPELL_SLOTS)):
        for i in range(count):
            struct.pack_into("<I", slot, off + 4 * i, 0xFFFFFFFF)
    return slot


@pytest.fixture
def save_file(tmp_path, names):
    slot = make_slot(name="Melatonina Vorcaro")
    uchi, staff = id_of(names, "Uchigatana"), id_of(names, "Sorcerer's Staff")
    struct.pack_into("<2I", slot, ds2save.OFF_HANDS, staff, uchi)  # L1, R1
    struct.pack_into("<I", slot, ds2save.OFF_RINGS, id_of(names, "Clear Bluestone Ring"))
    struct.pack_into("<I", slot, ds2save.OFF_SPELLS, id_of(names, "Soul Arrow"))
    struct.pack_into("<IIfI", slot, ds2save.OFF_INVENTORY, uchi, 0, 40.0, 5)
    struct.pack_into("<4I", slot, ds2save.OFF_INVENTORY + 16, id_of(names, "Human Effigy"), 0, 15, 0)
    struct.pack_into("<4I", slot, ds2save.OFF_INVENTORY + 32, 12345678, 0, 1, 0)
    struct.pack_into("<4I", slot, ds2save.OFF_KEY_ITEMS + 16, 0, id_of(names, "Soldier Key"), 0, 1)
    path = tmp_path / "DS2SOFS0000.sl2"
    path.write_bytes(build_bnd4({"USER_DATA000": bytes(0x100), "USER_DATA001": bytes(slot), "USER_DATA002": bytes(0x11000),
                                 "USER_DATA011": bytes(0x30000)}))
    return path


def set_flags(world: bytearray, flags) -> None:
    for flag in flags:
        k = flag - ds2save.FLAG_BASE_ID
        world[ds2save.FLAG_BASE_OFFSET + k // 8] |= 0x80 >> (k % 8)


@pytest.fixture
def world_save(tmp_path, names):
    """Save com 1 personagem, flags de mundo e histórico de compras."""
    slot = make_slot(name="Melatonina Vorcaro")
    struct.pack_into("<6I", slot, ds2save.OFF_SHOP, 76600301, 1, 76430000, 1, 0, 0)
    world = bytearray(0x30000)
    set_flags(world, [100968, 100971, 102480])  # Pursuer, Last Giant, flag sem nome
    path = tmp_path / "DS2SOFS0000.sl2"
    path.write_bytes(build_bnd4({"USER_DATA001": bytes(slot), "USER_DATA011": bytes(world)}))
    return path


@pytest.fixture(autouse=True)
def sem_jogo_no_prepare(monkeypatch):
    """prepare_page sem área injetada não lê o jogo instalado nos testes (seria lento e dependeria da máquina)."""
    import prepare_page

    def sem_jogo(*args, **kwargs):
        raise OSError("jogo desligado nos testes")

    monkeypatch.setattr(prepare_page, "_jogo_instalado", sem_jogo)
    monkeypatch.setattr(prepare_page, "area_do_jogador_real", prepare_page.area_do_jogador, raising=False)
    monkeypatch.setattr(prepare_page, "area_do_jogador", lambda plano: None)
