import json

import pytest

import ds2arquivos
import ds2fontes
import ds2save

ITEM, ARMA, ALMA, CHAVE = 61140000, 1700000, 64040000, 50990000
TIPO = 300100
AREAS = {"m10_04_00_00": {"nome": "Majula", "fogueiras": [14650], "ordem": -1},
         "m10_10_00_00": {"nome": "Forest of Fallen Giants", "fogueiras": [10670], "ordem": 1},
         "m10_18_00_00": {"nome": "No-man's Wharf", "fogueiras": [18650], "ordem": 4},
         "m10_16_00_00": {"nome": "The Lost Bastille", "fogueiras": [16650], "ordem": 5},
         "m10_19_00_00": {"nome": "Iron Keep", "fogueiras": [19655], "ordem": 19},
         "m50_35_00_00": {"nome": "Shulva, Sanctum City", "fogueiras": [35650], "ordem": 100}}


def corredor(area, fogueira, x_fog=1.0, **listas):
    """Corredor reto de 40 m (x de 0 a 40, z de 0 a 4) com uma fogueira perto do começo."""
    return {"area": area, "nome": AREAS[area]["nome"], "malhas": [{"v": [0, 0, 0, 40, 0, 0, 40, 0, 4, 0, 0, 4], "f": [0, 1, 2, 0, 2, 3]}],
            "fogueiras": [{"id": fogueira, "nome": f"Fogueira {fogueira}", "pos": [x_fog, 0.0, 2.0]}],
            **{k: [] for k in ("itens", "npcs", "chefes", "inimigos", "objetos")}, **listas}


PORTA = {"parte": "o00_0316_0002", "cat": "porta", "nome": "Iron Door", "modelo": "o00_0316", "pos": [25.0, 0.0, 2.0],
         "rot": [0.0, 90.0, 0.0], "chave": [CHAVE, "Antiquated Key"], "chave_fonte": "evento", "estado_ref": "porta:1"}
MAPAS = {
    "m10_04_00_00": corredor("m10_04_00_00", 14650, npcs=[{"id": 7620, "nome": "Stone Trader Chloanne", "pos": [30.0, 0.0, 2.0]}]),
    "m10_18_00_00": corredor("m10_18_00_00", 18650, chefes=[{"flag": 100961, "nome": "Flexile Sentry", "pos": [20.0, 0.0, 2.0]}],
                             inimigos=[{"id": 7, "tipo": TIPO, "papel": None, "pos": [12.0, 0.0, 2.0]},
                                       {"id": 8, "tipo": TIPO, "papel": None, "pos": [36.0, 0.0, 2.0]}]),
    "m10_16_00_00": corredor("m10_16_00_00", 16650, objetos=[PORTA],
                             npcs=[{"id": 7643, "nome": "Steady Hand McDuff", "pos": [15.0, 0.0, 2.0]},
                                   {"id": 7680, "nome": "Straid of Olaphis", "pos": [5.0, 0.0, 2.0]}],
                             itens=[{"lote": 1000, "pos": [30.0, 0.0, 2.0], "itens": [{"id": ITEM, "nome": "Magic Stone", "qtd": 2}],
                                     "no": "bau", "estado_ref": "lote:1000"}]),
}
INDICE = {"areas": AREAS, "itens": {
    str(ITEM): {"id": ITEM, "nome": "Magic Stone", "cat": "material", "req": {}, "fontes": [
        {"tipo": "compra", "npc": "Stone Trader Chloanne", "linha": 76200005, "preco": 2000, "estoque": 10, "areas": ["m10_04_00_00"]},
        {"tipo": "chao", "area": "m10_16_00_00", "lote": 1000, "pos": [30.0, 0.0, 2.0], "no": "bau", "qtd": 2, "estado_ref": "lote:1000"},
        {"tipo": "drop", "area": "m10_18_00_00", "inimigo": "Royal Swordsman", "tipo_inimigo": TIPO, "quantos": 2},
        {"tipo": "compra", "npc": "Steady Hand McDuff", "linha": 76430000, "preco": 2500, "estoque": None, "areas": ["m10_16_00_00"]},
        {"tipo": "chao", "area": "m10_19_00_00", "lote": 2000, "pos": [0.0, 0.0, 0.0], "no": None, "qtd": 1, "estado_ref": "lote:2000"},
        {"tipo": "chao", "area": "m50_35_00_00", "lote": 3000, "pos": [0.0, 0.0, 0.0], "no": None, "qtd": 1, "estado_ref": "lote:3000"}]},
    str(ARMA): {"id": ARMA, "nome": "Uchigatana", "cat": "arma", "req": {"STR": 10, "DEX": 16}, "fontes": [
        {"tipo": "troca", "npc": "Straid of Olaphis", "linha": 76801000, "preco": 1000, "alma_id": ALMA, "alma": "Flexile Sentry Soul",
         "chefe": {"flag": 100961, "nome": "Flexile Sentry", "area": "m10_18_00_00"}, "areas": ["m10_16_00_00"]}]},
    str(ALMA): {"id": ALMA, "nome": "Flexile Sentry Soul", "cat": "consumivel", "req": {}, "fontes": [
        {"tipo": "recompensa", "chefe": "Flexile Sentry", "flag": 100961, "area": "m10_18_00_00"}]},
}}
PERS = {"nivel": 30, "almas": 1500, "stats": {"VGR": 10, "END": 10, "VIT": 10, "ATN": 10, "STR": 10, "DEX": 10, "INT": 10,
                                               "FTH": 10, "ADP": 10},
        "equipado": [], "itens": [], "chefes": [], "fogueiras": [14650, 10670, 18650, 16650]}


def calcular(item_id, pers=PERS, estado=None):
    return ds2fontes.fontes(INDICE["itens"][str(item_id)], INDICE, pers, carregar_area=lambda a: (MAPAS[a], None),
                            estado_area=(lambda a: estado.get(a)) if estado else None)


def test_area_access_from_lit_bonfires_and_route_order():
    acesso = ds2fontes.acesso_areas(AREAS, {10670, 18650})
    assert acesso["m10_04_00_00"] == "agora"  # hub (rota.json)
    assert acesso["m10_10_00_00"] == "agora" and acesso["m10_18_00_00"] == "agora"
    assert acesso["m10_16_00_00"] == "em_breve"  # a próxima depois da mais avançada liberada
    assert acesso["m10_19_00_00"] == "tarde" and acesso["m50_35_00_00"] == "tarde"


def test_sources_are_ordered_now_soon_late_and_by_walk_from_the_bonfire():
    res = calcular(ITEM, pers={**PERS, "fogueiras": [14650, 18650]})
    ordem = [(f["tipo"], f["acesso"], f.get("npc") or f.get("area")) for f in res["fontes"]]
    assert ordem == [("drop", "agora", "m10_18_00_00"), ("compra", "agora", "Stone Trader Chloanne"),
                     ("compra", "em_breve", "Steady Hand McDuff"), ("chao", "em_breve", "m10_16_00_00"),
                     ("chao", "tarde", "m10_19_00_00"), ("chao", "tarde", "m50_35_00_00")]
    drop, loja = res["fontes"][:2]
    assert drop["rota"]["metros"] == pytest.approx(11.0) and drop["rota"]["de"] == {"id": 18650, "nome": "Fogueira 18650"}
    assert loja["rota"]["metros"] == pytest.approx(29.0)


def test_earliest_and_most_profitable_are_marked_once():
    res = calcular(ITEM)
    marcas = [(f["tipo"], f.get("npc"), f["destaques"]) for f in res["fontes"] if f["destaques"]]
    assert marcas == [("drop", None, ["mais_cedo"]), ("compra", "Steady Hand McDuff", ["mais_rentavel"])]


def test_route_lists_doors_with_key_and_the_save_state():
    fechada = next(f for f in calcular(ITEM)["fontes"] if f["tipo"] == "chao" and f["area"] == "m10_16_00_00")
    assert [(p["nome"], p["chave"], p["aberta"], p["tem_chave"]) for p in fechada["rota"]["portas"]] == \
        [("Iron Door", "Antiquated Key", None, False)]
    assert {"tipo": "chave", "item": "Antiquated Key", "porta": "Iron Door"} in fechada["faltam"]
    aberta = next(f for f in calcular(ITEM, estado={"m10_16_00_00": {"objetos": {"o00_0316_0002": True}, "lotes": {}}})["fontes"]
                  if f["tipo"] == "chao" and f["area"] == "m10_16_00_00")
    assert aberta["rota"]["portas"][0]["aberta"] is True and not any(x["tipo"] == "chave" for x in aberta["faltam"])
    com_chave = {**PERS, "itens": [{"nome": "Antiquated Key", "qtd": 1}]}
    tem = next(f for f in calcular(ITEM, pers=com_chave)["fontes"] if f["tipo"] == "chao" and f["area"] == "m10_16_00_00")
    assert tem["rota"]["portas"][0]["tem_chave"] is True and not any(x["tipo"] == "chave" for x in tem["faltam"])


def test_route_carries_the_map_drawing_for_the_page():
    fonte = next(f for f in calcular(ITEM)["fontes"] if f["tipo"] == "chao" and f["area"] == "m10_16_00_00")
    mapa = fonte["mapa"]
    assert mapa["area"] == "m10_16_00_00" and mapa["nome"] == "The Lost Bastille" and mapa["metros"] == pytest.approx(29.0)
    assert [(p["n"], p["tipo"], p["ref"]) for p in mapa["pontos"]] == [(1, "fogueira", 16650), (2, "item", 1000)]
    assert mapa["trechos"][0][0] == [1.0, 0.0, 2.0] and mapa["portas"][0]["chave"]["nome"] == "Antiquated Key"


def test_ground_item_already_picked_goes_last_and_is_not_the_earliest():
    res = calcular(ITEM, estado={"m10_16_00_00": {"objetos": {}, "lotes": {"1000": True}}})
    pego = next(f for f in res["fontes"] if f.get("lote") == 1000)
    assert pego["feito"] and res["fontes"][-1] is pego and "mais_cedo" not in pego["destaques"]


def test_missing_souls_for_a_purchase():
    loja = next(f for f in calcular(ITEM)["fontes"] if f.get("npc") == "Steady Hand McDuff")
    assert {"tipo": "almas", "valor": 1000} in loja["faltam"]
    assert loja["rendimento"] == "ilimitado · 2.500 almas cada"


def test_shop_shows_the_wiki_for_event_conditions():
    loja = next(f for f in calcular(ITEM)["fontes"] if f.get("npc") == "Stone Trader Chloanne")
    assert "ver na wiki" in loja["condicao"]
    assert loja["wiki"] == "https://darksouls2.wiki.fextralife.com/Stone+Trader+Chloanne"


def test_trade_needs_the_boss_soul():
    troca = calcular(ARMA)["fontes"][0]
    assert {"tipo": "alma", "item": "Flexile Sentry Soul", "chefe": "Flexile Sentry", "derrotado": False} in troca["faltam"]
    com_alma = {**PERS, "itens": [{"nome": "Flexile Sentry Soul", "qtd": 1}], "chefes": ["Flexile Sentry"]}
    assert not any(x["tipo"] == "alma" for x in calcular(ARMA, pers=com_alma)["fontes"][0]["faltam"])


def test_boss_reward_already_taken_when_the_boss_is_dead():
    res = calcular(ALMA, pers={**PERS, "chefes": ["Flexile Sentry"]})
    assert res["fontes"][0]["feito"] and res["fontes"][0]["rota"]["metros"] == pytest.approx(19.0)


def test_requirement_gap_in_levels_and_souls():
    res = calcular(ARMA)
    custo = ds2save.level_costs()
    assert res["requisito"] == {"faltam": {"DEX": 6}, "niveis": 6, "almas": sum(custo[n] for n in range(31, 37))}
    assert calcular(ARMA, pers={**PERS, "stats": {**PERS["stats"], "DEX": 16}})["requisito"] is None


def test_steps_buy_then_level_then_equip():
    res = calcular(ITEM)
    assert [(s["tipo"], s["id"]) for s in ds2fontes.passos(res, PERS)] == [("farm", f"quero-{ITEM}-farm")]
    arma = calcular(ARMA)
    passos = ds2fontes.passos(arma, PERS)
    assert [s["tipo"] for s in passos] == ["troca", "nivel"]
    assert passos[1]["fluxo"][0] == {"tipo": "atributo", "nome": "DEX", "sub": "10 → 16"}
    tem = {**PERS, "itens": [{"nome": "Uchigatana", "qtd": 1}], "stats": {**PERS["stats"], "DEX": 16}}
    equipar = ds2fontes.passos(calcular(ARMA, pers=tem), tem)
    assert [s["tipo"] for s in equipar] == ["equipar"] and equipar[0]["fluxo"][0]["sub"] == "entra"
    assert ds2fontes.passos(calcular(ARMA, pers={**tem, "equipado": ["Uchigatana"]}), {**tem, "equipado": ["Uchigatana"]}) == []
    assert all(len(s["titulo"]) <= 40 for s in passos + equipar)


def test_page_entry_uses_the_plan_format():
    entrada = ds2fontes.pagina(calcular(ITEM))
    assert entrada["id"] == f"quero-{ITEM}" and entrada["item"]["nome"] == "Magic Stone" and entrada["item"]["tipo"] == "item"
    tipos = [f["tipo"] for f in entrada["fontes"]]
    assert tipos[0] == "drop" and "chao" in tipos
    drop = entrada["fontes"][0]
    assert drop["acesso"] == "agora" and drop["destaques"] == ["mais_cedo"] and drop["mapa"]["area"] == "m10_18_00_00"
    assert drop["fluxo"][0]["tipo"] == "local" and drop["fluxo"][0]["ponto"] == {"area": "m10_18_00_00", "tipo": "fogueira", "ref": 18650}
    assert drop["fluxo"][1]["tipo"] == "inimigo" and drop["fluxo"][1]["nome"] == "Royal Swordsman"
    assert drop["fluxo"][1]["ponto"] == {"area": "m10_18_00_00", "tipo": "inimigo", "ref": 7}
    assert all(len(f["requisito"]) <= 80 for f in entrada["fontes"] if isinstance(f.get("requisito"), str))


def test_cli_without_game_reports_error(monkeypatch, capsys):
    monkeypatch.setattr(ds2arquivos, "game_dir_padrao", lambda: None)
    assert ds2fontes.main(["fontes", "--item", "Magic Stone"]) == 1
    assert "error" in json.loads(capsys.readouterr().out)


def test_real_sources_for_the_save(capsys):
    if ds2arquivos.game_dir_padrao() is None:
        pytest.skip("DS2 SotFS não instalado")
    try:
        save = ds2save.find_save()
        personagem = ds2save.personagens(save)[0]["slug"]
    except (ds2save.SaveError, OSError, IndexError):
        pytest.skip("sem save do DS2")
    assert ds2fontes.main(["fontes", "--item", "Magic Stone", "--personagem", personagem]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["item"]["nome"] == "Magic Stone" and out["fontes"]
    assert [f["acesso"] for f in out["fontes"] if not f["feito"]] == sorted(
        (f["acesso"] for f in out["fontes"] if not f["feito"]), key=["agora", "em_breve", "tarde"].index)


def test_plan_entries_from_code_pass_the_plan_validator():
    import validate_plano
    from test_prepare_page import example

    plano = example()
    for item_id in (ITEM, ARMA, ALMA):
        out = ds2fontes.para_plano(calcular(item_id), PERS)
        plano["itens"].append(out["item"])
        plano["passos"] += out["passos"]
    assert validate_plano.validate(plano) == []
    # o mapa sai: o prepare_page refaz a rota pelos pontos dos nós (e o plano gasta menos)
    assert not any("mapa" in f for it in plano["itens"] for f in it["fontes"]) and not any("mapa" in s for s in plano["passos"])
    assert any(n.get("ponto") for it in plano["itens"][-3:] for f in it["fontes"] for n in f["fluxo"])
