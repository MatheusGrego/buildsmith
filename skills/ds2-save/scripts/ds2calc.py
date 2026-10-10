#!/usr/bin/env python3
"""Dano de arma no DS2 SotFS calculado com as tabelas de regras do próprio jogo.

AR físico (validado contra o menu do jogo: Uchigatana +5 = 218, Cleric's Parma = 54, punho = 49):
  base(L) = dano + (dano_max − dano) × L / nivel_max
  bônus   = escala_FOR(L) × bônus_FOR(FOR) + escala_DES(L) × bônus_DES(DES)
  AR      = floor((base + bônus) × mult_fisico / 100)
Catalisador (validado: Sorcerer's Staff +2 = 356, Pyromancy Flame = 204 com INT 26 / FÉ 6):
  bônus por elemento: mágico = linha INT, fogo = linha ⌊(INT+FÉ)/2⌋, raio = linha FÉ, sombrio = linha min(INT, FÉ)
  AR por elemento = floor((base + escala × bônus) × mult / 100); o menu mostra a soma dos elementos.
Feitiço: AR = floor(AR do catalisador no elemento × damage_mult do PlayerDamageParam). O menu não mostra esse
número, então ele é "calculado" (não conferido no jogo). damage_mult 0 (teleguiados) = sem cálculo.
"""
import argparse
import json
import math
import struct
import sys

import ds2regulation
from ds2save import SaveError, load_item_names


ELEMENTOS = {"magico": 2, "raio": 3, "fogo": 4, "sombrio": 5}  # elemento → índice de escala na WeaponStatsAffectParam
TIPO_DANO = {1: "magico", 2: "raio", 3: "fogo", 4: "sombrio"}  # PlayerDamageParam.damage_type_0


def bonus_rows(stats: dict) -> dict[str, int]:
    """Linha da PhysicalStatsPerLevelStatValuesParam usada para o bônus de cada elemento."""
    def clamp(value):
        return max(1, min(99, value))
    return {"magico": clamp(stats["INT"]), "fogo": clamp((stats["INT"] + stats["FTH"]) // 2),
            "raio": clamp(stats["FTH"]), "sombrio": clamp(min(stats["INT"], stats["FTH"]))}


class Calc:
    def __init__(self, params: dict[str, bytes]):
        rows = ds2regulation.param_rows
        layouts = ds2regulation.LAYOUTS
        self.weapons = rows(params["WeaponParam"], layouts["WeaponParam"])
        self.reinforce = rows(params["WeaponReinforceParam"], layouts["WeaponReinforceParam"])
        self.stat_bonus = rows(params["PhysicalStatsPerLevelStatValuesParam"], layouts["PhysicalStatsPerLevelStatValuesParam"])
        self.spells = rows(params["SpellParam"], layouts["SpellParam"]) if "SpellParam" in params else {}
        self.damage = rows(params["PlayerDamageParam"], layouts["PlayerDamageParam"]) if "PlayerDamageParam" in params else {}
        self._affect_raw = params["WeaponStatsAffectParam"]
        self._affect_index = {
            row_id: offset for row_id, offset, _ in
            (struct.unpack_from("<QQQ", self._affect_raw, 0x40 + 24 * i)
             for i in range(struct.unpack_from("<H", self._affect_raw, 0x0A)[0]))
        }

    def _scaling(self, affect_id: int, level: int, kind: int) -> float:
        offset = self._affect_index[affect_id] + ds2regulation.scaling_offset(level, kind)
        return struct.unpack_from("<f", self._affect_raw, offset)[0]

    def physical_ar(self, item_id: int, level: int, stats: dict) -> int:
        if item_id not in self.weapons:
            raise SaveError(f"arma {item_id} não está na WeaponParam")
        row = self.reinforce[self.weapons[item_id]["reinforce_id"]]
        if not 0 <= level <= row["nivel_max"]:
            raise SaveError(f"nível +{level} fora do limite da arma (+{row['nivel_max']})")
        base = row["dano_fisico"] + (row["dano_fisico_max"] - row["dano_fisico"]) * level / max(row["nivel_max"], 1)
        strength = self.stat_bonus[max(1, min(99, stats["STR"]))]["bonus_str"]
        dexterity = self.stat_bonus[max(1, min(99, stats["DEX"]))]["bonus_dex"]
        bonus = (self._scaling(row["stats_affect_id"], level, 0) * strength
                 + self._scaling(row["stats_affect_id"], level, 1) * dexterity)
        return math.floor((base + bonus) * row["mult_fisico"] / 100)


    def physical_parts(self, item_id: int, level: int, stats: dict) -> dict[str, int]:
        """Quanto do AR físico vem da arma e quanto vem de cada atributo (a soma pode diferir 1 do AR pelo arredondamento)."""
        row = self.reinforce[self.weapons[item_id]["reinforce_id"]]
        mult = row["mult_fisico"] / 100
        base = row["dano_fisico"] + (row["dano_fisico_max"] - row["dano_fisico"]) * level / max(row["nivel_max"], 1)
        out = {"base": math.floor(base * mult)}
        for stat, kind, key in (("STR", 0, "bonus_str"), ("DEX", 1, "bonus_dex")):
            valor = self._scaling(row["stats_affect_id"], level, kind) * self.stat_bonus[max(1, min(99, stats[stat]))][key]
            if valor:
                out[stat] = math.floor(valor * mult)
        return out

    def catalyst_parts(self, item_id: int, level: int, stats: dict) -> dict[str, dict[str, int]]:
        """Por elemento: quanto vem do catalisador e quanto vem dos atributos (INT, FÉ ou os dois)."""
        row = self.reinforce[self.weapons[item_id]["reinforce_id"]]
        lines = bonus_rows(stats)
        out = {}
        for element, kind in ELEMENTOS.items():
            mult = row[f"mult_{element}"] / 100
            if not mult:
                continue
            low, high = row[f"dano_{element}"], row[f"dano_{element}_max"]
            base = low + (high - low) * level / max(row["nivel_max"], 1)
            bonus = self._scaling(row["stats_affect_id"], level, kind) * self.stat_bonus[lines[element]][f"bonus_{element}"]
            out[element] = {"base": math.floor(base * mult), "atributos": math.floor(bonus * mult)}
        return out

    def catalyst_ar(self, item_id: int, level: int, stats: dict) -> dict[str, int]:
        """AR por elemento de um catalisador (só os elementos que ele tem)."""
        if item_id not in self.weapons:
            raise SaveError(f"catalisador {item_id} não está na WeaponParam")
        row = self.reinforce[self.weapons[item_id]["reinforce_id"]]
        if not 0 <= level <= row["nivel_max"]:
            raise SaveError(f"nível +{level} fora do limite (+{row['nivel_max']})")
        lines = bonus_rows(stats)
        out = {}
        for element, kind in ELEMENTOS.items():
            mult = row[f"mult_{element}"]
            if not mult:
                continue
            low, high = row[f"dano_{element}"], row[f"dano_{element}_max"]
            base = low + (high - low) * level / max(row["nivel_max"], 1)
            bonus = self.stat_bonus[lines[element]][f"bonus_{element}"]
            out[element] = math.floor((base + self._scaling(row["stats_affect_id"], level, kind) * bonus) * mult / 100)
        return out

    def attunement(self, atn: int) -> dict:
        row = self.stat_bonus[max(1, min(99, atn))]
        return {"slots": row["slots"], "faixa": max(1, row["faixa"])}

    def spell(self, spell_id: int, catalyst: dict[str, int], stats: dict) -> dict:
        if spell_id not in self.spells:
            raise SaveError(f"feitiço {spell_id} não está na SpellParam")
        row = self.spells[spell_id]
        dmg = self.damage.get(row["damage_id"], {"tipo": 0, "mult": 0.0})
        element = TIPO_DANO.get(dmg["tipo"])
        ar = math.floor(catalyst[element] * dmg["mult"]) if element in catalyst and dmg["mult"] > 0 else None
        faixa = self.attunement(stats["ATN"])["faixa"]
        return {"id": spell_id, "elemento": element, "mult": round(dmg["mult"], 3), "ar": ar,
                "slots": row["slots"], "usos": row[f"usos_{faixa}"], "req_int": row["req_int"], "req_fth": row["req_fth"],
                "requisito_ok": stats["INT"] >= row["req_int"] and stats["FTH"] >= row["req_fth"]}


def load(path=None) -> Calc:
    return Calc(ds2regulation.load_params(path))


# Anéis que somam atributo (wiki: Ring of Knowledge = +5 INT). Só entra aqui o que tem fonte.
ANEIS_ATRIBUTO = {"Ring of Knowledge": {"INT": 5}}
# Anéis que somam slot de sintonia (wiki: Southern Ritual Band = +1). Variantes +1/+2 sem fonte aqui ainda.
ANEIS_SLOTS = {"Southern Ritual Band": 1}


def slots_dos_aneis(nomes) -> int:
    return sum(ANEIS_SLOTS.get(n, 0) for n in nomes)
# Wiki (Dark Pyromancy Flame): o fogo cai com o personagem humano; só com Hollowing máximo (10 mortes) passa a
# Pyromancy Flame, por 3-4%. A calculadora não modela o Hollowing: o AR que ela mostra para essa chama não vale.
ESCALA_HOLLOWING = {"Dark Pyromancy Flame": "escala com Hollowing: humano fica abaixo da Pyromancy Flame (wiki)"}


def atributos_efetivos(snapshot: dict) -> tuple[dict, list[str]]:
    stats = dict(snapshot["stats"])
    fontes = []
    for ring in snapshot["equipped"].get("rings", []):
        for stat, valor in ANEIS_ATRIBUTO.get(ring["name"], {}).items():
            stats[stat] += valor
            fontes.append(f"{ring['name']} +{valor} {stat}")
    return stats, fontes


def catalisadores_do_save(calc: Calc, snapshot: dict, stats: dict) -> dict:
    """Catalisadores do inventário (cajados, sinos, chamas) no maior upgrade, com AR por elemento e se estão na mão."""
    equipados = {h["id"] for h in snapshot["equipped"].get("hands", {}).values()}
    cats = {}
    for item in snapshot["inventory"]:
        nivel = item.get("upgrade") or 0
        catalisador = item.get("category") == "SpellTools" or item["name"].endswith("Pyromancy Flame")  # escudo com magia não conjura
        if (not catalisador or item["id"] not in calc.weapons
                or (item["id"] in cats and cats[item["id"]]["nivel"] >= nivel)):
            continue
        try:
            ar = calc.catalyst_ar(item["id"], nivel, stats)
        except SaveError:
            continue
        if ar:
            cats[item["id"]] = {"id": item["id"], "nome": item["name"], "nivel": nivel, "tem": True,
                                "equipado": item["id"] in equipados, "ar": ar}
    return cats


def sintonia(calc: Calc, snapshot: dict, candidatos=()) -> dict:
    """Feitiços do save (equipados e no inventário) com o AR em cada catalisador que o jogador tem ou pode pegar.

    candidatos: [(item_id, nome, nível)] de catalisadores que ele ainda não tem. Catalisador que escala com
    Hollowing aparece com aviso e nunca é o "melhor".
    """
    stats, fontes = atributos_efetivos(snapshot)
    cats = catalisadores_do_save(calc, snapshot, stats)
    for item_id, nome, nivel in candidatos:
        if item_id not in cats:
            cats[item_id] = {"id": item_id, "nome": nome, "nivel": nivel, "tem": False, "equipado": False,
                             "ar": calc.catalyst_ar(item_id, nivel, stats)}
    for c in cats.values():
        c["menu"] = sum(c["ar"].values())
        if c["nome"] in ESCALA_HOLLOWING:
            c["aviso"] = ESCALA_HOLLOWING[c["nome"]]
    equip_spells = [s["id"] for s in snapshot["equipped"].get("spells", [])]
    nomes = {s["id"]: s["name"] for s in snapshot["equipped"].get("spells", [])}
    nomes.update({i["id"]: i["name"] for i in snapshot["inventory"] if i["id"] in calc.spells})
    feiticos = []
    for spell_id in dict.fromkeys(equip_spells + [i for i in nomes if i not in equip_spells]):
        if spell_id not in calc.spells:
            continue
        por_cat = []
        for c in cats.values():
            r = calc.spell(spell_id, c["ar"], stats)
            if r["ar"] is not None:
                por_cat.append((r["ar"], c))
        base = calc.spell(spell_id, {}, stats)
        atual = max(((ar, c) for ar, c in por_cat if c["equipado"]), default=(None, None), key=lambda x: x[0] or 0)
        validos = [(ar, c) for ar, c in por_cat if "aviso" not in c]
        melhor = max(validos, default=(None, None), key=lambda x: x[0])
        feiticos.append({
            "id": spell_id, "nome": nomes[spell_id], "equipado": equip_spells.count(spell_id), "elemento": base["elemento"],
            "slots": base["slots"], "usos": base["usos"], "req_int": base["req_int"], "req_fth": base["req_fth"],
            "requisito_ok": base["requisito_ok"], "ar_atual": atual[0],
            "catalisador_atual": atual[1]["nome"] if atual[1] else None,
            "melhor": {"ar": melhor[0], "catalisador": melhor[1]["nome"], "nivel": melhor[1]["nivel"],
                       "tem": melhor[1]["tem"]} if melhor[1] else None})
    usados = sum(f["slots"] * f["equipado"] for f in feiticos)
    return {"atributos": {k: stats[k] for k in ("INT", "FTH", "ATN")}, "aneis": fontes,
            "slots": {**calc.attunement(stats["ATN"]), "usados": usados,
                      "aneis": slots_dos_aneis(r["name"] for r in snapshot["equipped"].get("rings", []))},
            "catalisadores": sorted(cats.values(), key=lambda c: (not c["equipado"], not c["tem"], -c["menu"])),
            "feiticos": feiticos}


def _item_id(value: str) -> tuple[int, str]:
    if value.isdigit():
        return int(value), value
    for item_id, (_, name) in load_item_names().items():
        if name.lower() == value.lower():
            return item_id, name
    raise SaveError(f"arma '{value}' não encontrada nas listas de itens")


def main(argv=None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="ds2calc")
    sub = parser.add_subparsers(dest="cmd", required=True)
    ar = sub.add_parser("ar", help="AR físico de uma arma com os atributos dados")
    ar.add_argument("--arma", required=True, help="nome (como nas listas de itens) ou id")
    ar.add_argument("--nivel", type=int, default=0)
    ar.add_argument("--str", type=int, required=True)
    ar.add_argument("--dex", type=int, required=True)
    ar.add_argument("--jogo", help="pasta Game do DS2 (padrão: Steam)")
    cat = sub.add_parser("catalisador", help="AR por elemento de um catalisador (o menu mostra a soma)")
    spell = sub.add_parser("feitico", help="AR calculado, usos e slots de um feitiço com um catalisador")
    spell.add_argument("--feitico", required=True)
    spell.add_argument("--atn", type=int, required=True)
    for p in (cat, spell):
        p.add_argument("--catalisador", required=True)
        p.add_argument("--nivel", type=int, default=0)
        p.add_argument("--int", dest="int_", type=int, required=True)
        p.add_argument("--fth", type=int, required=True)
        p.add_argument("--jogo")
    sin = sub.add_parser("sintonia", help="feitiços equipados e do inventário comparados entre catalisadores (lê o snapshot)")
    sin.add_argument("--snapshot", required=True, help="saída do ds2save.py snapshot")
    sin.add_argument("--candidato", action="append", default=[], help='catalisador que ainda não tem: "Lizard Staff:0"')
    sin.add_argument("--jogo")
    args = parser.parse_args(argv)
    if args.cmd == "sintonia":
        try:
            calc = load(ds2regulation.find_regulation(args.jogo))
            with open(args.snapshot, encoding="utf-8") as fh:
                snap = json.load(fh)
            candidatos = []
            for texto in args.candidato:
                nome, _, nivel = texto.rpartition(":") if ":" in texto else (texto, "", "0")
                item_id, item_nome = _item_id(nome.strip())
                candidatos.append((item_id, item_nome, int(nivel or 0)))
            out = sintonia(calc, snap, candidatos)
        except (SaveError, OSError, ValueError) as err:
            print(json.dumps({"error": str(err)}, ensure_ascii=False))
            return 1
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0
    if args.cmd in ("catalisador", "feitico"):
        try:
            calc = load(ds2regulation.find_regulation(args.jogo))
            cat_id, cat_name = _item_id(args.catalisador)
            stats = {"INT": args.int_, "FTH": args.fth, "ATN": getattr(args, "atn", 1)}
            elements = calc.catalyst_ar(cat_id, args.nivel, stats)
            out = {"catalisador": cat_name, "nivel": args.nivel, "ar": elements, "menu": sum(elements.values())}
            if args.cmd == "feitico":
                spell_id, spell_name = _item_id(args.feitico)
                out = {"feitico": spell_name, **calc.spell(spell_id, elements, stats), "catalisador": out}
        except SaveError as err:
            print(json.dumps({"error": str(err)}, ensure_ascii=False))
            return 1
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0
    try:
        item_id, name = _item_id(args.arma)
        calc = load(ds2regulation.find_regulation(args.jogo))
        value = calc.physical_ar(item_id, args.nivel, {"STR": args.str, "DEX": args.dex})
    except SaveError as err:
        print(json.dumps({"error": str(err)}, ensure_ascii=False))
        return 1
    print(json.dumps({"arma": name, "item_id": item_id, "nivel": args.nivel, "str": args.str, "dex": args.dex,
                      "ar_fisico": value}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
