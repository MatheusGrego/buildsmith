#!/usr/bin/env python3
"""Animação dos personagens do DS2 SotFS (Morpheme 4 da NaturalMotion): rig do .nmb e pose de um quadro do .nsa.

Lido dos próprios arquivos (sem código do runtime Morpheme), conferido no Hollow Soldier (c1020) e em mais 7 rigs:

- /morpheme4/chr/<cXXXX>.anibnd.dcx: BND4 com <cXXXX>.nmb (a rede, com o rig) e as animações .nsa
  ("a00_00_0000_Idle_untitled_<hash>.nsa").
- Rig no .nmb: em 0x120 a quantidade de ossos e em 0x130 o pai de cada um (-1, 0, 1, 1, 3...); nomes como texto a partir
  de "CharacterWorldSpaceTM" (CharacterWorldSpaceTM, Character, Master, Root, Pelvis, Spine...); pose de referência num
  buffer de transformações apontado por 0x118 (relativo a 0x100): +0x10 quantidade, um mapa de bits com um bit por osso
  (tamanho variável) e depois os offsets das posições e das rotações (8 bytes um do outro, a diferença é n4·16, n4 = n
  arredondado para 4); posições xyz e quatérnions xyzw de 16 bytes.
- O rig é o esqueleto do FLVER com Y e Z trocados: posição FLVER = (x, z, y); rotação FLVER = (-qx, -qz, -qy, qw)
  (conferido osso a osso: Root, Pelvis, coluna, cabeça, clavículas, braços, coxas).
- .nsa (ponteiros absolutos no cabeçalho): 0x28 duração, 0x2C quadros/s, 0x30 canais; canal c = osso c+1 do rig.
  0x40/0x48 listas (u16 n + u16[n]) dos canais de posição e de rotação que não mudam; 0x50/0x58 apontam para as listas
  dos amostrados; 0x60 faixa das médias de posição (offset xyz, escala xyz); 0x78 quantos conjuntos de quantização de
  posição e de rotação, 0x80/0x88 os conjuntos (offset xyz, escala xyz); 0x90 os dados que não mudam (+0 nº pos,
  +4 nº rot, +8 faixa pos, +0x20 faixa rot, +0x38/+0x40 offsets dos u16×3 relativos a essa estrutura); 0xA0/0xB0
  quadro inicial e offset de cada seção.
- Seção: +0 quadros, +4 nº pos, +8 nº rot, +0x10..0x28 offsets (relativos à seção) de: posição por quadro (u32 com x
  nos 11 bits altos, y nos 11 do meio, z nos 10 baixos), média+conjunto de cada canal de posição (u8×3 + u8×3),
  rotação por quadro (u16×3 por canal, quadro > canal > xyz) e média+conjunto de cada canal de rotação.
- Valor = média + offset do conjunto + amostra × escala do conjunto; média da posição = offset + u8 × escala (0x60);
  média da rotação = u8 × 2/255 - 1. Rotação em tangente de um quarto do ângulo: q = (2v, 1 - |v|²) / (1 + |v|²).
  Conferido: no quadro 0 do Idle do Hollow Soldier os dedos dos pés ficam no chão (z ≈ 0) e o Root a 0,92 m.
"""
import math
import struct

CWS = b"CharacterWorldSpaceTM\x00"


class AnimError(Exception):
    pass


def _tqa(v) -> tuple:
    s = v[0] * v[0] + v[1] * v[1] + v[2] * v[2]
    d = 1.0 + s
    return (2 * v[0] / d, 2 * v[1] / d, 2 * v[2] / d, (1 - s) / d)


def ler_rig(nmb: bytes) -> dict:
    """{nomes, pais, pos, rot} do rig (pose de referência no eixo do Morpheme)."""
    i = nmb.find(CWS)
    if i < 0 or len(nmb) < 0x130:
        raise AnimError("nmb sem rig")
    n = struct.unpack_from("<I", nmb, 0x120)[0]
    if not 0 < n < 1024 or 0x130 + 4 * n > len(nmb):
        raise AnimError("hierarquia do rig fora do lugar")
    pais = list(struct.unpack_from(f"<{n}i", nmb, 0x130))
    if pais[0] != -1 or any(not -1 <= p < j for j, p in enumerate(pais)):
        raise AnimError("hierarquia do rig inválida")
    nomes, k = [], i
    while len(nomes) < n:
        e = nmb.index(b"\0", k)
        nomes.append(nmb[k:e].decode("latin-1"))
        k = e + 1
    # pose de referência: a definição do rig (0x100) aponta o buffer em +0x18; dentro dele, depois de um mapa de bits de
    # um bit por osso (tamanho variável), vêm os offsets (relativos ao buffer) das posições e das rotações, a 8 bytes
    # um do outro, separados por n4·16 bytes
    n4 = (n + 3) // 4 * 4
    base = 0x100 + struct.unpack_from("<Q", nmb, 0x118)[0]
    if not 0 < base < len(nmb) - 0x100 or struct.unpack_from("<I", nmb, base + 0x10)[0] != n:
        raise AnimError("pose de referência do rig não achada")
    for k in range(base + 0x20, base + 0x100, 4):
        o_pos, o_rot = struct.unpack_from("<I", nmb, k)[0], struct.unpack_from("<I", nmb, k + 8)[0]
        if not (0x40 <= o_pos < 0x400 and o_pos % 16 == 0 and o_rot == o_pos + n4 * 16):
            continue
        if base + o_rot + 16 * n > len(nmb):
            break
        pos = [struct.unpack_from("<3f", nmb, base + o_pos + 16 * m) for m in range(n)]
        rot = [struct.unpack_from("<4f", nmb, base + o_rot + 16 * m) for m in range(n)]
        if all(abs(math.sqrt(sum(x * x for x in q)) - 1) < 1e-3 for q in rot):
            return {"nomes": nomes, "pais": pais, "pos": pos, "rot": rot}
    raise AnimError("pose de referência do rig não achada")


def _lista(a: bytes, o: int) -> list[int]:
    n = struct.unpack_from("<H", a, o)[0]
    return list(struct.unpack_from(f"<{n}H", a, o + 2))


def info_nsa(a: bytes) -> dict:
    duracao, fps = struct.unpack_from("<2f", a, 0x28)
    canais, _x, secoes = struct.unpack_from("<3I", a, 0x30)
    return {"duracao": duracao, "fps": fps, "canais": canais, "secoes": secoes,
            "quadros": max(1, round(duracao * fps) + 1)}


def pose_nsa(a: bytes, quadro: int = 0) -> tuple[dict, dict]:
    """(posições, rotações) locais de um quadro, por osso do rig (canal c = osso c+1), no eixo do Morpheme."""
    try:
        q = lambda o: struct.unpack_from("<Q", a, o)[0]  # noqa: E731
        info = info_nsa(a)
        upos, uquat = _lista(a, q(0x40)), _lista(a, q(0x48))
        spos, squat = _lista(a, q(q(0x50))), _lista(a, q(q(0x58)))
        pm = struct.unpack_from("<6f", a, 0x60)
        n_pset, n_qset = struct.unpack_from("<2I", a, 0x78)
        psets = [struct.unpack_from("<6f", a, q(0x80) + 24 * k) for k in range(n_pset)]
        qsets = [struct.unpack_from("<6f", a, q(0x88) + 24 * k) for k in range(n_qset)]
        U = q(0x90)
        pmin, pscl = struct.unpack_from("<3f", a, U + 8), struct.unpack_from("<3f", a, U + 0x14)
        qmin, qscl = struct.unpack_from("<3f", a, U + 0x20), struct.unpack_from("<3f", a, U + 0x2C)
        po, qo = U + struct.unpack_from("<I", a, U + 0x38)[0], U + struct.unpack_from("<I", a, U + 0x40)[0]
        pos, rot = {}, {}
        for i, c in enumerate(upos):
            v = struct.unpack_from("<3H", a, po + 6 * i)
            pos[c] = tuple(pmin[k] + v[k] * pscl[k] for k in range(3))
        for i, c in enumerate(uquat):
            v = struct.unpack_from("<3H", a, qo + 6 * i)
            rot[c] = _tqa([qmin[k] + v[k] * qscl[k] for k in range(3)])
        if spos or squat:
            n_sec = max(1, info["secoes"])
            inicios = list(struct.unpack_from(f"<{n_sec + 1}I", a, q(0xA0)))
            offs = list(struct.unpack_from(f"<{n_sec}I", a, q(0xB0)))
            quadro = max(0, min(quadro, inicios[-1]))
            s = next((k for k in range(n_sec) if inicios[k] <= quadro <= inicios[k + 1]), n_sec - 1)
            S = offs[s]
            nq, npos, nquat = struct.unpack_from("<3I", a, S)
            pd, pmeta, qd, qmeta = (S + o for o in struct.unpack_from("<4Q", a, S + 0x10))
            f = min(quadro - inicios[s], nq - 1)
            for i, c in enumerate(spos):
                w = struct.unpack_from("<I", a, pd + 4 * (f * npos + i))[0]
                amostra = ((w >> 21) & 0x7FF, (w >> 10) & 0x7FF, w & 0x3FF)
                m = a[pmeta + 6 * i:pmeta + 6 * i + 6]
                pos[c] = tuple(pm[k] + m[k] * pm[3 + k] + psets[m[3 + k]][k] + amostra[k] * psets[m[3 + k]][3 + k]
                               for k in range(3))
            for i, c in enumerate(squat):
                amostra = struct.unpack_from("<3H", a, qd + 6 * (f * nquat + i))
                m = a[qmeta + 6 * i:qmeta + 6 * i + 6]
                rot[c] = _tqa([m[k] * 2 / 255 - 1 + qsets[m[3 + k]][k] + amostra[k] * qsets[m[3 + k]][3 + k]
                               for k in range(3)])
        return {c + 1: v for c, v in pos.items()}, {c + 1: v for c, v in rot.items()}
    except (struct.error, IndexError, ValueError) as err:
        raise AnimError(f"nsa em formato inesperado ({err})") from err


def para_flver(pos, rot) -> tuple[tuple, tuple]:
    """Posição e rotação do eixo do Morpheme para o do FLVER (Y e Z trocados)."""
    return (pos[0], pos[2], pos[1]), (-rot[0], -rot[2], -rot[1], rot[3])


def pose_flver(rig: dict, nsa: bytes, quadro: int = 0) -> dict[str, tuple]:
    """Nome do osso -> (posição, rotação xyzw) local no eixo do FLVER, para os ossos que a animação mexe ou fixa."""
    pos, rot = pose_nsa(nsa, quadro)
    out = {}
    for i, nome in enumerate(rig["nomes"]):
        if i in pos or i in rot:
            out[nome] = para_flver(pos.get(i, rig["pos"][i]), rot.get(i, rig["rot"][i]))
    return out


def escolher_idle(nomes: list[str]) -> str | None:
    """A animação de espera padrão do personagem: a00_00_0000_Idle_untitled, senão o 1º Idle sem arma."""
    nsa = sorted(n for n in nomes if n.lower().endswith(".nsa"))
    for teste in (lambda n: n.lower().startswith("a00_00_0000_idle_untitled"),
                  lambda n: n.lower().startswith("a00_00_0000_idle"),
                  lambda n: "_idle" in n.lower() and "wep" not in n.lower(),
                  lambda n: n.lower().startswith("a00_00_")):
        achados = [n for n in nsa if teste(n)]
        if achados:
            return achados[0]
    return None
