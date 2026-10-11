import json
import struct

import pytest

import ds2arquivos
import ds2itens
from test_ds2data import ITEM, SOUL, WEAPON, synthetic
from test_ds2regulation import build_param

TIPO_SOLDADO = 300100
BASTILLE = {
    "area": "m10_16_00_00", "nome": "The Lost Bastille",
    "fogueiras": [{"id": 16650, "nome": "Straid's Cell", "pos": [0.0, 0.0, 0.0]}],
    "itens": [{"lote": 1000, "pos": [5.0, 0.0, 5.0], "itens": [{"id": ITEM, "nome": "Magic Stone", "qtd": 2}],
               "no": "bau", "chave": False, "estado_ref": "lote:1000"}],
    "npcs": [{"id": 7643, "nome": "Steady Hand McDuff", "pos": [10.0, 0.0, 0.0]},
             {"id": 7680, "nome": "Straid of Olaphis", "pos": [-3.0, 0.0, 0.0]}],
    "chefes": [],
    "inimigos": [{"id": 1, "tipo": TIPO_SOLDADO, "papel": None, "pos": [20.0, 0.0, 0.0]},
                 {"id": 2, "tipo": TIPO_SOLDADO, "papel": None, "pos": [22.0, 0.0, 0.0]},
                 {"id": 3, "tipo": 999900, "papel": "npc", "pos": [0.0, 0.0, 9.0]}],
}
MAJULA = {"area": "m10_04_00_00", "nome": "Majula", "fogueiras": [{"id": 14650, "nome": "Majula", "pos": [1.0, 2.0, 3.0]}],
          "itens": [], "npcs": [{"id": 7620, "nome": "Stone Trader Chloanne", "pos": [0.0, 0.0, 0.0]}], "chefes": [], "inimigos": []}
WHARF = {"area": "m10_18_00_00", "nome": "No-man's Wharf", "fogueiras": [], "itens": [], "npcs": [], "inimigos": [],
         "chefes": [{"flag": 100961, "nome": "Flexile Sentry", "pos": [0.0, 0.0, 0.0]}]}
CHEFES = [{"flag": 100961, "nome": "Flexile Sentry", "area": "No-Man's Wharf", "mapa": "m10_18_00_00",
           "wiki": "https://darksouls2.wiki.fextralife.com/Flexile+Sentry", "itens": [SOUL]}]


def nome_inimigo(tipo):
    return {"nome": "Royal Swordsman", "base": "Royal Swordsman"} if tipo == TIPO_SOLDADO else None


def indice(names, **kw):
    return ds2itens.montar(names, synthetic(), [BASTILLE, MAJULA, WHARF], {TIPO_SOLDADO: [WEAPON]}, CHEFES,
                           nome_inimigo=nome_inimigo, **kw)


def test_category_comes_from_the_id_list_and_spell_prefix():
    assert ds2itens.categoria("Spells", 31090000, "Soul Spear") == "feitico"
    assert ds2itens.categoria("Spells", 32010000, "Heal") == "milagre"
    assert ds2itens.categoria("Spells", 33010000, "Fireball") == "piromancia"
    assert ds2itens.categoria("Spells", 34010000, "Dark Orb") == "hex"
    assert ds2itens.categoria("Spells", 35030000, "Resonant Soul") == "hex"
    assert ds2itens.categoria("MeleeWeapons", 5400000, "Pyromancy Flame") == "catalisador"
    assert ds2itens.categoria("SpellTools", 3800000, "Sorcerer's Staff") == "catalisador"
    assert ds2itens.categoria("MeleeWeapons", 1700000, "Uchigatana") == "arma"
    assert ds2itens.categoria("Rings", 40010000, "Life Ring") == "anel"
    assert ds2itens.categoria("UpgradeMaterials", 60975000, "Large Titanite Shard") == "material"


def test_shop_source_has_npc_price_stock_and_the_npc_areas(names):
    fontes = indice(names)["itens"][str(ITEM)]["fontes"]
    lojas = {f["npc"]: f for f in fontes if f["tipo"] == "compra"}
    assert lojas["Steady Hand McDuff"]["estoque"] is None and lojas["Steady Hand McDuff"]["preco"] == 2500
    assert lojas["Steady Hand McDuff"]["areas"] == ["m10_16_00_00"]
    assert lojas["Stone Trader Chloanne"]["estoque"] == 10 and lojas["Stone Trader Chloanne"]["areas"] == ["m10_04_00_00"]


def test_ground_source_has_area_lot_and_chest(names):
    chao = [f for f in indice(names)["itens"][str(ITEM)]["fontes"] if f["tipo"] == "chao"]
    assert chao == [{"tipo": "chao", "area": "m10_16_00_00", "lote": 1000, "pos": [5.0, 0.0, 5.0], "no": "bau", "qtd": 2,
                     "estado_ref": "lote:1000"}]


def test_trade_source_names_the_soul_and_its_boss(names):
    troca = next(f for f in indice(names)["itens"][str(WEAPON)]["fontes"] if f["tipo"] == "troca")
    assert troca["npc"] == "Straid of Olaphis" and troca["areas"] == ["m10_16_00_00"]
    assert troca["alma_id"] == SOUL and troca["alma"] == "Flexile Sentry Soul"
    assert troca["chefe"] == {"flag": 100961, "nome": "Flexile Sentry", "area": "m10_18_00_00"}


def test_enemy_drop_source_counts_the_enemies_of_that_type(names):
    drop = next(f for f in indice(names)["itens"][str(WEAPON)]["fontes"] if f["tipo"] == "drop")
    assert drop == {"tipo": "drop", "area": "m10_16_00_00", "inimigo": "Royal Swordsman", "tipo_inimigo": TIPO_SOLDADO,
                    "quantos": 2}


def test_boss_reward_source(names):
    rec = [f for f in indice(names)["itens"][str(SOUL)]["fontes"] if f["tipo"] == "recompensa"]
    assert rec == [{"tipo": "recompensa", "chefe": "Flexile Sentry", "flag": 100961, "area": "m10_18_00_00"}]


def test_every_listed_item_is_indexed_with_category_and_requirements(names):
    idx = indice(names, spells={31090000: {"req_int": 40, "req_fth": 0}},
                 icones={"soul spear": {"url": "https://static0.fextralifeimages.com/file/darksouls2/x/Soul_Spear.png"}})
    assert len(idx["itens"]) == len(names)
    spear = idx["itens"]["31090000"]
    assert spear["nome"] == "Soul Spear" and spear["cat"] == "feitico" and spear["req"] == {"INT": 40}
    assert spear["icone"].endswith("Soul_Spear.png") and spear["fontes"] == []
    assert idx["itens"][str(WEAPON)]["cat"] == "arma" and idx["itens"][str(WEAPON)]["req"] == {}


def test_areas_keep_name_bonfires_and_route_order(names):
    areas = indice(names)["areas"]
    assert areas["m10_16_00_00"]["nome"] == "The Lost Bastille" and areas["m10_16_00_00"]["fogueiras"] == [16650]
    assert areas["m10_16_00_00"]["ordem"] == 5 and areas["m10_04_00_00"]["ordem"] == -1


def test_boss_rewards_come_from_boss_battle_param_lot():
    linha = bytearray(68)
    struct.pack_into("<i", linha, 8, 303300)
    struct.pack_into("<i", linha, 20, 100961)
    out = ds2itens.recompensas_chefes(build_param({1018000: bytes(linha)}), {303300: [(SOUL, 1)]})
    assert out == {100961: {"mapa": "m10_18_00_00", "lote": 303300, "itens": [SOUL]}}


def test_drops_by_enemy_type_read_both_lots_without_repeating():
    linha = bytearray(0x138)
    struct.pack_into("<i", linha, 0x4C, 7)
    struct.pack_into("<i", linha, 0x134, 8)
    out = ds2itens.drops_por_tipo(build_param({TIPO_SOLDADO: bytes(linha)}), {7: [(WEAPON, 1)], 8: [(WEAPON, 1), (ITEM, 3)]},
                                  [TIPO_SOLDADO, 123])
    assert out == {TIPO_SOLDADO: [WEAPON, ITEM]}


def test_cache_is_reused_until_the_game_changes(tmp_path, monkeypatch):
    feitos = []

    def montar_jogo(game_dir, cache_dir):
        feitos.append(1)
        return {"itens": {"1": {"id": 1}}, "areas": {}}

    assinatura = {"v": "a"}
    monkeypatch.setattr(ds2itens, "assinatura_jogo", lambda game_dir: assinatura["v"])
    primeiro = ds2itens.carregar(tmp_path / "game", tmp_path / "cache", montar_jogo=montar_jogo)
    segundo = ds2itens.carregar(tmp_path / "game", tmp_path / "cache", montar_jogo=montar_jogo)
    assert len(feitos) == 1 and primeiro == segundo
    gravado = json.loads((tmp_path / "cache" / "itens.json").read_text(encoding="utf-8"))
    assert gravado["versao"] == ds2itens.INDICE_VERSAO and gravado["assinatura"] == "a"
    assert not list((tmp_path / "cache").glob("*.tmp"))
    assinatura["v"] = "b"
    ds2itens.carregar(tmp_path / "game", tmp_path / "cache", montar_jogo=montar_jogo)
    assert len(feitos) == 2


def test_cache_with_another_version_is_rebuilt(tmp_path, monkeypatch):
    monkeypatch.setattr(ds2itens, "assinatura_jogo", lambda game_dir: "a")
    (tmp_path / "itens.json").write_text(json.dumps({"versao": -1, "assinatura": "a", "itens": {}}), encoding="utf-8")
    out = ds2itens.carregar(tmp_path, tmp_path, montar_jogo=lambda g, c: {"itens": {"9": {}}, "areas": {}})
    assert out["itens"] == {"9": {}}


def _jogo():
    game = ds2arquivos.game_dir_padrao()
    if game is None:
        pytest.skip("DS2 SotFS não instalado")
    return game


def test_real_index_links_souls_to_bosses_and_shops_to_npcs(tmp_path):
    import ds2mapa

    idx = ds2itens.carregar(_jogo(), ds2mapa._cache_padrao(), destino=tmp_path / "itens.json")
    por_nome = {i["nome"]: i for i in idx["itens"].values()}
    alma = por_nome["Soul of the Pursuer"]["fontes"]
    assert {"tipo": "recompensa", "chefe": "The Pursuer", "flag": 100968, "area": "m10_10_00_00"} in alma
    trocas = [f for i in idx["itens"].values() for f in i["fontes"] if f["tipo"] == "troca"]
    assert trocas and all(f["npc"] in ("Straid of Olaphis", "Weaponsmith Ornifex") for f in trocas)
    assert any(f["chefe"] and f["chefe"]["nome"] == "The Pursuer" for f in trocas)
    lojas = [f for i in idx["itens"].values() for f in i["fontes"] if f["tipo"] == "compra"]
    mcduff = [f for f in lojas if f["npc"] == "Steady Hand McDuff"]
    assert mcduff and all(f["areas"] == ["m10_16_00_00"] for f in mcduff)
