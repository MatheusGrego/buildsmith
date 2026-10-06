#!/usr/bin/env python3
"""Lê as tabelas de regras (params) do DS2 SotFS direto do enc_regulation.bnd.dcx instalado."""
import os
import struct
import zlib
from pathlib import Path

from ds2save import SaveError, bnd4_entries

KEY = bytes.fromhex("40178130DF0A94543309E171ECBF254C")
GAME_DIRS = [
    Path(r"C:\Program Files (x86)\Steam\steamapps\common\Dark Souls II Scholar of the First Sin\Game"),
    Path(r"C:\Program Files\Steam\steamapps\common\Dark Souls II Scholar of the First Sin\Game"),
]
FILE_NAME = "enc_regulation.bnd.dcx"

# Só os campos usados pelo buildsmith: nome → (formato struct, offset na linha).
LAYOUTS = {
    "WeaponParam": {"reinforce_id": ("i", 8), "req_str": ("h", 24), "req_dex": ("h", 26), "req_int": ("h", 28), "req_fth": ("h", 30)},
    "WeaponReinforceParam": {"dano_fisico": ("f", 0), "dano_fisico_max": ("f", 36), "nivel_max": ("i", 72),
                             "stats_affect_id": ("i", 76), "mult_fisico": ("f", 160)},
    "PhysicalStatsPerLevelStatValuesParam": {"bonus_str": ("I", 12), "bonus_dex": ("I", 16)},
    "ShopLineupParam": {"item_id": ("i", 0), "quantidade": ("i", 32)},
}


def scaling_offset(level: int, kind: int) -> int:
    """WeaponStatsAffectParam: 2 floats de cabeçalho e 9 escalas por nível (0 = FOR, 1 = DES)."""
    return 8 + (level * 9 + kind) * 4


def find_regulation(game_dir=None) -> Path:
    candidates = [Path(game_dir)] if game_dir else []
    if os.environ.get("BUILDSMITH_DS2_GAME"):
        candidates.append(Path(os.environ["BUILDSMITH_DS2_GAME"]))
    if not game_dir:
        candidates += GAME_DIRS
    for folder in candidates:
        if (folder / FILE_NAME).exists():
            return folder / FILE_NAME
    raise SaveError(f"não achei {FILE_NAME}; defina BUILDSMITH_DS2_GAME com a pasta Game do DS2")


def decrypt(data: bytes) -> bytes:
    from Crypto.Cipher import AES
    from Crypto.Util import Counter

    iv = bytes([0x80]) + data[:11] + b"\x00\x00\x00\x01"
    counter = Counter.new(128, initial_value=int.from_bytes(iv, "big"))
    return AES.new(KEY, AES.MODE_CTR, counter=counter).decrypt(data[32:])


def decompress_dcx(data: bytes) -> bytes:
    if data[:4] != b"DCX\x00" or b"DCA\x00" not in data[:0x80]:
        raise SaveError("regulation em formato inesperado (DCX não reconhecido)")
    dca = data.index(b"DCA\x00")
    start = dca + struct.unpack_from(">I", data, dca + 4)[0]
    try:
        return zlib.decompress(data[start:])
    except zlib.error as err:
        raise SaveError(f"regulation em formato inesperado ({err})") from err


def load_params(path=None) -> dict[str, bytes]:
    """Nome do param (sem extensão) → bytes do arquivo .param."""
    raw = Path(path or find_regulation()).read_bytes()
    entries = bnd4_entries(decompress_dcx(decrypt(raw)))
    return {name.replace("\\", "/").rsplit("/", 1)[-1][: -len(".param")]: blob
            for name, blob in entries.items() if name.endswith(".param")}


def param_rows(data: bytes, layout: dict[str, tuple[str, int]]) -> dict[int, dict]:
    count = struct.unpack_from("<H", data, 0x0A)[0]
    rows = {}
    for i in range(count):
        row_id, offset, _ = struct.unpack_from("<QQQ", data, 0x40 + 24 * i)
        rows[row_id] = {name: struct.unpack_from("<" + fmt, data, offset + pos)[0] for name, (fmt, pos) in layout.items()}
    return rows
