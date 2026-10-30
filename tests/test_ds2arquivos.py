import os
import struct
import zlib
from pathlib import Path

import pytest
from Crypto.Cipher import AES
from Crypto.PublicKey import RSA

import ds2arquivos

GAME = ds2arquivos.game_dir_padrao()  # o jogo instalado (Windows ou Linux); None sem ele


def dcx(payload: bytes) -> bytes:
    body = zlib.compress(payload)
    head = b"DCX" + bytes(1) + bytes(0x14) + b"DCS" + bytes(1) + struct.pack(">II", len(payload), len(body))
    return head + b"DCP" + bytes(1) + b"DFLT" + bytes(0x18) + b"DCA" + bytes(1) + struct.pack(">I", 8) + body


def hash_manual(path: str) -> int:
    h = 0
    for ch in path.lower():
        h = (h * 37 + ord(ch)) % 2 ** 32
    return h


@pytest.fixture(scope="module")
def jogo_falso(tmp_path_factory):
    """Pasta Game com GameDataEbl.bhd cifrado por uma chave RSA de teste e dois arquivos no .bdt."""
    pasta = tmp_path_factory.mktemp("Game")
    key = RSA.generate(2048)
    (pasta / "GameDataKeyCode.pem").write_bytes(key.publickey().export_key("PEM"))

    msb = dcx(b"MSB " + b"conteudo do mapa" * 4)
    aes_key = bytes(range(16))
    claro = b"PARAM" + bytes(27)
    cifrado = AES.new(aes_key, AES.MODE_ECB).encrypt(claro[:16]) + claro[16:]
    bdt = msb + bytes((-len(msb)) % 16)
    off_param = len(bdt)
    bdt += cifrado
    (pasta / "GameDataEbl.bdt").write_bytes(bdt)

    salt = b"SALT_DE_TESTE"
    head = bytearray(b"BHD5" + bytes(0x0C))
    head += struct.pack("<ii", 1, 0)  # 1 bucket, offset preenchido depois
    head += struct.pack("<i", len(salt)) + salt
    buckets_off = len(head)
    head += struct.pack("<ii", 2, 0)
    files_off = len(head)
    aes_off = files_off + 2 * 0x20
    head += struct.pack("<Iiqqq", ds2arquivos.ds2_hash("/map/m10_16_00_00/m10_16_00_00.msb"), len(msb), 0, 0, 0)
    head += struct.pack("<Iiqqq", ds2arquivos.ds2_hash("/param/teste.param"), len(cifrado), off_param, 0, aes_off)
    head += aes_key + struct.pack("<i", 1) + struct.pack("<qq", 0, 16)
    struct.pack_into("<i", head, 0x14, buckets_off)
    struct.pack_into("<i", head, buckets_off + 4, files_off)
    plano = bytes(head) + bytes((-len(head)) % 255)
    cifra = bytearray()
    for i in range(0, len(plano), 255):
        m = int.from_bytes(plano[i:i + 255], "big")
        cifra += pow(m, key.d, key.n).to_bytes(256, "big")
    (pasta / "GameDataEbl.bhd").write_bytes(bytes(cifra))
    return pasta, claro


def test_hash_matches_game_rule():
    assert ds2arquivos.ds2_hash("/map/m10_16_00_00/m10_16_00_00.msb") == hash_manual("/map/m10_16_00_00/m10_16_00_00.msb")
    assert ds2arquivos.ds2_hash("MAP\\M10.msb") == hash_manual("/map/m10.msb")


def test_reads_compressed_and_encrypted_files(jogo_falso):
    pasta, claro = jogo_falso
    arq = ds2arquivos.Arquivo(pasta, "GameData")
    assert arq.ler("/map/m10_16_00_00/m10_16_00_00.msb").startswith(b"MSB conteudo do mapa")
    assert arq.ler("/param/teste.param") == claro
    assert arq.tem("/param/teste.param") and not arq.tem("/param/outro.param")
    with pytest.raises(ds2arquivos.ArquivoError):
        arq.ler("/param/outro.param")


def test_signature_changes_with_the_index(jogo_falso, tmp_path):
    pasta, _ = jogo_falso
    assert ds2arquivos.assinatura(pasta) == ds2arquivos.assinatura(pasta)
    with pytest.raises(ds2arquivos.ArquivoError):
        ds2arquivos.Arquivo(tmp_path, "GameData")


@pytest.mark.skipif(GAME is None, reason="DS2 SotFS não instalado")
def test_real_game_map_file():
    assert ds2arquivos.Arquivo(GAME, "GameData").ler("/map/m10_16_00_00/m10_16_00_00.msb")[:4] == b"MSB "


def test_index_is_decrypted_once_per_process_until_the_game_updates(jogo_falso, monkeypatch):
    pasta, claro = jogo_falso
    chamadas = []
    original = ds2arquivos._decifrar_indice
    monkeypatch.setattr(ds2arquivos, "_decifrar_indice", lambda pem, bhd: chamadas.append(bhd) or original(pem, bhd))
    monkeypatch.setattr(ds2arquivos, "_INDICES", {})
    for _ in range(3):  # uma área por vez abre o pacote: o RSA do índice (~1 s no jogo real) só roda na primeira
        assert ds2arquivos.Arquivo(pasta, "GameData").ler("/param/teste.param") == claro
    assert len(chamadas) == 1
    bhd = pasta / "GameDataEbl.bhd"
    st = bhd.stat()
    os.utime(bhd, (st.st_atime, st.st_mtime + 10))  # o jogo atualizou: índice novo
    ds2arquivos.Arquivo(pasta, "GameData")
    assert len(chamadas) == 2


def test_game_dir_padrao_acha_o_jogo_numa_biblioteca_da_steam(tmp_path, monkeypatch):
    import ds2save

    monkeypatch.delenv("BUILDSMITH_DS2_GAME", raising=False)
    monkeypatch.setattr(ds2save, "STEAM_DIRS", [tmp_path / "Steam"])
    assert ds2arquivos.game_dir_padrao() is None
    game = tmp_path / "Steam" / "steamapps" / "common" / ds2save.DS2_PASTA / "Game"
    game.mkdir(parents=True)
    (game / "GameDataEbl.bhd").write_bytes(b"")
    assert ds2arquivos.game_dir_padrao() == game
