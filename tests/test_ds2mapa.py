import json
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


def test_build_area_classifies_bonfires_items_and_enemies():
    partes = [{"nome": "n01", "tipo": 4, "pos": (-78.0, 4.0, 562.0), "ref": 0},
              {"nome": "o00_0100_0000", "tipo": 1, "pos": (-128.1, 27.7, 604.2), "ref": 10160653},
              {"nome": "o00_0256_0006", "tipo": 1, "pos": (-118.0, 27.7, 601.8), "ref": 10165290},
              {"nome": "o00_2000_0001", "tipo": 1, "pos": (0.0, 0.0, 0.0), "ref": 999}]
    area = ds2mapa.montar_area(
        "m10_16_00_00", "The Lost Bastille", partes,
        instancias={10160653: 16650}, nomes_fogueira={16650: "Straid's Cell"},
        lotes={10165290: [(19010000, 1), (60140000, 3)]}, nomes_itens={19010000: "Petrified Dragon Bone", 60140000: "Firebomb"},
        malhas=[{"v": [(0.04, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0)], "f": [(0, 1, 2)]}],
        geradores=[(145, (-49.3, 23.7, 39.1))], assinatura="x")
    assert area["fogueiras"] == [{"id": 16650, "nome": "Straid's Cell", "pos": [-128.1, 27.7, 604.2]}]
    assert area["itens"] == [{"lote": 10165290, "pos": [-118.0, 27.7, 601.8],
                              "itens": [{"id": 19010000, "nome": "Petrified Dragon Bone", "qtd": 1}, {"id": 60140000, "nome": "Firebomb", "qtd": 3}]}]
    assert area["inimigos"] == [{"id": 145, "pos": [-127.3, 27.7, 601.1]}]
    assert area["malhas"] == [{"v": [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0], "f": [0, 1, 2]}]
    assert area["origem"] == [-78.0, 4.0, 562.0] and area["nome"] == "The Lost Bastille"


def test_item_lot_rows():
    row = bytearray(124)
    row[4] = 1
    row[5] = 3
    struct.pack_into("<10i", row, 0x2C, 19010000, 60140000, *([10] * 8))
    struct.pack_into("<10f", row, 0x54, 1.0, 1.0, *([0.0] * 8))
    assert ds2mapa.lotes_itens(build_param([(10165290, bytes(row))])) == {10165290: [(19010000, 1), (60140000, 3)]}


GAME = __import__("pathlib").Path(r"C:/Program Files (x86)/Steam/steamapps/common/Dark Souls II Scholar of the First Sin/Game")


@pytest.mark.skipif(not (GAME / "GameDataEbl.bhd").exists(), reason="DS2 SotFS não instalado")
def test_real_lost_bastille(tmp_path):
    import math
    area = ds2mapa.extrair_area(GAME, "m10_16_00_00", tmp_path)
    assert area["nome"] == "The Lost Bastille"
    fog = {f["nome"]: f["pos"] for f in area["fogueiras"]}
    assert set(fog) == {"Straid's Cell", "Exile Holding Cells", "The Tower Apart", "Upper Ramparts",
                        "McDuff's Workshop", "Servants' Quarters", "The Saltfort"}
    assert math.dist(fog["Straid's Cell"], (-128.1, 27.7, 604.2)) < 1
    cela = [p for p in area["itens"] if {"Petrified Dragon Bone", "Firebomb"} <= {i["nome"] for i in p["itens"]}]
    assert cela and math.dist(cela[0]["pos"], fog["Straid's Cell"]) < 15
    assert (tmp_path / "mapas" / "m10_16_00_00.json").exists()
    assert ds2mapa.extrair_area(GAME, "m10_16_00_00", tmp_path)["assinatura"] == area["assinatura"]
    pontos = ds2mapa.onde(GAME, tmp_path, "fragrant branch of yore", areas_filtro=["m10_16_00_00"])
    assert len(pontos) >= 2 and all(p["area"] == "m10_16_00_00" for p in pontos)
    assert {"area": "m10_16_00_00", "nome": "The Lost Bastille"} in ds2mapa.areas(GAME)


def test_cli_without_game_reports_error(tmp_path, capsys):
    assert ds2mapa.main(["areas", "--game", str(tmp_path)]) == 1
    assert "error" in json.loads(capsys.readouterr().out)


@pytest.mark.skipif(not (GAME / "GameDataEbl.bhd").exists(), reason="DS2 SotFS não instalado")
def test_cli_extract_prints_summary(tmp_path, capsys):
    assert ds2mapa.main(["extrair", "--area", "m10_16_00_00", "--game", str(GAME), "--cache", str(tmp_path)]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["nome"] == "The Lost Bastille" and out["fogueiras"] == 7 and out["itens"] > 50


def faixa_area(ilhas=False):
    """Faixa de 6 triângulos ao longo de x (0..3), e uma ilha separada em x=10 quando pedida."""
    v = [0, 0, 0, 0, 0, 1, 1, 0, 0, 1, 0, 1, 2, 0, 0, 2, 0, 1, 3, 0, 0, 3, 0, 1]
    f = [0, 2, 1, 1, 2, 3, 2, 4, 3, 3, 4, 5, 4, 6, 5, 5, 6, 7]
    malhas = [{"v": v, "f": f}]
    if ilhas:
        malhas.append({"v": [10, 0, 0, 11, 0, 0, 10, 0, 1], "f": [0, 1, 2]})
    return {"area": "m10_16_00_00", "malhas": malhas,
            "fogueiras": [{"id": 16675, "nome": "Servants' Quarters", "pos": [0.2, 0, 0.3]}],
            "itens": [{"lote": 10165010, "pos": [2.9, 0, 0.6], "itens": []}, {"lote": 7, "pos": [10.5, 0, 0.2], "itens": []}],
            "inimigos": [{"id": 145, "pos": [1.5, 0, 0.5]}]}


def test_route_follows_the_floor():
    area = faixa_area()
    r = ds2mapa.rota(area, ds2mapa.ponto_de(area, "fogueira", 16675), ds2mapa.ponto_de(area, "item", 10165010))
    assert r["pontos"][0] == [0.2, 0, 0.3] and r["pontos"][-1] == [2.9, 0, 0.6]
    assert 2.7 <= r["metros"] <= 4.0 and len(r["pontos"]) >= 3


def test_route_between_islands_is_none():
    area = faixa_area(ilhas=True)
    assert ds2mapa.rota(area, ds2mapa.ponto_de(area, "fogueira", 16675), ds2mapa.ponto_de(area, "item", 7)) is None


def test_unknown_point_raises():
    with pytest.raises(KeyError):
        ds2mapa.ponto_de(faixa_area(), "item", 123)
    with pytest.raises(KeyError):
        ds2mapa.ponto_de(faixa_area(), "baú", 1)


@pytest.mark.skipif(not (GAME / "GameDataEbl.bhd").exists(), reason="DS2 SotFS não instalado")
def test_real_route_servants_quarters_to_straid(tmp_path, capsys):
    assert ds2mapa.main(["rota", "--area", "m10_16_00_00", "--de", "fogueira:16675", "--ate", "fogueira:16650",
                         "--game", str(GAME), "--cache", str(tmp_path)]) == 0
    r = json.loads(capsys.readouterr().out)
    assert 150 < r["metros"] < 400 and len(r["pontos"]) > 10


def quadrado(x0, z0, x1, z1, y):
    """Dois triângulos cobrindo o retângulo (x0,z0)-(x1,z1) na altura y."""
    return {"v": [x0, y, z0, x1, y, z0, x1, y, z1, x0, y, z1], "f": [0, 1, 2, 0, 2, 3]}


def area_sintetica(malhas, fogueiras=(), itens=()):
    return {"area": "m10_16_00_00", "nome": "x", "malhas": list(malhas), "fogueiras": list(fogueiras),
            "itens": list(itens), "inimigos": []}


def area_poligono(poly):
    return abs(sum(poly[i][0] * poly[i - 1][1] - poly[i - 1][0] * poly[i][1] for i in range(len(poly)))) / 2


def test_floors_are_detected_by_height():
    area = ds2mapa.com_planta(area_sintetica(
        [quadrado(0, 0, 20, 20, 0.0), quadrado(0, 0, 20, 20, 10.0)],
        fogueiras=[{"id": 1, "nome": "a", "pos": [5, 10.5, 5]}], itens=[{"lote": 2, "pos": [5, 0.2, 5], "itens": []}]))
    andares = area["planta"]["andares"]
    assert [round(a["altura"]) for a in andares] == [0, 10]
    for a in andares:
        assert len(a["poligonos"]) == 1 and 300 <= area_poligono(a["poligonos"][0]) <= 500
    assert area["fogueiras"][0]["andar"] == andares[1]["id"] and area["itens"][0]["andar"] == andares[0]["id"]


def test_small_gap_between_mesh_pieces_is_closed():
    area = ds2mapa.com_planta(area_sintetica([quadrado(0, 0, 10, 10, 0.0), quadrado(10.3, 0, 20, 10, 0.0)]))
    andares = area["planta"]["andares"]
    assert len(andares) == 1 and len(andares[0]["poligonos"]) == 1
    assert len(andares[0]["poligonos"][0]) <= 8  # contorno simplificado, não a escadinha da grade


def test_floor_plan_is_cached_with_version():
    area = ds2mapa.com_planta(area_sintetica([quadrado(0, 0, 10, 10, 0.0)]))
    assert area["planta"]["versao"] == ds2mapa.PLANTA_VERSAO
    assert ds2mapa.com_planta(area) is area  # já tem a planta desta versão: não refaz


@pytest.mark.skipif(not (GAME / "GameDataEbl.bhd").exists(), reason="DS2 SotFS não instalado")
def test_real_lost_bastille_floors(tmp_path):
    area = ds2mapa.extrair_area(GAME, "m10_16_00_00", tmp_path)
    alturas = [a["altura"] for a in area["planta"]["andares"]]
    for esperada in (-78, 0, 8, 13, 22):
        assert any(abs(h - esperada) <= 2 for h in alturas), (esperada, alturas)
    assert all(a["poligonos"] for a in area["planta"]["andares"])
    ids = {a["id"] for a in area["planta"]["andares"]}
    assert all(p["andar"] in ids for p in area["fogueiras"] + area["itens"])


def test_actors_from_generators():
    loc = {145: (-49.3, 23.7, 39.1), 146: (-52.1, 23.9, 37.9), 300: (10.0, 0.0, 10.0),
           501: (0.0, 0.0, 0.0), 502: (4.0, 0.0, 0.0), 503: (2.0, 0.0, 6.0), 900: (50.0, 0.0, 50.0)}
    chr_ = {145: 76800000, 146: 76800001, 300: 75200000, 501: 32500000, 502: 32500001, 503: 32500002, 900: 12500000}
    npcs, chefes = ds2mapa.montar_atores(loc, chr_, (-78.0, 4.0, 562.0), {7680: "Straid of Olaphis", 7520: "Lucatiel of Mirrah"},
                                         [{"flag": 100962, "nome": "Ruin Sentinels", "wiki": "w", "familias": [3251, 3252, 3253]},
                                          {"flag": 1, "nome": "Sem gerador", "wiki": "", "familias": [9990]}])
    assert sorted(n["nome"] for n in npcs) == ["Lucatiel of Mirrah", "Straid of Olaphis"]  # dois geradores do Straid = um marcador
    straid = next(n for n in npcs if n["id"] == 7680)
    assert straid["pos"] == [-127.3, 27.7, 601.1]
    assert [c["nome"] for c in chefes] == ["Ruin Sentinels"]
    assert chefes[0]["pos"] == [-76.0, 4.0, 564.0] and chefes[0]["flag"] == 100962


@pytest.mark.skipif(not (GAME / "GameDataEbl.bhd").exists(), reason="DS2 SotFS não instalado")
def test_real_lost_bastille_actors(tmp_path):
    import math
    area = ds2mapa.extrair_area(GAME, "m10_16_00_00", tmp_path)
    fog = {f["nome"]: f["pos"] for f in area["fogueiras"]}
    npcs = {n["nome"]: n for n in area["npcs"]}
    assert "Straid of Olaphis" in npcs and math.dist(npcs["Straid of Olaphis"]["pos"], fog["Straid's Cell"]) < 5
    assert {"Ruin Sentinels", "Belfry Gargoyles"} <= {c["nome"] for c in area["chefes"]}
    assert all("andar" in a for a in area["npcs"] + area["chefes"])


def test_bonfire_zones_by_walking_distance_and_start():
    area = ds2mapa.com_planta(area_sintetica(
        [quadrado(0, 0, 10, 10, 0.0), quadrado(10, 0, 20, 10, 0.0)],
        fogueiras=[{"id": 1, "nome": "A", "pos": [2, 0, 5]}, {"id": 2, "nome": "B", "pos": [18, 0, 5]}],
        itens=[{"lote": 9, "pos": [3, 0, 5], "itens": []}]))
    area["inicio"] = [19, 0, 5]
    area = ds2mapa.com_zonas(area)
    zonas = area["zonas"]["lista"]
    assert [(z["ordem"], z["fogueira"]) for z in zonas] == [(1, 2), (2, 1)]  # B fica mais perto do início do mapa
    assert area["zonas"]["ordem_por"] == "inicio"
    assert area["itens"][0]["zona"] == 2 and area["fogueiras"][0]["zona"] == 2
    for z in zonas:
        polys = [p for ps in z["poligonos"].values() for p in ps]
        assert polys and 60 <= sum(area_poligono(p) for p in polys) <= 140


@pytest.mark.skipif(not (GAME / "GameDataEbl.bhd").exists(), reason="DS2 SotFS não instalado")
def test_real_lost_bastille_zones(tmp_path):
    area = ds2mapa.extrair_area(GAME, "m10_16_00_00", tmp_path)
    zonas = area["zonas"]["lista"]
    assert len(zonas) == 7 and sorted(z["ordem"] for z in zonas) == list(range(1, 8))
    assert area["zonas"]["ordem_por"] == "inicio"
    assert all(p.get("zona") for p in area["itens"] + area["npcs"] + area["chefes"])
