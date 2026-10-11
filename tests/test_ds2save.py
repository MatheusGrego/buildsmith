import json
import struct

import pytest

import ds2save


def test_level_cost_65_to_66_matches_game():
    assert ds2save.levels_cost(65, 66)["total"] == 6657


def test_level_phase_vgr_to_20():
    result = ds2save.levels_cost(65, 76)
    assert result["total"] == 82736
    assert [s["level"] for s in result["steps"]] == list(range(66, 77))


def test_levels_beyond_table_raises():
    with pytest.raises(ds2save.SaveError):
        ds2save.levels_cost(65, 900)


def test_levels_requires_increasing_range():
    with pytest.raises(ds2save.SaveError):
        ds2save.levels_cost(70, 70)


def test_cli_levels_prints_json(capsys):
    assert ds2save.main(["levels", "--from", "65", "--to", "66"]) == 0
    assert json.loads(capsys.readouterr().out)["total"] == 6657


from conftest import build_bnd4


def test_read_bnd4_roundtrip():
    data = build_bnd4({"USER_DATA000": b"resumo", "USER_DATA001": bytes(range(40))})
    entries = ds2save.read_bnd4(data)
    assert entries["USER_DATA000"][:6] == b"resumo"
    assert entries["USER_DATA001"][:40] == bytes(range(40))


def test_read_bnd4_rejects_other_files():
    with pytest.raises(ds2save.SaveError):
        ds2save.read_bnd4(b"PK\x03\x04 isto e um zip")


import os

from conftest import make_slot


def test_item_names_known_and_unknown(names):
    assert ds2save.item_name(names, 31010000) == "Soul Arrow"
    assert ds2save.item_name(names, 99) == "desconhecido #99"


def test_snapshot_reads_character(save_file):
    snap = ds2save.snapshot(save_file)
    assert snap["slot"] == 1
    assert snap["name"] == "Personagem Um"
    assert snap["level"] == 65 and snap["souls"] == 1234 and snap["soul_memory"] == 221118
    assert snap["stats"] == {"VGR": 9, "END": 6, "VIT": 5, "ATN": 30, "STR": 10, "DEX": 18, "INT": 26, "FTH": 6, "ADP": 8}
    assert snap["equipped"]["hands"]["R1"]["name"] == "Uchigatana"
    assert snap["equipped"]["hands"]["L1"]["name"] == "Sorcerer's Staff"
    assert [r["name"] for r in snap["equipped"]["rings"]] == ["Clear Bluestone Ring"]
    assert [s["name"] for s in snap["equipped"]["spells"]] == ["Soul Arrow"]


def test_snapshot_inventory(save_file):
    inv = {i["name"]: i for i in ds2save.snapshot(save_file)["inventory"]}
    assert inv["Uchigatana"]["upgrade"] == 5 and inv["Uchigatana"]["quantity"] == 1
    assert inv["Human Effigy"]["quantity"] == 15 and inv["Human Effigy"]["upgrade"] is None
    assert inv["Soldier Key"]["category"] == "KeyItems"
    assert inv["desconhecido #12345678"]["category"] == "?"


def test_snapshot_lists_unknown_ids(save_file):
    assert 12345678 in ds2save.snapshot(save_file)["unknown_ids"]


def test_list_slots_skips_empty(save_file):
    assert ds2save.list_slots(save_file) == [{"slot": 1, "name": "Personagem Um", "level": 65}]


def test_multiple_characters_require_slot(tmp_path, names):
    path = tmp_path / "multi.sl2"
    path.write_bytes(build_bnd4({"USER_DATA001": bytes(make_slot(name="A")), "USER_DATA002": bytes(make_slot(name="B", level=10)),
                                 "USER_DATA011": bytes(0x30000), "USER_DATA012": bytes(0x30000)}))
    with pytest.raises(ds2save.SaveError, match="--slot"):
        ds2save.snapshot(path, names=names)
    assert ds2save.snapshot(path, slot=2, names=names)["name"] == "B"


def test_slot_by_name_picks_character_in_shared_save(tmp_path, capsys):
    path = tmp_path / "multi.sl2"
    path.write_bytes(build_bnd4({"USER_DATA001": bytes(make_slot(name="Personagem Um")),
                                 "USER_DATA002": bytes(make_slot(name="Personagem (teste)", level=10)),
                                 "USER_DATA011": bytes(0x30000), "USER_DATA012": bytes(0x30000)}))
    assert ds2save.slot_by_name(path, "personagem (TESTE)") == 2
    assert ds2save.slot_by_name(path, "Personagem Um") == 1
    with pytest.raises(ds2save.SaveError, match="1: Personagem Um, 2: Personagem"):
        ds2save.slot_by_name(path, "Outro")
    assert ds2save.main(["snapshot", "--save", str(path), "--personagem", "Personagem (teste)"]) == 0
    assert json.loads(capsys.readouterr().out)["slot"] == 2


def test_characters_with_the_same_name_get_unique_slugs(tmp_path, names):
    path = tmp_path / "multi.co2"
    a, b = make_slot(name="pssk", level=32), make_slot(name="pssk", level=87)
    b[ds2save.OFF_MAPA:ds2save.OFF_MAPA + 4] = bytes([0, 0, 0x04, 0x0A])  # m10_04_00_00
    path.write_bytes(build_bnd4({"USER_DATA001": bytes(a), "USER_DATA002": bytes(b),
                                 "USER_DATA011": bytes(0x30000), "USER_DATA012": bytes(0x30000)}))
    assert ds2save.slot_by_name(path, "pssk") == 2  # o nome sozinho é o de maior nível
    assert ds2save.slot_by_name(path, "pssk-1") == 1
    assert [(p["slot"], p["slug"]) for p in ds2save.personagens(path, names=names)] == [(1, "pssk-1"), (2, "pssk")]
    pos = ds2save.posicoes(path)
    assert pos["pssk"]["slot"] == 2 and pos["pssk"]["area"] == "m10_04_00_00" and pos["pssk-1"]["slot"] == 1


def test_lit_bonfires_come_from_the_world_block(tmp_path, names, capsys):
    world = bytearray(0x30000)
    ids = [2650, 4650, 16650, 16655]
    struct.pack_into(f"<{len(ids)}H", world, ds2save.OFF_FOGUEIRAS, *ids)
    estado = ds2save.OFF_FOGUEIRAS + 2 * ds2save.FOGUEIRAS_MAX
    world[estado:estado + 4] = bytes([1, 1, 0, 1])  # Things Betwixt, Majula e Exile Holding Cells; Straid's Cell apagada
    path = tmp_path / "a.co2"
    path.write_bytes(build_bnd4({"USER_DATA001": bytes(make_slot(name="pssk")), "USER_DATA011": bytes(world)}))
    assert ds2save.fogueiras_acesas(bytes(world)) == [2650, 4650, 16655]
    assert ds2save.posicoes(path)["pssk"]["fogueiras"] == [2650, 4650, 16655]
    assert ds2save.snapshot(path, names=names, regulation=False)["progresso"]["fogueiras"] == [2650, 4650, 16655]
    assert ds2save.main(["fogueiras", "--save", str(path), "--personagem", "pssk"]) == 0
    assert json.loads(capsys.readouterr().out) == {"slot": 1, "acesas": [2650, 4650, 16655]}
    assert ds2save.fogueiras_acesas(b"curto") == []


def test_find_save_picks_newest(tmp_path):
    folder = tmp_path / "DarkSoulsII" / "0110000100000000"
    folder.mkdir(parents=True)
    old, new = folder / "DS2SOFS0000.sl2", folder / "DS2SOFS0000.co2"
    old.write_bytes(b"x")
    new.write_bytes(b"y")
    os.utime(old, (1, 1))
    assert ds2save.find_save(str(tmp_path)) == new


def test_cli_snapshot_prints_json(save_file, capsys):
    assert ds2save.main(["snapshot", "--save", str(save_file)]) == 0
    assert json.loads(capsys.readouterr().out)["name"] == "Personagem Um"


def _real_save():
    try:
        return ds2save.find_save()
    except ds2save.SaveError:
        return None


@pytest.mark.skipif(_real_save() is None, reason="sem save real do DS2 nesta máquina")
def test_real_save_invariants():
    path = _real_save()
    slots = ds2save.list_slots(path)
    assert slots, "nenhum personagem encontrado no save real"
    snap = ds2save.snapshot(path, slot=slots[0]["slot"])
    assert snap["name"]
    assert all(1 <= v <= 99 for v in snap["stats"].values())
    assert any(i["name"] == "Uchigatana" for i in snap["inventory"])


def test_find_save_prefers_seamless_extension(tmp_path):
    folder = tmp_path / "DarkSoulsII" / "0110000100000000"
    folder.mkdir(parents=True)
    test_save, main_save = folder / "DS2SOFS0000.teste", folder / "DS2SOFS0000.co2"
    test_save.write_bytes(b"t")
    main_save.write_bytes(b"m")
    os.utime(test_save, (1, 1))  # o principal é mais novo, mas o ini manda usar .teste
    game = tmp_path / "Game"
    (game / "SeamlessCoop").mkdir(parents=True)
    (game / "SeamlessCoop" / "ds2sc_settings.ini").write_text("[SAVE]\nsave_file_extension = teste\n", encoding="utf-8")
    assert ds2save.find_save(str(tmp_path), game_dir=game) == test_save
    assert ds2save.seamless_extension(game) == "teste"


def test_armor_uses_item_ids(tmp_path):
    slot = make_slot(name="A")
    struct.pack_into("<4I", slot, ds2save.OFF_ARMOR, 12460100, 12460101, 12460102, 12460103)
    path = tmp_path / "a.sl2"
    path.write_bytes(build_bnd4({"USER_DATA001": bytes(slot), "USER_DATA011": bytes(0x30000)}))
    armor = ds2save.snapshot(path, names={22460100: ("Armor", "Tseldora Cap")}, regulation=False)["equipped"]["armor"]
    assert armor["cabeca"] == {"id": 22460100, "name": "Tseldora Cap"}


def test_slot_by_slug_and_character_list(tmp_path, names):
    path = tmp_path / "multi.sl2"
    path.write_bytes(build_bnd4({"USER_DATA001": bytes(make_slot(name="Personagem Um")),
                                 "USER_DATA002": bytes(make_slot(name="Personagem (teste)", level=10)),
                                 "USER_DATA011": bytes(0x30000), "USER_DATA012": bytes(0x30000)}))
    assert ds2save.slot_by_name(path, "personagem-teste") == 2
    lista = ds2save.personagens(path, names=names)
    assert [(p["slot"], p["slug"], p["nivel"]) for p in lista] == [(1, "personagem-um", 65), (2, "personagem-teste", 10)]
    assert set(lista[0]["equipado"]) == {"cabeca", "peito", "maos", "pernas", "R1", "L1"}


def test_position_and_map_from_slot(tmp_path, capsys):
    slot = make_slot(name="A")
    struct.pack_into("<3f", slot, ds2save.OFF_POS, -150.72, 12.32, 481.19)
    slot[ds2save.OFF_MAPA:ds2save.OFF_MAPA + 4] = bytes([0, 0, 0x10, 0x0A])  # m10_16_00_00
    path = tmp_path / "a.sl2"
    path.write_bytes(build_bnd4({"USER_DATA001": bytes(slot), "USER_DATA011": bytes(0x30000)}))
    assert ds2save.posicao(path, 1) == {"area": "m10_16_00_00", "pos": [-150.72, 12.32, 481.19]}
    assert ds2save.main(["posicao", "--save", str(path), "--personagem", "A"]) == 0
    assert json.loads(capsys.readouterr().out)["area"] == "m10_16_00_00"
    with pytest.raises(ds2save.SaveError, match="vazio"):
        ds2save.posicao(path, 2)


@pytest.mark.skipif(_real_save() is None, reason="sem save real do DS2 nesta máquina")
def test_real_save_position_is_on_a_known_map():
    import re
    path = _real_save()
    for s in ds2save.list_slots(path):
        p = ds2save.posicao(path, s["slot"])
        assert re.match(r"^m\d\d_\d\d_\d\d_\d\d$", p["area"]) and all(abs(c) < 5000 for c in p["pos"])


def test_empty_hand_and_armor_slots_are_left_out(tmp_path, names):
    slot = make_slot(name="A")
    struct.pack_into("<6I", slot, ds2save.OFF_HANDS, 3800000, 1700000, 3400000, 3400000, 3400000, 3400000)
    struct.pack_into("<4I", slot, ds2save.OFF_ARMOR, 11001100, 12180101, 11001102, 11001103)
    path = tmp_path / "a.sl2"
    path.write_bytes(build_bnd4({"USER_DATA001": bytes(slot), "USER_DATA011": bytes(0x30000)}))
    eq = ds2save.snapshot(path, names=names, regulation=False)["equipped"]
    assert set(eq["hands"]) == {"L1", "R1"}  # punho = mão vazia
    assert list(eq["armor"]) == ["peito"]  # 2100110x = sem peça


def test_live_state_has_inventory_and_equipment(save_file, names):
    v = ds2save.ao_vivo(save_file, names)["personagem-um"]
    assert v["nivel"] == 65 and v["stats"]["DEX"] == 18 and v["almas"] == 1234
    itens = {i["nome"]: i for i in v["itens"]}
    assert itens["Human Effigy"]["qtd"] == 15 and itens["Uchigatana"]["up"] == 5 and itens["Soldier Key"]["cat"] == "KeyItems"
    assert {"Uchigatana", "Sorcerer's Staff", "Clear Bluestone Ring", "Soul Arrow"} <= set(v["equipado"])
    assert "desconhecido #12345678" not in itens  # item que o jogo não nomeia fica de fora


def test_live_state_has_defeated_bosses(world_save, names):  # o save_file e o world_save são o mesmo arquivo
    w = ds2save.ao_vivo(world_save, names)["personagem-um"]
    assert set(w["chefes"]) == {"The Pursuer", "The Last Giant"}  # flags 100968 e 100971 ligadas


def _registro(mapa: int, pares=(), lotes=()) -> bytes:
    """Registro de 0xC08 da tabela de eventos do bloco de mundo: mapa, n, 192 pares, 192 lotes e o estado de cada lote."""
    reg = bytearray(0xC08)
    struct.pack_into("<II", reg, 0, mapa, len(pares))
    for i, (ev, est) in enumerate(pares):
        struct.pack_into("<II", reg, 8 + 8 * i, ev, est)
    for i, (lote, est) in enumerate(lotes):
        struct.pack_into("<I", reg, 0x608 + 4 * i, lote)
        struct.pack_into("<I", reg, 0x908 + 4 * i, est)
    return bytes(reg)


def _mundo(onde=0x2EF2C) -> bytes:
    bastille = _registro(0x0A100000, [(10160432, 30), (10160440, 10), (10162020, 33), (10165010, 80), (10165020, 20)],
                         [(10166180, 0x1100001), (10166190, 0x100401), (10166201, 0x100401)])
    harvest = _registro(0x0A110000, [(10172100, 20), (10173200, 10)], [(10176160, 0x1100003), (0, 0)])
    majula = _registro(0x0A040000, [(10040450, 50)], [])
    w = bytearray(0x50000)
    w[0x100:0x104] = struct.pack("<I", 0x0A040000)  # cabeçalho de outra tabela: não confunde a busca
    w[onde:onde + 3 * 0xC08] = bastille + harvest + majula
    return bytes(w)


def test_world_state_follows_the_rule_found_in_the_save():
    refs = ["porta:10160432", "porta:10160440", "porta:10040450", "alavanca:10172100", "alavanca:10173200",
            "bau:10165010", "bau:10165020", "lote:10166180", "lote:10166190", "lote:10176160", "lote:10166200",
            "lote:10169999", "porta:10169999", "elevador:10162020", "porta:99"]
    for onde in (0x2EF2C, 0x3AF3C):  # a tabela muda de lugar entre gravações
        estado = ds2save.estado_mundo(_mundo(onde), refs)
        assert estado == {
            "porta:10160432": True, "porta:10160440": False, "porta:10040450": None,  # 50: estado sem regra
            "alavanca:10172100": True, "alavanca:10173200": False,
            "bau:10165010": True, "bau:10165020": False,
            "lote:10166180": True, "lote:10166190": False, "lote:10176160": True,
            "lote:10166200": False,  # Bonfire Ascetic: o save tem o lote do NG+ (…01) para o …00 do mapa
            "lote:10169999": None, "porta:10169999": None, "elevador:10162020": None, "porta:99": None,
        }


def test_world_without_the_table_has_no_state():
    assert ds2save.estado_mundo(bytes(0x1000), ["porta:10160432", "lote:10166180"]) == {
        "porta:10160432": None, "lote:10166180": None}


@pytest.mark.skipif(_real_save() is None, reason="sem save real do DS2 nesta máquina")
def test_real_save_world_table_and_the_spike_door():
    path = _real_save()
    entradas = ds2save.blocos(path)
    for s in ds2save.list_slots(path):
        tabela = ds2save.tabela_eventos(entradas[f"USER_DATA{10 + s['slot']:03d}"])
        assert len(tabela) >= 20 and 1004 in tabela  # Majula sempre está lá
        if s["name"] == "Personagem Um":  # o personagem do spike: cela da Bastille aberta com a Bastille Key
            assert ds2save.estado_mundo(entradas[f"USER_DATA{10 + s['slot']:03d}"], ["porta:10160432"]) == {"porta:10160432": True}
