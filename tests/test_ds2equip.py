import json

import pytest

import ds2calc
import ds2equip
import ds2regulation
from ds2save import load_item_names


def _real():
    try:
        return ds2regulation.find_regulation()
    except ds2regulation.SaveError:
        return None


def test_swap_argument():
    assert ds2equip.ler_troca("L1=Lizard Staff:0") == ("L1", ("Lizard Staff", 0))
    assert ds2equip.ler_troca("peito=Black Witch Robe") == ("peito", ("Black Witch Robe", 0))
    assert ds2equip.ler_troca("R3=-") == ("R3", (None, 0))
    with pytest.raises(ValueError):
        ds2equip.ler_troca("sem-igual")


def snapshot_vorcaro():
    def it(item_id, name, cat, upgrade=None):
        return {"id": item_id, "name": name, "category": cat, "quantity": 1, "upgrade": upgrade}
    return {
        "stats": {"VGR": 12, "END": 6, "VIT": 5, "ATN": 30, "STR": 10, "DEX": 18, "INT": 34, "FTH": 6, "ADP": 8},
        "equipped": {"hands": {"L1": {"id": 3800000, "name": "Sorcerer's Staff"}, "R1": {"id": 1700000, "name": "Uchigatana"},
                               "R2": {"id": 5400000, "name": "Pyromancy Flame"}, "R3": {"id": 3400000, "name": "#3400000"}},
                     "armor": {"cabeca": {"id": 21001100, "name": "#21001100"}, "peito": {"id": 22180101, "name": "Black Hollow Mage Robe"}},
                     "rings": [{"id": 40210000, "name": "Ring of Knowledge"}],
                     "spells": [{"id": 31020000, "name": "Great Soul Arrow"}, {"id": 31020000, "name": "Great Soul Arrow"},
                                {"id": 33020000, "name": "Fire Orb"}]},
        "inventory": [it(3800000, "Sorcerer's Staff", "SpellTools", 2), it(3800000, "Sorcerer's Staff", "SpellTools", 0),
                      it(1700000, "Uchigatana", "MeleeWeapons", 5), it(5400000, "Pyromancy Flame", "MeleeWeapons", 0)],
    }


@pytest.mark.skipif(_real() is None, reason="DS2 não instalado nesta máquina")
def test_real_equipment_now_and_plan():
    calc = ds2calc.load()
    out = ds2equip.equipamento(calc, load_item_names(), snapshot_vorcaro(),
                               {"L1": ("Lizard Staff", 0), "peito": ("Black Witch Robe", 0), "R2": ("Pyromancy Flame", 2)})
    slots = {s["slot"]: s for s in out["slots"]}
    assert slots["R1"]["agora"]["ar"] == 218 and slots["R1"]["agora"]["nivel"] == 5 and not slots["R1"]["muda"]
    assert slots["R1"]["agora"]["partes"]["DEX"] > 0
    assert slots["L1"]["agora"]["ar"]["magico"] == 205 and slots["L1"]["agora"]["nivel"] == 2  # maior upgrade do inventário
    assert slots["L1"]["plano"]["nome"] == "Lizard Staff" and slots["L1"]["plano"]["ar"]["magico"] == 240
    assert slots["R2"]["agora"]["ar"]["fogo"] == 223 and slots["R2"]["plano"]["ar"]["fogo"] == 265
    assert slots["R3"]["agora"] is None and slots["cabeca"]["agora"] is None  # punho e cabeça vazia
    assert slots["peito"]["plano"]["nome"] == "Black Witch Robe" and slots["peito"]["muda"]
    assert out["atributos"]["agora"]["INT"] == 39
    gsa = [f for f in out["sintonia"]["plano"] if f["nome"] == "Great Soul Arrow"]
    assert len(gsa) == 2 and gsa[0]["ar"] == 215 and gsa[0]["catalisador"] == "Lizard Staff"
    assert any(r["dado"] == "Great Soul Arrow" and r["agora"] == "184" and r["depois"] == "215" for r in out["resumo"])


@pytest.mark.skipif(_real() is None, reason="DS2 não instalado nesta máquina")
def test_cli_equipment(tmp_path, capsys):
    snap = tmp_path / "s.json"
    snap.write_text(json.dumps(snapshot_vorcaro()), encoding="utf-8")
    assert ds2equip.main(["--snapshot", str(snap), "--troca", "L1=Lizard Staff:0", "--atributo", "INT=35"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["atributos"]["plano"]["INT"] == 40
    assert ds2equip.main(["--snapshot", str(snap), "--troca", "L9=Lizard Staff"]) == 1
