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
