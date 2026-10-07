import json
import struct

import pytest

import ds2data
import ds2regulation
import ds2save
from test_ds2regulation import build_param

ITEM, SOUL, WEAPON, MAT = 61140000, 64040000, 1700000, 60975000


def shop_row(item_id, material=0, price_rate=1.0, qty=255):
    row = bytearray(36)
    struct.pack_into("<i", row, 0, item_id)
    struct.pack_into("<i", row, 16, material)
    struct.pack_into("<fi", row, 28, price_rate, qty)
    return bytes(row)


def item_row(price):
    row = bytearray(64)
    struct.pack_into("<i", row, 48, price)
    return bytes(row)


def synthetic():
    weapon = bytearray(32)
    struct.pack_into("<i", weapon, 8, 900)
    reinforce = bytearray(244)
    struct.pack_into("<i", reinforce, 240, 7)
    cost = bytearray(100)
    for lvl in range(1, 11):
        struct.pack_into("<i", cost, 4 * (lvl - 1), 100 * lvl)
        struct.pack_into("<i", cost, 40 + 4 * (lvl - 1), MAT)
        struct.pack_into("<H", cost, 80 + 2 * (lvl - 1), 1 + (lvl - 1) % 3)
    return ds2data.Data({
        "ShopLineupParam": build_param({76430000: shop_row(ITEM), 76200005: shop_row(ITEM, qty=10, price_rate=0.8),
                                        76801000: shop_row(WEAPON, material=SOUL, price_rate=0.0)}),
        "ItemParam": build_param({ITEM: item_row(2500), WEAPON: item_row(1000)}),
        "WeaponParam": build_param({WEAPON: bytes(weapon)}),
        "WeaponReinforceParam": build_param({900: bytes(reinforce)}),
        "ReinforceCostParam": build_param({7: bytes(cost)}),
    })


def test_shops_with_price_and_stock():
    lojas = synthetic().shops_for(ITEM)
    assert {(l["loja"], l["estoque"], l["preco"]) for l in lojas} == {("Steady Hand McDuff", None, 2500), ("Stone Trader Chloanne", 10, 2000)}


def test_trades_by_item_and_by_soul():
    data = synthetic()
    assert [(t["npc"], t["alma_id"], t["preco"]) for t in data.trades(item_id=WEAPON)] == [("Straid of Olaphis", SOUL, 0)]
    assert [t["item_id"] for t in data.trades(soul_id=SOUL)] == [WEAPON]


def test_upgrade_cost_sums_levels():
    cost = synthetic().upgrade_cost(WEAPON, 4, 6)
    assert [n["nivel"] for n in cost["niveis"]] == [5, 6]
    assert cost["almas_total"] == 500 + 600
    assert cost["materiais"] == {MAT: 2 + 3}


def test_area_status_from_bosses():
    snap = {"progresso": {"chefes": [
        {"nome": "Flexile Sentry", "area": "No-man's Wharf", "derrotado": True},
        {"nome": "Ruin Sentinels", "area": "Lost Bastille", "derrotado": False}]}}
    status = ds2data.area_status(snap)
    acesso = {a["area"]: a["acesso"] for a in status["areas"]}
    assert status["mais_avancada"] == "No-Man's Wharf"
    assert acesso["The Lost Bastille"] == "agora" and acesso["Majula"] == "agora"
    assert acesso["Huntsman's Copse"] == "em_breve" and acesso["Drangleic Castle"] == "tarde"


def _real():
    try:
        return ds2regulation.find_regulation()
    except ds2regulation.SaveError:
        return None


@pytest.mark.skipif(_real() is None, reason="DS2 não instalado nesta máquina")
def test_real_game_data():
    data = ds2data.load()
    names = ds2save.load_item_names()
    nid = {n: i for i, (_, n) in names.items()}
    mcduff = [l for l in data.shops_for(nid["Large Titanite Shard"]) if l["loja"] == "Steady Hand McDuff"]
    assert mcduff and mcduff[0]["preco"] == 2500 and mcduff[0]["estoque"] is None
    cost = data.upgrade_cost(1700000, 5, 6)
    assert cost["almas_total"] == 1320 and cost["materiais"] == {nid["Large Titanite Shard"]: 3}
    assert any(t["npc"] == "Weaponsmith Ornifex" and t["alma_id"] == nid["Old Paledrake Soul"]
               for t in data.trades(item_id=nid["Moonlight Greatsword"]))


@pytest.mark.skipif(_real() is None, reason="DS2 não instalado nesta máquina")
def test_cli_onde_comprar(capsys):
    assert ds2data.main(["onde-comprar", "--item", "Large Titanite Shard"]) == 0
    assert any(l["loja"] == "Steady Hand McDuff" for l in json.loads(capsys.readouterr().out)["lojas"])
