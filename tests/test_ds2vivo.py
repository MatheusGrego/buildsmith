import math
import struct

import pytest

import ds2mem
import ds2vivo

MOD, BASE_A, CTRL, CAM_OBJ, CAM, NOME_OBJ, P1, POS = (0x140000000, 0x10000, 0x20000, 0x30000, 0x40000, 0x50000, 0x60000,
                                                       0x70000)


def regiao(tamanho, **valores):
    """Bloco de memória com valores em offsets: inteiro = ponteiro (u64), tupla = floats, str = UTF-16."""
    b = bytearray(tamanho)
    for off, v in valores.items():
        off = int(off[1:], 16)
        if isinstance(v, int):
            struct.pack_into("<Q", b, off, v)
        elif isinstance(v, tuple):
            struct.pack_into(f"<{len(v)}f", b, off, *v)
        else:
            enc = (v + "\0").encode("utf-16-le")
            b[off:off + len(enc)] = enc
    return bytes(b)


def jogo(pos=(10.0, 2.0, -5.0), quat=(1.0, 0.0, 0.0, 0.0), camera=(10.0, 4.0, -1.0), nome="Personagem Um", base_a=BASE_A,
         ctrl=CTRL):
    codigo = bytearray(0x200)
    codigo[0x100:0x111] = bytes.fromhex("488B05" + "80000000" + "488B583848 85DB 7410 F6".replace(" ", ""))
    struct.pack_into("<Q", codigo, 0x187, base_a)
    mem = ds2mem.MemoriaFalsa({
        MOD: bytes(codigo),
        BASE_A: regiao(0x200, x0=CAM_OBJ, xa8=NOME_OBJ, xd0=ctrl),
        CAM_OBJ: regiao(0x40, x20=CAM),
        CAM: regiao(0x200, x1a0=camera),
        NOME_OBJ: regiao(0x200, x114=nome),
        CTRL: regiao(0x200, xf8=P1),
        P1: regiao(0x200, xf0=POS),
        POS: regiao(0x80, x20=pos, x30=quat),
    })
    mem.base_modulo, mem.tamanho_modulo = MOD, 0x200
    return mem


def leitor(mem):
    return ds2vivo.LeitorVivo(abrir=lambda: mem, relogio=lambda: 123.0)


def test_camera_yaw_uses_the_same_convention_as_the_3d_map():
    # câmera atrás do personagem em +Z: ela olha para −Z (giro π no iso.js: frente = (sen, cos))
    assert abs(abs(ds2vivo.yaw_da_camera([0, 3, 5], [0, 0, 0])) - math.pi) < 1e-9
    assert abs(ds2vivo.yaw_da_camera([-5, 3, 0], [0, 0, 0]) - math.pi / 2) < 1e-9  # olha para +X
    assert ds2vivo.yaw_da_camera([0.01, 9, 0.02], [0, 0, 0]) is None  # câmera em cima: sem direção


def test_character_heading_from_the_rotation_quaternion():
    meia = math.radians(90) / 2  # 90° em torno do eixo vertical
    assert abs(ds2vivo.direcao_do_quaternion((math.cos(meia), 0.0, math.sin(meia), 0.0)) - math.pi / 2) < 1e-6
    assert ds2vivo.direcao_do_quaternion((0.0, 0.0, 0.0, 0.0)) is None  # não é rotação


def test_live_state_from_memory():
    r = leitor(jogo()).ler()
    assert r["ativo"] and r["nome"] == "Personagem Um" and r["ts"] == 123.0
    assert r["pos"] == [10.0, 2.0, -5.0] and r["camera"] == [10.0, 4.0, -1.0]
    assert abs(abs(r["yaw_camera"]) - math.pi) < 1e-6 and abs(r["dir_personagem"]) < 1e-6
    assert r["area"] is None  # Task 3


def test_null_pointers_mean_loading():
    assert leitor(jogo(ctrl=0)).ler() == {"ativo": False, "motivo": "carregando", "ts": 123.0}
    assert leitor(jogo(base_a=0)).ler()["motivo"] == "carregando"


def test_closed_game_and_reopening():
    estado = {"aberto": False}
    mem = jogo()

    def abrir():
        if not estado["aberto"]:
            raise ds2mem.ErroMemoria("DarkSoulsII.exe não está aberto")
        return mem

    lv = ds2vivo.LeitorVivo(abrir=abrir, relogio=lambda: 1.0)
    assert lv.ler() == {"ativo": False, "motivo": "jogo fechado", "ts": 1.0}
    estado["aberto"] = True
    assert lv.ler()["ativo"]  # tenta abrir de novo na leitura seguinte
