import struct
import zlib

import pytest
from Crypto.Cipher import AES
from Crypto.Util import Counter

import ds2regulation
from conftest import build_bnd4


def build_param(rows: dict[int, bytes]) -> bytes:
    """PARAM do DS2: cabeçalho de 0x40, linhas de 24 bytes, dados em seguida."""
    ids = sorted(rows)
    header = bytearray(0x40)
    struct.pack_into("<H", header, 0x0A, len(ids))
    table = bytearray(24 * len(ids))
    data = bytearray()
    start = 0x40 + len(table)
    for i, rid in enumerate(ids):
        struct.pack_into("<QQQ", table, 24 * i, rid, start + len(data), 0)
        data += rows[rid]
    return bytes(header + table + data)


def build_dcx(payload: bytes) -> bytes:
    body = zlib.compress(payload)
    head = b"DCX\x00" + bytes(0x14) + b"DCS\x00" + struct.pack(">II", len(payload), len(body))
    head += b"DCP\x00DFLT" + bytes(0x18) + b"DCA\x00" + struct.pack(">I", 8)
    return head + body


def encrypt_regulation(dcx: bytes) -> bytes:
    prefix = bytes(range(32))
    iv = bytes([0x80]) + prefix[:11] + b"\x00\x00\x00\x01"
    ctr = Counter.new(128, initial_value=int.from_bytes(iv, "big"))
    return prefix + AES.new(ds2regulation.KEY, AES.MODE_CTR, counter=ctr).encrypt(dcx)


def regulation_file(tmp_path, params: dict[str, bytes]):
    bnd = build_bnd4({f"N:/FRPG2/data/Param/{k}": v for k, v in params.items()}, encrypt=False, unicode=False)
    path = tmp_path / "enc_regulation.bnd.dcx"
    path.write_bytes(encrypt_regulation(build_dcx(bnd)))
    return path


def test_round_trip_reads_params(tmp_path):
    row = struct.pack("<ii", 7, 99)
    path = regulation_file(tmp_path, {"TesteParam.param": build_param({10: row, 20: row})})
    params = ds2regulation.load_params(path)
    assert set(params) == {"TesteParam"}
    rows = ds2regulation.param_rows(params["TesteParam"], {"a": ("i", 0), "b": ("i", 4)})
    assert rows == {10: {"a": 7, "b": 99}, 20: {"a": 7, "b": 99}}


def test_not_dcx_is_rejected(tmp_path):
    path = tmp_path / "enc_regulation.bnd.dcx"
    path.write_bytes(bytes(64))
    with pytest.raises(ds2regulation.SaveError):
        ds2regulation.load_params(path)


def test_missing_regulation_is_reported(tmp_path):
    with pytest.raises(ds2regulation.SaveError, match="enc_regulation"):
        ds2regulation.find_regulation(tmp_path)


def _real():
    try:
        return ds2regulation.find_regulation()
    except ds2regulation.SaveError:
        return None


@pytest.mark.skipif(_real() is None, reason="DS2 não instalado nesta máquina")
def test_real_uchigatana_reinforce():
    params = ds2regulation.load_params(_real())
    weapons = ds2regulation.param_rows(params["WeaponParam"], ds2regulation.LAYOUTS["WeaponParam"])
    reinforce = ds2regulation.param_rows(params["WeaponReinforceParam"], ds2regulation.LAYOUTS["WeaponReinforceParam"])
    row = reinforce[weapons[1700000]["reinforce_id"]]
    assert (row["dano_fisico"], row["dano_fisico_max"], row["nivel_max"]) == (115.0, 230.0, 10)
    assert weapons[1700000]["req_str"] == 10 and weapons[1700000]["req_dex"] == 16
