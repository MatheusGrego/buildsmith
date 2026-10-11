import math
import struct
from pathlib import Path

import pytest

import ds2anim

GAME = Path(r"C:/Program Files (x86)/Steam/steamapps/common/Dark Souls II Scholar of the First Sin/Game")


def tqa_inv(q):
    """Quatérnion -> tangente de um quarto do ângulo (o que o .nsa guarda)."""
    x, y, z, w = q
    return (x / (1 + w), y / (1 + w), z / (1 + w))


def build_nsa(canais: int, upos: dict, uquat: dict, spos: list, squat: list) -> bytes:
    """NSA mínimo no layout do Morpheme 4 do DS2. upos/uquat: canal -> valor parado; spos/squat: [(canal, [por quadro])].
    Faixas fixas: posição em [-2, 2], rotação (tangente) em [-1, 1]; amostrados com média 0 e um conjunto de quantização."""
    quadros = len((spos or squat)[0][1]) if (spos or squat) else 1
    b = bytearray(0x600)
    struct.pack_into("<2f", b, 0x28, (quadros - 1) / 30.0, 30.0)
    struct.pack_into("<3I", b, 0x30, canais, 1, 1)
    o = 0x100

    def lista(valores):
        nonlocal o
        ini = o
        struct.pack_into(f"<H{len(valores)}H", b, o, len(valores), *valores)
        o += 2 + 2 * len(valores)
        o += (-o) % 4
        return ini

    struct.pack_into("<Q", b, 0x40, lista(sorted(upos)))
    struct.pack_into("<Q", b, 0x48, lista(sorted(uquat)))
    l_spos, l_squat = lista([c for c, _ in spos]), lista([c for c, _ in squat])
    o += (-o) % 8
    struct.pack_into("<2Q", b, o, l_spos, l_squat)
    struct.pack_into("<2Q", b, 0x50, o, o + 8)
    o += 16
    # média da posição: offset 0, escala 0 (a amostra carrega o valor todo); conjuntos: posição em [-2, 2]
    struct.pack_into("<6f", b, 0x60, 0, 0, 0, 0, 0, 0)
    struct.pack_into("<2I", b, 0x78, 1, 1)
    struct.pack_into("<6f", b, o, -2, -2, -2, 4 / 2047, 4 / 2047, 4 / 1023)
    struct.pack_into("<Q", b, 0x80, o)
    o += 24
    struct.pack_into("<6f", b, o, -1, -1, -1, 2 / 65535, 2 / 65535, 2 / 65535)  # somado à média (u8 × 2/255 - 1)
    struct.pack_into("<Q", b, 0x88, o)
    o += 24
    U = o  # dados que não mudam
    struct.pack_into("<Q", b, 0x90, U)
    struct.pack_into("<2I", b, U, len(upos), len(uquat))
    struct.pack_into("<6f", b, U + 8, -2, -2, -2, 4 / 65535, 4 / 65535, 4 / 65535)
    struct.pack_into("<6f", b, U + 0x20, -1, -1, -1, 2 / 65535, 2 / 65535, 2 / 65535)
    q16 = lambda v, lo, esc: max(0, min(65535, round((v - lo) / esc)))  # noqa: E731
    dados = b"".join(struct.pack("<3H", *(q16(v[k], -2, 4 / 65535) for k in range(3))) for _c, v in sorted(upos.items()))
    dq = b"".join(struct.pack("<3H", *(q16(t, -1, 2 / 65535) for t in tqa_inv(v))) for _c, v in sorted(uquat.items()))
    struct.pack_into("<QQ", b, U + 0x38, 0x48, 0x48 + len(dados))
    b[U + 0x48:U + 0x48 + len(dados) + len(dq)] = dados + dq
    o = U + 0x48 + len(dados) + len(dq)
    o += (-o) % 16
    S = o  # seção única
    struct.pack_into("<2I", b, 0xC0, 0, quadros - 1)  # quadro inicial de cada seção (+ o último)
    struct.pack_into("<I", b, 0xC8, S)
    struct.pack_into("<Q", b, 0xA0, 0xC0)
    struct.pack_into("<Q", b, 0xB0, 0xC8)
    corpo = bytearray()
    pos_dados = b"".join(struct.pack("<I", (q(v[0], 11) << 21) | (q(v[1], 11) << 10) | q(v[2], 10))
                         for f in range(quadros) for _c, vals in spos for v in [vals[f]]
                         for q in [lambda x, bits: max(0, min((1 << bits) - 1, round((x + 2) / 4 * ((1 << bits) - 1))))])
    pos_meta = b"".join(bytes((0, 0, 0, 0, 0, 0)) for _ in spos)
    # média 127.5 -> 0; o conjunto (offset -1, escala 2/65535) leva a tangente toda
    rot_dados = b"".join(struct.pack("<3H", *(q16(t + 1 - (128 * 2 / 255 - 1) - 1, -1, 2 / 65535) for t in tqa_inv(vals[f])))
                         for f in range(quadros) for _c, vals in squat)
    rot_meta = b"".join(bytes((128, 128, 128, 0, 0, 0)) for _ in squat)
    partes, offs = [pos_dados, pos_meta, rot_dados, rot_meta], []
    cursor = 0x30
    for p in partes:
        offs.append(cursor)
        corpo += bytes(cursor - 0x30 - len(corpo)) + p
        cursor = 0x30 + len(corpo) + (-(0x30 + len(corpo))) % 4
    sec = bytearray(0x30)
    struct.pack_into("<3I", sec, 0, quadros, len(spos), len(squat))
    struct.pack_into("<4Q", sec, 0x10, *offs)
    b[S:S + 0x30 + len(corpo)] = sec + corpo
    return bytes(b)


def build_nmb(nomes: list[str], pais: list[int], pos: list, rot: list) -> bytes:
    """NMB mínimo: hierarquia em 0x120/0x130, nomes a partir de CharacterWorldSpaceTM e o buffer da pose de referência
    apontado por 0x118 (relativo a 0x100), com o mapa de bits de um bit por osso antes dos offsets."""
    n = len(nomes)
    n4 = (n + 3) // 4 * 4
    b = bytearray(0x130 + 4 * n)
    struct.pack_into("<I", b, 0x120, n)
    struct.pack_into(f"<{n}i", b, 0x130, *pais)
    b += b"\0" * ((-len(b)) % 16) + "\0".join(nomes).encode() + b"\0"
    b += b"\0" * ((-len(b)) % 16)
    base = len(b)
    palavras = (n + 31) // 32
    buf = bytearray(0x40 + 4 * palavras + 0x10)
    struct.pack_into("<I", buf, 0x10, n)
    o_pos = 0x40 + 4 * palavras + 0x10
    o_pos += (-o_pos) % 16
    struct.pack_into("<I", buf, 0x40 + 4 * palavras, o_pos)
    struct.pack_into("<I", buf, 0x40 + 4 * palavras + 8, o_pos + n4 * 16)
    buf += bytes(o_pos - len(buf))
    for p in pos:
        buf += struct.pack("<4f", *p, 0)
    buf += bytes((n4 - n) * 16)
    for q in rot:
        buf += struct.pack("<4f", *q)
    struct.pack_into("<Q", b, 0x118, base - 0x100)
    return bytes(b + buf)


NOMES = ["CharacterWorldSpaceTM", "Character", "Master", "Root", "Pelvis"]
PAIS = [-1, 0, 1, 1, 3]
GIRO = (0.0, 0.0, math.sin(math.radians(45)), math.cos(math.radians(45)))  # 90° em z


def test_rig_do_nmb_com_pose_de_referencia():
    pos = [(0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0.98), (0.1, 0, 0)]
    rot = [(0, 0, 0, 1)] * 3 + [GIRO, (0, 0, 0, 1)]
    rig = ds2anim.ler_rig(build_nmb(NOMES, PAIS, pos, rot))
    assert rig["nomes"] == NOMES and rig["pais"] == PAIS
    assert rig["pos"][3] == pytest.approx((0, 0, 0.98)) and rig["rot"][3] == pytest.approx(GIRO)
    with pytest.raises(ds2anim.AnimError):
        ds2anim.ler_rig(b"x" * 0x200)


def test_quadro_do_nsa_parado_e_amostrado():
    """Canal c = osso c+1. Root (canal 2) com posição amostrada e rotação amostrada; Pelvis (canal 3) parado."""
    raiz = [(0.0, 0.0, 0.90), (0.0, 0.05, 0.95)]
    giro = [(0, 0, 0, 1), GIRO]
    nsa = build_nsa(4, upos={0: (0, 0, 0), 1: (0, 0, 0), 3: (0.1, 0.2, -0.3)},
                    uquat={0: (0, 0, 0, 1), 1: (0, 0, 0, 1), 3: (0.5, 0.5, 0.5, 0.5)},
                    spos=[(2, raiz)], squat=[(2, giro)])
    info = ds2anim.info_nsa(nsa)
    assert info["quadros"] == 2 and info["canais"] == 4
    for f in (0, 1):
        pos, rot = ds2anim.pose_nsa(nsa, f)
        assert pos[4] == pytest.approx((0.1, 0.2, -0.3), abs=1e-3)
        assert rot[4] == pytest.approx((0.5, 0.5, 0.5, 0.5), abs=1e-3)
        assert pos[3] == pytest.approx(raiz[f], abs=4e-3)  # 11/10 bits em [-2, 2]
        assert rot[3] == pytest.approx(giro[f], abs=1e-3)


def test_eixo_do_morpheme_para_o_flver():
    """Y e Z trocados: conferido no Hollow Soldier (Root do rig (0, 0, 0.98) = (0, 0.98, 0) do FLVER)."""
    p, q = ds2anim.para_flver((0, 0, 0.98), (0.0, 0.0, -0.7071, 0.7071))
    assert p == (0, 0.98, 0) and q == pytest.approx((0.0, 0.7071, 0.0, 0.7071))


def test_escolhe_a_espera_padrao():
    nomes = ["a00_00_7001_Wep01_Idle_x.nsa", "a00_00_0000_Idle_Head_A_x.nsa", "a00_00_0000_Idle_untitled_x.nsa", "c1020.nmb"]
    assert ds2anim.escolher_idle(nomes) == "a00_00_0000_Idle_untitled_x.nsa"
    assert ds2anim.escolher_idle(["a00_00_7001_Wep01_Idle_x.nsa", "a12_Idle_y.nsa"]) == "a12_Idle_y.nsa"
    assert ds2anim.escolher_idle(["a65_Attack.nsa"]) is None


@pytest.mark.skipif(not (GAME / "GameDataEbl.bhd").exists(), reason="DS2 SotFS não instalado")
def test_hollow_soldier_na_espera_com_o_jogo():
    """Pose de referência do rig reproduz a malha do FLVER (eixos, nomes e pele certos); no Idle os pés ficam no chão."""
    import ds2arquivos
    import ds2cena

    pac = ds2cena.Pacotes(GAME)
    arqs = ds2cena.ler_binder(pac.ler("/model/chr/c1020.bnd"))
    flv = arqs["c1020.flv"]
    anim = ds2cena.ler_binder(pac.ler("/morpheme4/chr/c1020.anibnd.dcx"))
    rig = ds2anim.ler_rig(next(v for k, v in anim.items() if k.endswith(".nmb")))
    referencia = {n: ds2anim.para_flver(rig["pos"][i], rig["rot"][i]) for i, n in enumerate(rig["nomes"])}
    base, mesma = ds2cena.ler_flver(flv), ds2cena.ler_flver(flv, pose=referencia)
    desvio = max(math.dist(a, b) for m0, m1 in zip(base["malhas"], mesma["malhas"]) for a, b in zip(m0["vertices"], m1["vertices"]))
    assert desvio < 1e-3
    idle = ds2cena.ler_flver(flv, pose=ds2anim.pose_flver(rig, anim[ds2anim.escolher_idle(list(anim))], 0))
    assert abs(idle["bb"][0][1]) < 0.05 and 1.6 < idle["bb"][1][1] - idle["bb"][0][1] < 2.0
    assert ds2arquivos  # o pacote abre pelo mesmo caminho do extrator
