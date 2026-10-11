import json

import ds2save
from conftest import build_bnd4


def _save(tmp_path, nome, mundo, slot):
    caminho = tmp_path / nome
    caminho.write_bytes(build_bnd4({"USER_DATA001": bytes(slot), "USER_DATA011": bytes(mundo)}))
    return caminho


def _par(tmp_path):
    mundo, slot = bytearray(4096), bytearray(512)
    antes = _save(tmp_path, "antes.sl2", mundo, slot)
    mundo[100] |= 0x80          # bit 0 (o mais alto, como as flags do jogo)
    mundo[101] |= 0x01          # bit 7
    mundo[3000] |= 0x10         # bit 3
    slot[40] = 0xFF             # um byte inteiro (contador, quantidade...)
    depois = _save(tmp_path, "depois.sl2", mundo, slot)
    return antes, depois


def test_diff_finds_each_flipped_bit_and_byte(tmp_path):
    antes, depois = _par(tmp_path)
    mudancas = ds2save.diff_blocos(ds2save.blocos(antes), ds2save.blocos(depois))
    assert mudancas == [
        {"bloco": "USER_DATA001", "offset": 40, "bit": None, "antes": 0, "depois": 0xFF},
        {"bloco": "USER_DATA011", "offset": 100, "bit": 0, "antes": 0, "depois": 0x80},
        {"bloco": "USER_DATA011", "offset": 101, "bit": 7, "antes": 0, "depois": 0x01},
        {"bloco": "USER_DATA011", "offset": 3000, "bit": 3, "antes": 0, "depois": 0x10},
    ]


def test_blocks_come_decrypted(tmp_path):
    antes, _ = _par(tmp_path)
    blocos = ds2save.blocos(antes)
    assert set(blocos) == {"USER_DATA001", "USER_DATA011"}
    assert blocos["USER_DATA011"][:4096] == bytes(4096)


def test_cli_groups_by_block_and_filters(tmp_path, capsys):
    antes, depois = _par(tmp_path)
    assert ds2save.main(["blocos-diff", "--antes", str(antes), "--depois", str(depois), "--bloco", "USER_DATA011"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert list(out) == ["USER_DATA011"]
    assert [m["offset"] for m in out["USER_DATA011"]] == [100, 101, 3000]
