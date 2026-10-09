import struct

import pytest

import ds2mapa


def utf16z(text: str) -> bytes:
    return text.encode("utf-16-le") + bytes(2)


def build_msb(parts: list[dict]) -> bytes:
    """MSB mínimo: cabeçalho de 0x10 bytes e uma lista PARTS_PARAM_ST com as partes dadas."""
    data = bytearray(b"MSB " + struct.pack("<ii", 1, 0x10) + bytes(4))
    head = len(data)
    count = len(parts) + 1
    data += bytes(16 + 8 * count)
    nome_lista = len(data)
    data += utf16z("PARTS_PARAM_ST")
    offsets = []
    for p in parts:
        while len(data) % 8:
            data += b"\0"
        e = len(data)
        offsets.append(e)
        entry = bytearray(0xB0)
        struct.pack_into("<q", entry, 0, 0xB0)
        struct.pack_into("<HHH", entry, 8, p["tipo"], 0, 0)
        struct.pack_into("<3f", entry, 0x10, *p["pos"])
        struct.pack_into("<I", entry, 0xA0, p.get("ref", 0))
        data += entry + utf16z(p["nome"])
    struct.pack_into("<ii", data, head, 5, count)
    struct.pack_into("<q", data, head + 8, nome_lista)
    struct.pack_into(f"<{count}q", data, head + 16, *offsets, 0)
    return bytes(data)


def build_param(rows: list[tuple[int, bytes]]) -> bytes:
    head = bytearray(0x40 + 24 * len(rows))
    struct.pack_into("<H", head, 0x0A, len(rows))
    body = bytearray()
    for i, (rid, raw) in enumerate(rows):
        struct.pack_into("<QQQ", head, 0x40 + 24 * i, rid, len(head) + len(body), 0)
        body += raw
    data = head + body
    struct.pack_into("<I", data, 0, len(data))
    return bytes(data)


def build_nvg2(verts, faces) -> bytes:
    data = bytearray(b"NVG2" + struct.pack("<ii", 2, 1) + bytes(0x14))
    data += bytes(8 * 5)  # 4 seções de ligação + 1 malha
    mesh = len(data)
    data += bytes(0x70)
    voff = len(data)
    for v in verts:
        data += struct.pack("<3f", *v)
    aoff = len(data)
    data += bytes(4 * len(faces))
    foff = len(data)
    for f in faces:
        data += struct.pack("<6H", *f, 0, 0, 0)
    struct.pack_into("<I", data, mesh + 0x28, len(verts))
    struct.pack_into("<H", data, mesh + 0x2C, len(faces))
    struct.pack_into("<qqq", data, mesh + 0x40, voff, aoff, foff)
    struct.pack_into("<5q", data, 0x20, 0, 0, 0, 0, mesh)
    return bytes(data)


def build_fmg(groups: list[tuple[int, list[str]]]) -> bytes:
    total = sum(len(t) for _, t in groups)
    head = bytearray(0x1C + 12 * len(groups))
    struct.pack_into("<i", head, 0x0C, len(groups))
    struct.pack_into("<i", head, 0x10, total)
    idx = 0
    for g, (first, textos) in enumerate(groups):
        struct.pack_into("<iii", head, 0x1C + 12 * g, idx, first, first + len(textos) - 1)
        idx += len(textos)
    str_off = len(head)
    struct.pack_into("<i", head, 0x14, str_off)
    data = head + bytes(4 * total)
    k = 0
    for _, textos in groups:
        for t in textos:
            struct.pack_into("<i", data, str_off + 4 * k, len(data))
            data += utf16z(t)
            k += 1
    return bytes(data)


def test_msb_parts_with_position_and_reference():
    msb = build_msb([{"nome": "n01_0100_0000", "tipo": 4, "pos": (-78.0, 4.0, 562.0)},
                     {"nome": "o00_0100_0000", "tipo": 1, "pos": (-128.0, 27.5, 604.0), "ref": 10160653}])
    partes = ds2mapa.partes_msb(msb)
    assert [(p["nome"], p["tipo"]) for p in partes] == [("n01_0100_0000", 4), ("o00_0100_0000", 1)]
    assert partes[1]["pos"] == pytest.approx((-128.0, 27.5, 604.0)) and partes[1]["ref"] == 10160653
    assert ds2mapa.origem(partes) == pytest.approx((-78.0, 4.0, 562.0))


def test_param_rows():
    rows = ds2mapa.linhas_param(build_param([(10160653, struct.pack("<i", 16650) + bytes(36)), (10160654, bytes(40))]))
    assert [r[0] for r in rows] == [10160653, 10160654]
    assert struct.unpack_from("<i", rows[0][1])[0] == 16650 and len(rows[1][1]) == 40


def test_navmesh_triangles_in_absolute_coordinates():
    nvg = build_nvg2([(0, 0, 0), (1, 0, 0), (0, 0, 1), (1, 0, 1)], [(0, 1, 2), (1, 3, 2)])
    malhas = ds2mapa.malhas_nvg2(nvg, (10.0, 1.0, 100.0))
    assert len(malhas) == 1
    assert malhas[0]["v"][3] == pytest.approx((11.0, 1.0, 101.0)) and malhas[0]["f"] == [(0, 1, 2), (1, 3, 2)]


def test_navmesh_with_bad_index_is_refused():
    with pytest.raises(ds2mapa.MapaError):
        ds2mapa.malhas_nvg2(build_nvg2([(0, 0, 0)], [(0, 1, 2)]), (0, 0, 0))


def test_fmg_texts_and_map_name_id():
    textos = ds2mapa.textos_fmg(build_fmg([(2650, ["Fire Keepers' Dwelling"]), (16650, ["Straid's Cell", "x"])]))
    assert textos == {2650: "Fire Keepers' Dwelling", 16650: "Straid's Cell", 16651: "x"}
    assert ds2mapa.nome_mapa_id("m10_16_00_00") == 10160000
    with pytest.raises(ValueError):
        ds2mapa.nome_mapa_id("../x")
