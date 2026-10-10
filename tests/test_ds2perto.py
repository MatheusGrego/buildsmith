import ds2perto


class FakeData:
    weapons = {1: {"reinforce_id": 1, "req_str": 0, "req_dex": 0, "req_int": 10, "req_fth": 0},
               2: {"reinforce_id": 1, "req_str": 0, "req_dex": 0, "req_int": 0, "req_fth": 0},
               3: {"reinforce_id": 1, "req_str": 9, "req_dex": 13, "req_int": 0, "req_fth": 0},
               4: {"reinforce_id": 1, "req_str": 40, "req_dex": 0, "req_int": 0, "req_fth": 0}}

    def shops_for(self, item_id):
        return [{"loja": "Carhillion of the Fold", "preco": 1000, "estoque": None}] if item_id == 1 else []


class FakeCalc:
    reinforce = {1: {"nivel_max": 10}}

    def catalyst_ar(self, item_id, nivel, stats):
        return {1: {"magico": 180 + nivel}, 2: {"fogo": 270 + nivel}}.get(item_id, {})

    def physical_ar(self, item_id, nivel, stats):
        return {3: 158, 4: 300}[item_id] + nivel


NAMES = {1: ("SpellTools", "Sorcerer's Staff"), 2: ("MeleeWeapons", "Dark Pyromancy Flame"),
         3: ("MeleeWeapons", "Falchion"), 4: ("MeleeWeapons", "Greataxe"), 5: ("Armor", "Black Witch Robe"),
         6: ("Armor", "Tattered Cloth Hood"), 7: ("Rings", "Ring of Knowledge")}
SNAP = {"stats": {"STR": 10, "DEX": 18, "INT": 34, "FTH": 6, "ATN": 30},
        "equipped": {"rings": [{"name": "Ring of Knowledge"}]}, "inventory": [{"id": 1}]}
CHAO = {2: [{"area": "m10_25_00_00", "nome_area": "The Gutter", "lote": 9, "acesso": "agora"}],
        3: [{"area": "m10_16_00_00", "nome_area": "The Lost Bastille", "lote": 8, "acesso": "agora"}],
        4: [{"area": "m10_19_00_00", "nome_area": "Iron Keep", "lote": 7, "acesso": "tarde"}],
        6: [{"area": "m10_25_00_00", "nome_area": "The Gutter", "lote": 6, "acesso": "agora"}]}


def test_catalysts_put_hollowing_ones_last_with_a_warning():
    out = ds2perto.perto("catalisadores", SNAP, NAMES, FakeData(), FakeCalc(), CHAO)
    assert [l["nome"] for l in out] == ["Sorcerer's Staff", "Dark Pyromancy Flame"]
    staff, dark = out
    assert staff["tem"] and staff["lojas"][0]["loja"] == "Carhillion of the Fold" and staff["ar_max"] == {"magico": 190}
    assert "Hollowing" in dark["aviso"] and dark["chao"][0]["nome_area"] == "The Gutter"


def test_weapons_only_from_open_areas_and_requirement_check():
    out = ds2perto.perto("armas", SNAP, NAMES, FakeData(), FakeCalc(), CHAO)
    assert [l["nome"] for l in out] == ["Falchion"]  # o Greataxe só está numa área "tarde"
    assert out[0]["requisito_ok"] and out[0]["requisito"] == {"STR": 9, "DEX": 13}


def test_armor_is_grouped_by_set_and_filtered_by_name():
    out = ds2perto.perto("armaduras", SNAP, NAMES, FakeData(), FakeCalc(), CHAO, "cloth|witch")
    assert [(l["set"], l["nome"]) for l in out] == [("Tattered Cloth", "Tattered Cloth Hood")]


class FakeCalcFeitico(FakeCalc):
    weapons = {1: {"reinforce_id": 1}, 2: {"reinforce_id": 1}}
    spells = {31: {}, 32: {}}

    def spell(self, spell_id, catalyst, stats):
        elem = {31: "magico", 32: "fogo"}[spell_id]
        mult = {31: 1.8, 32: 1.0}[spell_id]
        return {"elemento": elem, "ar": int(catalyst[elem] * mult) if elem in catalyst else None, "usos": 2, "slots": 1,
                "req_int": 40 if spell_id == 31 else 0, "req_fth": 0, "requisito_ok": spell_id != 31}


def test_spells_use_the_best_catalyst_you_have_and_skip_hollowing_flames():
    names = {**NAMES, 31: ("Spells", "Soul Spear"), 32: ("Spells", "Fireball")}
    snap = {**SNAP, "equipped": {"rings": [{"name": "Ring of Knowledge"}], "hands": {}},
            "inventory": [{"id": 1, "name": "Sorcerer's Staff", "category": "SpellTools", "upgrade": 0},
                          {"id": 2, "name": "Dark Pyromancy Flame", "category": "MeleeWeapons", "upgrade": 0}]}
    chao = {31: [{"area": "m10_23_00_00", "nome_area": "Huntsman's Copse", "lote": 1, "acesso": "agora"}],
            32: [{"area": "m10_18_00_00", "nome_area": "No-man's Wharf", "lote": 2, "acesso": "agora"}]}
    out = {l["nome"]: l for l in ds2perto.perto("feiticos", snap, names, FakeData(), FakeCalcFeitico(), chao)}
    assert out["Soul Spear"]["ar"] == 324 and out["Soul Spear"]["catalisador"] == "Sorcerer's Staff"
    assert out["Soul Spear"]["requisito"] == {"INT": 40} and not out["Soul Spear"]["requisito_ok"]
    assert out["Fireball"]["ar"] is None  # a única chama é a Dark (escala com Hollowing): fica de fora
