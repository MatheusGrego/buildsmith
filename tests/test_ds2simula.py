import json

import pytest

import ds2calc
import ds2data
import ds2regulation
import ds2simula
from ds2save import SaveError, load_item_names

UCHI, OKH, BKH, SHARD, LARGE, CHUNK = 1700000, 3330000, 3280000, 60970000, 60975000, 60980000


def _real():
    try:
        return ds2regulation.find_regulation()
    except ds2regulation.SaveError:
        return None


pytestmark = pytest.mark.skipif(_real() is None, reason="DS2 não instalado nesta máquina")


def it(item_id, name, cat, upgrade=None, quantity=1, infusao=None):
    out = {"id": item_id, "name": name, "category": cat, "quantity": quantity, "upgrade": upgrade}
    if infusao is not None:
        out["infusao"] = infusao
    return out


def snap():
    return {"souls": 11583,
            "stats": {"VGR": 12, "END": 6, "VIT": 5, "ATN": 40, "STR": 18, "DEX": 20, "INT": 51, "FTH": 10, "ADP": 8},
            "equipped": {"hands": {"R1": {"id": OKH, "name": "Old Knight Halberd"}}, "armor": {},
                         "rings": [{"id": 40210000, "name": "Ring of Knowledge"}], "spells": []},
            "inventory": [it(OKH, "Old Knight Halberd", "MeleeWeapons", 0, infusao=0),
                          it(UCHI, "Uchigatana", "MeleeWeapons", 8, infusao=8), it(UCHI, "Uchigatana", "MeleeWeapons", 2, infusao=0),
                          it(SHARD, "Titanite Shard", "UpgradeMaterials", quantity=26),
                          it(LARGE, "Large Titanite Shard", "UpgradeMaterials", quantity=7)]}


@pytest.fixture(scope="module")
def regras():
    return ds2calc.load(), ds2data.load(), load_item_names()


def simular(regras, *args, **kw):
    calc, data, names = regras
    return ds2simula.simular(calc, data, names, snap(), *args, **kw)


def test_upgrade_and_new_infusion_cost_the_reinforcement_the_stone_and_mcduff(regras):
    r = simular(regras, OKH, 8, 1)
    mats = {m["item"]: m for m in r["falta"]["materiais"]}
    assert r["falta"]["almas"] == 9460 + 2000 and r["falta"]["almas_tem"] == 11583
    assert mats["Titanite Chunk"] == {"item": "Titanite Chunk", "id": CHUNK, "qtd": 3, "tem": 0}
    assert mats["Large Titanite Shard"]["tem"] == 7 and mats["Firedrake Stone"]["qtd"] == 1
    assert r["falta"]["ferreiro"] == "Steady Hand McDuff"
    assert r["agora"]["nivel"] == 0 and r["agora"]["ar"] == 250  # FOR 18 / DES 20 (tabela do jogo)
    assert "fogo" in r["peca"]["ar"] and r["infusao_nome"] == "Fogo" and r["conferido"]
    assert r["nivel_max"] == 10 and [i["k"] for i in r["infusoes"]] == list(range(10))
    assert r["infusoes"][1] == {"k": 1, "nome": "Fogo", "pedra": "Firedrake Stone"}


def test_going_back_to_normal_needs_a_palestone(regras):
    r = simular(regras, UCHI, 8, 0)  # a cópia de maior reforço é a Enchanted +8
    assert r["agora"]["infusao"] == 8
    assert [m["item"] for m in r["falta"]["materiais"]] == ["Palestone"] and r["falta"]["almas"] == 1000


def test_a_lower_level_has_no_reinforcement_cost_and_warns(regras):
    r = simular(regras, UCHI, 5, 8)
    assert r["falta"]["almas"] == 0 and r["falta"]["materiais"] == []
    assert any("não desfaz" in a for a in r["falta"]["avisos"])


def test_a_weapon_you_do_not_have_costs_from_plus_zero(regras):
    r = simular(regras, BKH, 3, 0)
    assert r["agora"] is None and any("não está no inventário" in a for a in r["falta"]["avisos"])
    assert r["falta"]["materiais"][0]["item"] == "Twinkling Titanite" and r["falta"]["materiais"][0]["qtd"] == 6
    assert r["falta"]["ferreiro"] == "qualquer ferreiro"


def test_an_infusion_the_weapon_does_not_take_is_an_error(regras):
    with pytest.raises(SaveError, match="não aceita"):
        regras_calc, data, names = regras
        ds2simula.simular(regras_calc, data, names, {**snap(), "inventory": []}, 3800000, 0, 1)  # cajado com Fogo


def test_weapons_of_the_inventory_once_each_with_the_best_copy(regras):
    armas = ds2simula.armas_do_inventario(regras[2], snap())
    assert [(a["nome"], a["nivel"], a["infusao"]) for a in armas] == [("Old Knight Halberd", 0, 0), ("Uchigatana", 8, 8)]


def test_cli(tmp_path, capsys):
    path = tmp_path / "s.json"
    path.write_text(json.dumps(snap()), encoding="utf-8")
    assert ds2simula.main(["--snapshot", str(path), "--item", "Old Knight Halberd", "--nivel", "8", "--infusao", "fogo"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["infusao_nome"] == "Fogo" and out["falta"]["almas"] == 11460
    assert ds2simula.main(["--snapshot", str(path), "--item", "Sorcerer's Staff", "--infusao", "fogo"]) == 1
