import json
import struct

import pytest

import ds2calc
import ds2regulation
from test_ds2regulation import build_param


def synthetic_params():
    weapon = bytearray(32)
    struct.pack_into("<i", weapon, 8, 900)
    reinforce = bytearray(200)
    struct.pack_into("<f", reinforce, 0, 100.0)
    struct.pack_into("<f", reinforce, 36, 200.0)
    struct.pack_into("<ii", reinforce, 72, 10, 5)
    struct.pack_into("<f", reinforce, 160, 100.0)
    affect = bytearray(8 + 11 * 9 * 4)
    struct.pack_into("<f", affect, ds2regulation.scaling_offset(4, 0), 0.2)
    struct.pack_into("<f", affect, ds2regulation.scaling_offset(4, 1), 0.5)
    stats = {}
    for value, (b_str, b_dex) in {10: (50, 60), 20: (70, 80)}.items():
        row = bytearray(40)
        struct.pack_into("<II", row, 12, b_str, b_dex)
        stats[value] = bytes(row)
    return {
        "WeaponParam": build_param({1234: bytes(weapon)}),
        "WeaponReinforceParam": build_param({900: bytes(reinforce)}),
        "WeaponStatsAffectParam": build_param({5: bytes(affect)}),
        "PhysicalStatsPerLevelStatValuesParam": build_param(stats),
    }


def test_physical_ar_formula():
    calc = ds2calc.Calc(synthetic_params())
    # base +4 = 100 + (200 − 100) × 4/10 = 140; bônus = 0,2 × 50 (FOR 10) + 0,5 × 80 (DES 20) = 50
    assert calc.physical_ar(1234, 4, {"STR": 10, "DEX": 20}) == 190


def test_level_above_max_is_rejected():
    with pytest.raises(ds2calc.SaveError, match="nível"):
        ds2calc.Calc(synthetic_params()).physical_ar(1234, 11, {"STR": 10, "DEX": 20})


def test_unknown_weapon_is_rejected():
    with pytest.raises(ds2calc.SaveError, match="arma"):
        ds2calc.Calc(synthetic_params()).physical_ar(42, 0, {"STR": 10, "DEX": 20})


def _real():
    try:
        return ds2regulation.find_regulation()
    except ds2regulation.SaveError:
        return None


@pytest.mark.skipif(_real() is None, reason="DS2 não instalado nesta máquina")
@pytest.mark.parametrize("item_id, level, expected", [(1700000, 5, 218), (11110000, 0, 54), (3400000, 0, 49)])
def test_real_ar_matches_game_menu(item_id, level, expected):
    """Valores do menu Status do jogo com FOR 10 / DES 18 (print de 2026-10-06)."""
    calc = ds2calc.load()
    assert calc.physical_ar(item_id, level, {"STR": 10, "DEX": 18}) == expected


@pytest.mark.skipif(_real() is None, reason="DS2 não instalado nesta máquina")
def test_cli_ar_by_name(capsys):
    assert ds2calc.main(["ar", "--arma", "Uchigatana", "--nivel", "5", "--str", "10", "--dex", "18"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["ar_fisico"] == 218 and out["arma"] == "Uchigatana"


def test_stat_bonus_rows_by_element():
    assert ds2calc.bonus_rows({"INT": 26, "FTH": 6}) == {"magico": 26, "fogo": 16, "raio": 6, "sombrio": 6}


@pytest.mark.skipif(_real() is None, reason="DS2 não instalado nesta máquina")
@pytest.mark.parametrize("item_id, level, expected", [(3800000, 2, 356), (5400000, 0, 204)])
def test_real_catalyst_matches_game_menu(item_id, level, expected):
    """Menu Status com INT 26 / FÉ 6: Sorcerer's Staff +2 = 356, Pyromancy Flame = 204."""
    ar = ds2calc.load().catalyst_ar(item_id, level, {"INT": 26, "FTH": 6})
    assert sum(ar.values()) == expected


@pytest.mark.skipif(_real() is None, reason="DS2 não instalado nesta máquina")
def test_real_spell_damage_and_attunement():
    calc = ds2calc.load()
    ar = calc.catalyst_ar(3800000, 2, {"INT": 26, "FTH": 6})
    soul_arrow = calc.spell(31010000, ar, {"INT": 26, "FTH": 6, "ATN": 30})
    assert soul_arrow["elemento"] == "magico" and soul_arrow["ar"] == 161 and soul_arrow["slots"] == 1
    assert soul_arrow["usos"] == 32 and soul_arrow["requisito_ok"]
    homing = calc.spell(31060000, ar, {"INT": 26, "FTH": 6, "ATN": 30})
    assert homing["ar"] is None and not homing["requisito_ok"]  # pede INT 35
    assert calc.attunement(30) == {"slots": 6, "faixa": 3}


def snapshot_mago():
    def it(item_id, name, cat, upgrade=None):
        return {"id": item_id, "name": name, "category": cat, "quantity": 1, "upgrade": upgrade}
    return {
        "stats": {"VGR": 12, "END": 6, "VIT": 5, "ATN": 30, "STR": 10, "DEX": 18, "INT": 34, "FTH": 6, "ADP": 8},
        "equipped": {"hands": {"L1": {"id": 3800000, "name": "Sorcerer's Staff"}, "R2": {"id": 5400000, "name": "Pyromancy Flame"}},
                     "rings": [{"id": 40210000, "name": "Ring of Knowledge"}],
                     "spells": [{"id": 31020000, "name": "Great Soul Arrow"}, {"id": 31020000, "name": "Great Soul Arrow"},
                                {"id": 33020000, "name": "Fire Orb"}]},
        "inventory": [it(3800000, "Sorcerer's Staff", "SpellTools", 2), it(3800000, "Sorcerer's Staff", "SpellTools", 0),
                      it(5400000, "Pyromancy Flame", "MeleeWeapons", 0), it(11310000, "Golden Wing Shield", "Shields", 0),
                      it(31020000, "Great Soul Arrow", "Spells"), it(33020000, "Fire Orb", "Spells"),
                      it(31040000, "Great Heavy Soul Arrow", "Spells")],
    }


@pytest.mark.skipif(_real() is None, reason="DS2 não instalado nesta máquina")
def test_real_attunement_reads_equipped_spells_and_compares_catalysts():
    calc = ds2calc.load()
    out = ds2calc.sintonia(calc, snapshot_mago(), [(3830000, "Lizard Staff", 0), (5410000, "Dark Pyromancy Flame", 0)])
    assert out["atributos"]["INT"] == 39 and out["aneis"] == ["Ring of Knowledge +5 INT"]  # anel conta
    assert out["slots"]["usados"] == 3
    cats = {c["nome"]: c for c in out["catalisadores"]}
    assert cats["Sorcerer's Staff"]["nivel"] == 2 and cats["Sorcerer's Staff"]["equipado"]  # o maior upgrade
    assert "Golden Wing Shield" not in cats  # escudo com dano mágico não é catalisador
    assert "aviso" in cats["Dark Pyromancy Flame"] and not cats["Lizard Staff"]["tem"]
    f = {x["nome"]: x for x in out["feiticos"]}
    assert f["Great Soul Arrow"]["equipado"] == 2 and f["Great Soul Arrow"]["ar_atual"] == 184
    assert f["Great Soul Arrow"]["melhor"]["catalisador"] == "Lizard Staff"
    assert f["Great Heavy Soul Arrow"]["equipado"] == 0 and f["Great Heavy Soul Arrow"]["ar_atual"] == 225
    assert f["Fire Orb"]["ar_atual"] == 278 and f["Fire Orb"]["melhor"]["catalisador"] == "Pyromancy Flame"  # Dark fica de fora


@pytest.mark.skipif(_real() is None, reason="DS2 não instalado nesta máquina")
def test_cli_attunement(tmp_path, capsys):
    snap = tmp_path / "s.json"
    snap.write_text(json.dumps(snapshot_mago()), encoding="utf-8")
    assert ds2calc.main(["sintonia", "--snapshot", str(snap), "--candidato", "Lizard Staff:0"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert any(c["nome"] == "Lizard Staff" for c in out["catalisadores"])


# ---- infusão --------------------------------------------------------------------------------------------------------

def params_infusao():
    """Arma 1234: reforço 900 (físico e mágico 100 → 200 em +10), escala 5 (+k = infusão k), máscara aceita 0, 2 (Mágica)
    e 7 (Raw)."""
    weapon = bytearray(32)
    struct.pack_into("<i", weapon, 8, 900)
    reinforce = bytearray(244)
    struct.pack_into("<5f", reinforce, 0, 100.0, 100.0, 100.0, 100.0, 100.0)
    struct.pack_into("<5f", reinforce, 36, 200.0, 200.0, 200.0, 200.0, 200.0)
    struct.pack_into("<ii", reinforce, 72, 10, 5)
    struct.pack_into("<f", reinforce, 160, 100.0)
    struct.pack_into("<i", reinforce, 232, 1000)

    def affect(mult, por_tipo):
        row = bytearray(8 + 11 * 9 * 4)
        struct.pack_into("<2f", row, 0, mult, mult)
        for kind, valor in por_tipo.items():
            struct.pack_into("<f", row, ds2regulation.scaling_offset(4, kind), valor)
        return bytes(row)

    stats = {}
    for value, bonus in {10: (50, 60, 40, 40, 40, 40), 15: (55, 65, 70, 70, 70, 70), 20: (70, 80, 100, 90, 90, 90)}.items():
        row = bytearray(40)
        struct.pack_into("<6I", row, 12, *bonus)
        stats[value] = bytes(row)
    return {
        "WeaponParam": build_param({1234: bytes(weapon)}),
        "WeaponReinforceParam": build_param({900: bytes(reinforce)}),
        "WeaponStatsAffectParam": build_param({5: affect(0.0, {0: 0.2, 1: 0.5}), 7: affect(1.4, {0: 0.1, 1: 0.25, 2: 0.3}),
                                               12: affect(1.15, {0: 0.05, 1: 0.1})}),
        "PhysicalStatsPerLevelStatValuesParam": build_param(stats),
        "CustomAttrSpecParam": build_param({1000: struct.pack("<I", 0b10000101)}),
    }


STATS_INF = {"STR": 10, "DEX": 20, "INT": 20, "FTH": 10}


def test_elemental_infusion_splits_the_base_between_physical_and_the_element():
    calc = ds2calc.Calc(params_infusao())
    # base +4 = 140; × 1,4 / 2 = 98 de cada lado. Físico: 98 + 0,1 × 50 + 0,25 × 80 = 123. Mágico: 98 + 0,3 × 100 (INT 20) = 128
    assert calc.weapon_ar(1234, 4, 2, STATS_INF) == {"fisico": 123, "magico": 128}
    partes = calc.weapon_parts(1234, 4, 2, STATS_INF)
    assert partes["fisico"]["base"] == 98 and partes["magico"] == {"base": 98, "atributos": 30}


def test_raw_infusion_multiplies_the_physical_base():
    # 140 × 1,15 = 161; + 0,05 × 50 + 0,1 × 80 = 10,5 → 171
    assert ds2calc.Calc(params_infusao()).weapon_ar(1234, 4, 7, STATS_INF) == {"fisico": 171}


def test_no_infusion_keeps_the_physical_ar():
    calc = ds2calc.Calc(params_infusao())
    assert calc.weapon_ar(1234, 4, 0, STATS_INF) == {"fisico": calc.physical_ar(1234, 4, STATS_INF)} == {"fisico": 190}


def test_infusion_outside_the_mask_is_rejected():
    calc = ds2calc.Calc(params_infusao())
    assert calc.infusoes(1234) == [0, 2, 7]
    with pytest.raises(ds2calc.SaveError, match="não aceita"):
        calc.weapon_ar(1234, 4, 3, STATS_INF)


@pytest.mark.skipif(_real() is None, reason="DS2 não instalado nesta máquina")
def test_real_infusions_match_the_wiki_bases():
    """Wiki (tabela da Uchigatana): Mágica +10 = 161 físico / 161 mágico; Raw +10 = 264."""
    calc = ds2calc.load()
    st = {"STR": 10, "DEX": 18, "INT": 56, "FTH": 10}
    magica = calc.weapon_parts(1700000, 10, 2, st)
    assert magica["fisico"]["base"] == 161 and magica["magico"]["base"] == 161
    assert calc.weapon_parts(1700000, 10, 7, st)["fisico"]["base"] == 264
    assert calc.weapon_ar(1700000, 5, 0, {"STR": 10, "DEX": 18, "INT": 10, "FTH": 10}) == {"fisico": 218}  # menu do jogo


@pytest.mark.skipif(_real() is None, reason="DS2 não instalado nesta máquina")
def test_real_fire_uses_the_average_of_int_and_faith():
    calc = ds2calc.load()
    fogo = lambda i, f: calc.weapon_ar(1700000, 10, 1, {"STR": 10, "DEX": 18, "INT": i, "FTH": f})["fogo"]  # noqa: E731
    assert fogo(50, 10) == fogo(40, 20) == fogo(30, 30) and fogo(50, 30) > fogo(50, 10)


@pytest.mark.skipif(_real() is None, reason="DS2 não instalado nesta máquina")
def test_real_mask_and_unverified_infusions():
    calc = ds2calc.load()
    assert calc.infusoes(1700000) == list(range(10))
    assert calc.infusoes(3800000) == [0, 2, 4]  # cajado: Mágica e Sombria (wiki)
    assert calc.infusoes(4010000) == [0, 3, 4]  # sino: Raio e Sombria
    assert calc.infusoes(5400000) == [0]  # chama de piromancia
    assert calc.conferido(1700000, 2) and calc.conferido(1700000, 0)
    assert not calc.conferido(1700000, 8) and not calc.conferido(1700000, 9)  # Enchanted e Mundane
    assert not calc.conferido(1320000, 2)  # Heide Knight Sword já tem raio próprio


@pytest.mark.skipif(_real() is None, reason="DS2 não instalado nesta máquina")
def test_cli_ar_with_infusion(capsys):
    assert ds2calc.main(["ar", "--arma", "Uchigatana", "--nivel", "10", "--str", "10", "--dex", "18", "--int", "40",
                         "--fth", "10", "--infusao", "magica"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert set(out["ar"]) == {"fisico", "magico"} and out["infusao"] == "Mágica" and out["conferido"] is True
