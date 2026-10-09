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
    assert snap["name"] == "Melatonina Vorcaro"
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
    assert ds2save.list_slots(save_file) == [{"slot": 1, "name": "Melatonina Vorcaro", "level": 65}]


def test_multiple_characters_require_slot(tmp_path, names):
    path = tmp_path / "multi.sl2"
    path.write_bytes(build_bnd4({"USER_DATA001": bytes(make_slot(name="A")), "USER_DATA002": bytes(make_slot(name="B", level=10)),
                                 "USER_DATA011": bytes(0x30000), "USER_DATA012": bytes(0x30000)}))
    with pytest.raises(ds2save.SaveError, match="--slot"):
        ds2save.snapshot(path, names=names)
    assert ds2save.snapshot(path, slot=2, names=names)["name"] == "B"


def test_slot_by_name_picks_character_in_shared_save(tmp_path, capsys):
    path = tmp_path / "multi.sl2"
    path.write_bytes(build_bnd4({"USER_DATA001": bytes(make_slot(name="Melatonina Vorcaro")),
                                 "USER_DATA002": bytes(make_slot(name="Melatonina (teste)", level=10)),
                                 "USER_DATA011": bytes(0x30000), "USER_DATA012": bytes(0x30000)}))
    assert ds2save.slot_by_name(path, "melatonina (TESTE)") == 2
    assert ds2save.slot_by_name(path, "Melatonina Vorcaro") == 1
    with pytest.raises(ds2save.SaveError, match="1: Melatonina Vorcaro, 2: Melatonina"):
        ds2save.slot_by_name(path, "Outro")
    assert ds2save.main(["snapshot", "--save", str(path), "--personagem", "Melatonina (teste)"]) == 0
    assert json.loads(capsys.readouterr().out)["slot"] == 2


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
    assert json.loads(capsys.readouterr().out)["name"] == "Melatonina Vorcaro"


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
    path.write_bytes(build_bnd4({"USER_DATA001": bytes(make_slot(name="Melatonina Vorcaro")),
                                 "USER_DATA002": bytes(make_slot(name="Melatonina (teste)", level=10)),
                                 "USER_DATA011": bytes(0x30000), "USER_DATA012": bytes(0x30000)}))
    assert ds2save.slot_by_name(path, "melatonina-teste") == 2
    lista = ds2save.personagens(path, names=names)
    assert [(p["slot"], p["slug"], p["nivel"]) for p in lista] == [(1, "melatonina-vorcaro", 65), (2, "melatonina-teste", 10)]
    assert set(lista[0]["equipado"]) == {"cabeca", "peito", "maos", "pernas", "R1", "L1"}
