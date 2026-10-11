import json

import pytest

import ds2arquivos
import ds2combate
import ds2save

UCHI, FALCHION, CLAYMORE, STAFF, LIZARD, ARROW, SHARD = 1700000, 1360000, 2000000, 3800000, 3830000, 31010000, 60970000
NAMES = {UCHI: ("MeleeWeapons", "Uchigatana"), FALCHION: ("MeleeWeapons", "Falchion"), CLAYMORE: ("MeleeWeapons", "Claymore"),
         STAFF: ("SpellTools", "Sorcerer's Staff"), LIZARD: ("SpellTools", "Lizard Staff"), ARROW: ("Spells", "Soul Arrow"),
         SHARD: ("UpgradeMaterials", "Titanite Shard")}
BASE = {UCHI: 150, FALCHION: 210, CLAYMORE: 300}
MAGIA = {STAFF: 100, LIZARD: 140}


class FakeCalc:
    weapons = {i: {"reinforce_id": 1, "req_str": r[0], "req_dex": r[1], "req_int": r[2], "req_fth": 0}
               for i, r in {UCHI: (10, 16, 0), FALCHION: (9, 13, 0), CLAYMORE: (16, 10, 0), STAFF: (0, 0, 10), LIZARD: (0, 0, 13)}.items()}
    reinforce = {1: {"nivel_max": 10}}
    spells = {ARROW: {}}

    def physical_ar(self, item_id, nivel, stats):
        return BASE[item_id] + 10 * nivel if item_id in BASE else 0

    def physical_parts(self, item_id, nivel, stats):
        return {"base": self.physical_ar(item_id, nivel, stats)}

    def catalyst_ar(self, item_id, nivel, stats):
        return {"magico": MAGIA[item_id] + nivel} if item_id in MAGIA else {}

    def catalyst_parts(self, item_id, nivel, stats):
        return {k: {"base": v} for k, v in self.catalyst_ar(item_id, nivel, stats).items()}

    def attunement(self, atn):
        return {"slots": 3, "faixa": 2}

    def spell(self, spell_id, catalyst, stats):
        return {"id": spell_id, "elemento": "magico", "mult": 1.0, "ar": catalyst["magico"] if "magico" in catalyst else None,
                "slots": 1, "usos": 10, "req_int": 10, "req_fth": 0, "requisito_ok": True}


class FakeData:
    def upgrade_cost(self, item_id, de, ate):
        return {"almas_total": 100 * (ate - de), "materiais": {SHARD: ate - de}, "niveis": []}


SNAP = {"name": "Teste", "level": 30, "souls": 500, "stats": {"VGR": 10, "END": 10, "VIT": 10, "ATN": 10, "STR": 10, "DEX": 18,
                                                             "INT": 14, "FTH": 6, "ADP": 10},
        "equipped": {"hands": {"R1": {"id": UCHI, "name": "Uchigatana"}, "L1": {"id": STAFF, "name": "Sorcerer's Staff"}},
                     "armor": {}, "rings": [], "spells": [{"id": ARROW, "name": "Soul Arrow"}]},
        "inventory": [{"id": UCHI, "name": "Uchigatana", "category": "MeleeWeapons", "quantity": 1, "upgrade": 5},
                      {"id": STAFF, "name": "Sorcerer's Staff", "category": "SpellTools", "quantity": 1, "upgrade": 0},
                      {"id": ARROW, "name": "Soul Arrow", "category": "Spells", "quantity": 1, "upgrade": None},
                      {"id": SHARD, "name": "Titanite Shard", "category": "UpgradeMaterials", "quantity": 1, "upgrade": None}],
        "progresso": {"fogueiras": [16650], "compras": [{"linha": 76430000, "loja": "Steady Hand McDuff", "item_id": UCHI,
                                                        "item": "Uchigatana", "qtd": 1}]}}
BASTILHA = "m10_16_00_00"
INDICE = {"areas": {BASTILHA: {"nome": "The Lost Bastille", "fogueiras": [16650], "ordem": 5},
                    "m10_19_00_00": {"nome": "Iron Keep", "fogueiras": [19655], "ordem": 19}},
          "itens": {str(FALCHION): {"id": FALCHION, "nome": "Falchion", "cat": "arma", "fontes": [{"tipo": "chao", "area": BASTILHA}]},
                    str(CLAYMORE): {"id": CLAYMORE, "nome": "Claymore", "cat": "arma",
                                    "fontes": [{"tipo": "compra", "areas": [BASTILHA], "preco": 1000}]},
                    str(LIZARD): {"id": LIZARD, "nome": "Lizard Staff", "cat": "catalisador",
                                  "fontes": [{"tipo": "chao", "area": BASTILHA}],
                                  "icone": "https://static0.fextralifeimages.com/file/darksouls2/x/Lizard_Staff.png"},
                    str(UCHI): {"id": UCHI, "nome": "Uchigatana", "cat": "arma", "fontes": []}}}


def calcular(**kw):
    return ds2combate.combate(FakeCalc(), FakeData(), NAMES, SNAP, indice=INDICE, **kw)


def slot(eq, nome):
    return next(s for s in eq["slots"] if s["slot"] == nome)


def test_best_weapon_and_catalyst_you_can_get_now_with_your_stats():
    eq = calcular()["equipamento"]
    r1, l1 = slot(eq, "R1"), slot(eq, "L1")
    assert r1["agora"]["nome"] == "Uchigatana" and r1["agora"]["ar"] == 200
    assert r1["plano"]["nome"] == "Falchion" and r1["plano"]["ar"] == 210 and r1["muda"]  # o Claymore pede STR 16
    assert l1["plano"]["nome"] == "Lizard Staff" and l1["plano"]["ar"] == {"magico": 140}
    assert eq["origem"] == "melhor que dá para pegar agora"
    assert l1["plano"]["icone"].endswith("Lizard_Staff.png")  # o ícone do índice, para a página


def test_nothing_better_keeps_the_slot():
    indice = {**INDICE, "itens": {k: v for k, v in INDICE["itens"].items() if k != str(FALCHION)}}
    eq = ds2combate.combate(FakeCalc(), FakeData(), NAMES, SNAP, indice=indice)["equipamento"]
    assert slot(eq, "R1")["plano"]["nome"] == "Uchigatana" and not slot(eq, "R1")["muda"]


def test_the_plan_swaps_win_over_the_code():
    plano = {"equipamento": {"slots": [{"slot": "R1", "agora": {"nome": "Uchigatana"}, "plano": {"nome": "Claymore", "nivel": 3},
                                        "muda": True}]}}
    eq = calcular(plano=plano)["equipamento"]
    assert slot(eq, "R1")["plano"]["nome"] == "Claymore" and slot(eq, "R1")["plano"]["nivel"] == 3
    assert slot(eq, "L1")["plano"]["nome"] == "Lizard Staff" and eq["origem"] == "plano"


def test_spells_come_from_the_save_with_the_best_catalyst():
    f = calcular()["feiticos"]
    assert f["catalisador"]["nome"] == "Sorcerer's Staff" and f["ar"] == {"magico": 100} and f["slots"]["total"] == 3
    (arrow,) = f["lista"]
    assert arrow["id"] == "soul-arrow" and arrow["estado"] == "equipado" and arrow["ar"] == 100 and arrow["elemento"] == "mágico"
    assert arrow["no"]["sub"] == "Lizard Staff: 140" and arrow["requisito"] == "INT 10" and arrow["requisito_ok"]


def test_suggested_spells_of_the_plan_stay_after_the_save_ones():
    plano = {"feiticos": {"lista": [{"id": "soul-arrow", "estado": "sugerido", "no": {"nome": "Soul Arrow"}},
                                    {"id": "soul-spear", "estado": "sugerido", "no": {"tipo": "item", "nome": "Soul Spear"}}]}}
    lista = calcular(plano=plano)["feiticos"]["lista"]
    assert [(s["id"], s["estado"]) for s in lista] == [("soul-arrow", "equipado"), ("soul-spear", "sugerido")]


def test_damage_rows_next_and_max_upgrade_with_materials_and_the_swap():
    dano = calcular()["dano"]
    uchi = [d for d in dano if d["arma"]["nome"] == "Uchigatana"]
    assert [(d["detalhe"], d["agora"], d["depois"]) for d in uchi] == [("reforço +5 → +6", 200, 210), ("reforço +5 → +10", 200, 250)]
    assert uchi[0]["por_causa"][0] == {"tipo": "item", "nome": "Titanite Shard", "sub": "×1 · tem 1", "tem": True,
                                       "link": "https://darksouls2.wiki.fextralife.com/Titanite+Shard"}
    assert uchi[1]["por_causa"][0]["sub"] == "×5 · tem 1" and "tem" not in uchi[1]["por_causa"][0]
    assert uchi[1]["por_causa"][-1] == {"tipo": "almas", "nome": "500 almas", "sub": "tem 500"}
    troca = next(d for d in dano if d["arma"]["nome"] == "Falchion")
    assert (troca["detalhe"], troca["agora"], troca["depois"]) == ("troca: Uchigatana +5 → Falchion +0", 200, 210)


def test_purchases_from_the_save_for_progress():
    assert calcular()["compras"] == [{"loja": {"tipo": "npc", "nome": "Steady Hand McDuff",
                                               "link": "https://darksouls2.wiki.fextralife.com/Steady+Hand+McDuff"},
                                      "item": {"tipo": "item", "nome": "Uchigatana",
                                               "link": "https://darksouls2.wiki.fextralife.com/Uchigatana"}, "qtd": 1}]


def test_without_index_the_future_is_only_what_you_have():
    eq = ds2combate.combate(FakeCalc(), FakeData(), NAMES, SNAP)["equipamento"]
    assert slot(eq, "R1")["plano"]["nome"] == "Uchigatana" and eq["origem"] == "o que você tem"


def test_real_combat_for_the_save():
    game = ds2arquivos.game_dir_padrao()
    if game is None:
        pytest.skip("DS2 SotFS não instalado")
    try:
        save = ds2save.find_save()
        slot_n = ds2save.personagens(save)[0]["slot"]
    except (ds2save.SaveError, OSError, IndexError):
        pytest.skip("sem save do DS2")
    import ds2calc
    import ds2data
    snap = ds2save.snapshot(save, slot_n)
    out = ds2combate.combate(ds2calc.load(), ds2data.load(), ds2save.load_item_names(), snap)
    assert out["equipamento"]["slots"] and isinstance(out["dano"], list) and isinstance(out["feiticos"]["lista"], list)
    json.dumps(out)  # vai para a página como JSON


def test_tool_in_the_right_hand_without_damage_has_no_damage_rows():
    binoculos = 5800000
    names = {**NAMES, binoculos: ("MeleeWeapons", "Binoculars")}
    calc = FakeCalc()
    calc.weapons = {**FakeCalc.weapons, binoculos: {"reinforce_id": 1, "req_str": 0, "req_dex": 0, "req_int": 0, "req_fth": 0}}
    snap = {**SNAP, "equipped": {**SNAP["equipped"], "hands": {**SNAP["equipped"]["hands"], "R2": {"id": binoculos, "name": "Binoculars"}}},
            "inventory": SNAP["inventory"] + [{"id": binoculos, "name": "Binoculars", "category": "MeleeWeapons", "quantity": 1, "upgrade": 0}]}
    dano = ds2combate.combate(calc, FakeData(), names, snap, indice=INDICE)["dano"]
    assert not any(d["arma"]["nome"] == "Binoculars" for d in dano)


def test_catalysts_are_compared_only_with_the_same_kind():
    """Chama não vira cajado: o elemento principal do catalisador (tabela do jogo) separa cajado, sino e chama."""
    chama, chama_boa = 5400000, 5410000
    names = {**NAMES, chama: ("MeleeWeapons", "Pyromancy Flame"), chama_boa: ("MeleeWeapons", "Ascended Pyromancy Flame")}
    calc = FakeCalc()
    calc.weapons = {**FakeCalc.weapons, chama: FakeCalc.weapons[STAFF], chama_boa: FakeCalc.weapons[STAFF]}
    fogo = {chama: 150, chama_boa: 190}
    calc.catalyst_ar = lambda i, n, s: {"fogo": fogo[i] + n} if i in fogo else FakeCalc.catalyst_ar(calc, i, n, s)
    snap = {**SNAP, "equipped": {**SNAP["equipped"], "hands": {**SNAP["equipped"]["hands"], "L3": {"id": chama, "name": "Pyromancy Flame"}}},
            "inventory": SNAP["inventory"] + [{"id": chama, "name": "Pyromancy Flame", "category": "MeleeWeapons", "quantity": 1, "upgrade": 0}]}
    so_cajado = ds2combate.combate(calc, FakeData(), names, snap, indice=INDICE)["equipamento"]
    assert slot(so_cajado, "L3")["plano"]["nome"] == "Pyromancy Flame" and not slot(so_cajado, "L3")["muda"]
    assert slot(so_cajado, "L1")["plano"]["nome"] == "Lizard Staff"
    indice = {**INDICE, "itens": {**INDICE["itens"], str(chama_boa): {"id": chama_boa, "nome": "Ascended Pyromancy Flame",
                                                                      "cat": "catalisador", "fontes": [{"tipo": "chao", "area": BASTILHA}]}}}
    com_chama = ds2combate.combate(calc, FakeData(), names, snap, indice=indice)["equipamento"]
    assert slot(com_chama, "L3")["plano"]["nome"] == "Ascended Pyromancy Flame" and slot(com_chama, "L1")["plano"]["nome"] == "Lizard Staff"
