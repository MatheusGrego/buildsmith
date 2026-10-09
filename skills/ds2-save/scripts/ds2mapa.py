#!/usr/bin/env python3
"""Mapa do DS2 SotFS a partir dos arquivos do jogo: chão andável (navmesh), fogueiras, itens e inimigos de uma área,
e rota pelo chão entre dois pontos.

Formatos lidos (conferidos contra a Lost Bastille, m10_16_00_00):
- MSB: listas a partir de 0x10 (versão, qtd+1, nome, offsets; o último offset é a próxima lista). Em PARTS_PARAM_ST,
  cada parte tem nome relativo em +0, tipo em +8, posição (3 floats) em +0x10; objeto tem a referência em +0xA0
  (linha da MapObjectInstanceParam ou lote da ItemLotParam2_Other). A navmesh (tipo 4) está na origem das
  coordenadas relativas dos params e do NVG2.
- Param por mapa: contagem u16 em 0x0A, linhas de 24 bytes (id, offset, nome) a partir de 0x40; fim = u32 em 0x00.
- NVG2: malhas em 0x08; em 0x20 vêm malhas+4 offsets (4 seções de ligação e as malhas); malha: vértices em +0x28,
  faces em +0x2C, offsets de vértices/atributos/faces em +0x40; face = 3 índices no começo de 12 bytes.
- FMG (texto do jogo): grupos em 0x0C, textos em 0x10, tabela de offsets em 0x14; grupo = (índice, primeiro, último).
"""
import re
import struct

AREA = re.compile(r"^m(\d\d)_(\d\d)_(\d\d)_(\d\d)$")
TIPO_NAVMESH, TIPO_COLISAO, TIPO_OBJETO = 4, 3, 1


class MapaError(Exception):
    pass


def _wstr(data: bytes, off: int) -> str:
    end = off
    while data[end:end + 2] != b"\0\0":
        end += 2
    return data[off:end].decode("utf-16-le", errors="replace")


def _listas_msb(data: bytes) -> dict[str, list[int]]:
    if data[:4] != b"MSB ":
        raise MapaError("MSB em formato inesperado")
    listas, off, vistos = {}, 0x10, set()
    while off and off not in vistos:
        vistos.add(off)
        _versao, count = struct.unpack_from("<ii", data, off)
        nome = _wstr(data, struct.unpack_from("<q", data, off + 8)[0])
        offsets = struct.unpack_from(f"<{count}q", data, off + 16)
        listas[nome] = list(offsets[:-1])
        off = offsets[-1]
    return listas


def partes_msb(data: bytes) -> list[dict]:
    out = []
    for e in _listas_msb(data).get("PARTS_PARAM_ST", []):
        nome = _wstr(data, e + struct.unpack_from("<q", data, e)[0])
        tipo = struct.unpack_from("<H", data, e + 8)[0]
        pos = struct.unpack_from("<3f", data, e + 0x10)
        ref = struct.unpack_from("<I", data, e + 0xA0)[0] if tipo == TIPO_OBJETO else 0
        out.append({"nome": nome, "tipo": tipo, "pos": pos, "ref": ref})
    return out


def origem(partes: list[dict]) -> tuple[float, float, float]:
    """Posição da navmesh (ou da colisão) no MSB: a origem das coordenadas relativas da área."""
    for tipo in (TIPO_NAVMESH, TIPO_COLISAO):
        for p in partes:
            if p["tipo"] == tipo:
                return tuple(p["pos"])
    return (0.0, 0.0, 0.0)


def linhas_param(data: bytes) -> list[tuple[int, bytes]]:
    count = struct.unpack_from("<H", data, 0x0A)[0]
    entradas = [struct.unpack_from("<QQQ", data, 0x40 + 24 * i) for i in range(count)]
    fim_total = struct.unpack_from("<I", data, 0)[0]
    out = []
    for i, (rid, off, _nome) in enumerate(entradas):
        fim = entradas[i + 1][1] if i + 1 < count else fim_total
        out.append((rid, data[off:fim]))
    return out


def malhas_nvg2(data: bytes, base: tuple) -> list[dict]:
    if data[:4] != b"NVG2":
        raise MapaError("navmesh em formato inesperado")
    n = struct.unpack_from("<i", data, 0x08)[0]
    offsets = struct.unpack_from(f"<{n + 4}q", data, 0x20)
    malhas = []
    for o in offsets[4:]:
        vcount = struct.unpack_from("<I", data, o + 0x28)[0]
        fcount = struct.unpack_from("<H", data, o + 0x2C)[0]
        voff, _aoff, foff = struct.unpack_from("<qqq", data, o + 0x40)
        verts = [tuple(c + base[k] for k, c in enumerate(struct.unpack_from("<3f", data, voff + 12 * i))) for i in range(vcount)]
        faces = [struct.unpack_from("<3H", data, foff + 12 * i) for i in range(fcount)]
        if any(max(f) >= vcount for f in faces):
            raise MapaError("navmesh com índice de vértice inválido")
        malhas.append({"v": verts, "f": faces})
    return malhas


def textos_fmg(data: bytes) -> dict[int, str]:
    grupos, textos, str_off = struct.unpack_from("<iii", data, 0x0C)
    offs = struct.unpack_from(f"<{textos}i", data, str_off)
    out = {}
    for g in range(grupos):
        idx, primeiro, ultimo = struct.unpack_from("<iii", data, 0x1C + 12 * g)
        for k, i in enumerate(range(primeiro, ultimo + 1)):
            o = offs[idx + k]
            if o:
                out[i] = _wstr(data, o)
    return out


def nome_mapa_id(area: str) -> int:
    """ID do nome da área em mapname.fmg: m10_16_00_00 -> 10160000."""
    m = AREA.match(area)
    if not m:
        raise ValueError(f"área inválida: {area!r}")
    return int(m.group(1)) * 1_000_000 + int(m.group(2)) * 10_000
