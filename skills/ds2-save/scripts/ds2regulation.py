#!/usr/bin/env python3
"""Lê as tabelas de regras (params) do DS2 SotFS direto do enc_regulation.bnd.dcx instalado."""
import struct
import zlib
from pathlib import Path

from ds2save import SaveError, bnd4_entries, game_dirs

KEY = bytes.fromhex("40178130DF0A94543309E171ECBF254C")
FILE_NAME = "enc_regulation.bnd.dcx"

# Só os campos usados pelo buildsmith: nome → (formato struct, offset na linha).
LAYOUTS = {
    "WeaponParam": {"reinforce_id": ("i", 8), "req_str": ("h", 24), "req_dex": ("h", 26), "req_int": ("h", 28), "req_fth": ("h", 30)},
    "WeaponReinforceParam": {"dano_fisico": ("f", 0), "dano_fisico_max": ("f", 36), "nivel_max": ("i", 72),
                             "stats_affect_id": ("i", 76), "mult_fisico": ("f", 160),
                             "dano_magico": ("f", 4), "dano_raio": ("f", 8), "dano_fogo": ("f", 12), "dano_sombrio": ("f", 16),
                             "dano_magico_max": ("f", 40), "dano_raio_max": ("f", 44), "dano_fogo_max": ("f", 48), "dano_sombrio_max": ("f", 52),
                             "mult_magico": ("f", 164), "mult_raio": ("f", 168), "mult_fogo": ("f", 172), "mult_sombrio": ("f", 176)},
    "PhysicalStatsPerLevelStatValuesParam": {"slots": ("B", 2), "faixa": ("B", 3), "bonus_str": ("I", 12), "bonus_dex": ("I", 16),
                                             "bonus_magico": ("I", 20), "bonus_fogo": ("I", 24), "bonus_raio": ("I", 28), "bonus_sombrio": ("I", 32)},
    "SpellParam": {"req_int": ("H", 8), "req_fth": ("H", 10), "damage_id": ("i", 16), "slots": ("B", 240),
                   **{f"usos_{tier}": ("B", 240 + tier) for tier in range(1, 11)}},
    "PlayerDamageParam": {"tipo": ("B", 25), "mult": ("f", 28)},
    "ShopLineupParam": {"item_id": ("i", 0), "material_id": ("i", 16), "price_rate": ("f", 28), "quantidade": ("i", 32)},
    "ItemParam": {"base_price": ("i", 48)},
    "WeaponReinforceCost": {"reinforce_cost_id": ("i", 240)},
}


def scaling_offset(level: int, kind: int) -> int:
    """WeaponStatsAffectParam: 2 floats de cabeçalho e 9 escalas por nível
    (0 = FOR, 1 = DES, 2 = mágico, 3 = raio, 4 = fogo, 5 = sombrio)."""
    return 8 + (level * 9 + kind) * 4


def find_regulation(game_dir=None) -> Path:
    for folder in game_dirs(game_dir):
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
