#!/usr/bin/env python3
"""Dano de arma no DS2 SotFS calculado com as tabelas de regras do próprio jogo.

AR físico (validado contra o menu do jogo: Uchigatana +5 = 218, Cleric's Parma = 54, punho = 49):
  base(L) = dano + (dano_max − dano) × L / nivel_max
  bônus   = escala_FOR(L) × bônus_FOR(FOR) + escala_DES(L) × bônus_DES(DES)
  AR      = floor((base + bônus) × mult_fisico / 100)
Catalisador (validado: Sorcerer's Staff +2 = 356, Pyromancy Flame = 204 com INT 26 / FÉ 6):
  bônus por elemento: mágico = linha INT, fogo = linha ⌊(INT+FÉ)/2⌋, raio = linha FÉ, sombrio = linha min(INT, FÉ)
  AR por elemento = floor((base + escala × bônus) × mult / 100); o menu mostra a soma dos elementos.
Infusão k (0..9): a escala sai da linha `stats_affect_id + k` da WeaponStatsAffectParam e o multiplicador de dano dos 2
floats do cabeçalho dela (1,4 elementais/veneno/sangramento, 1,15 Raw, 1,0 Enchanted, 0,5 Mundane). Elemento novo divide a
base meio a meio entre físico e elemento (Uchigatana +10 Mágica = 161/161, wiki). A máscara de infusões aceitas é a linha da
CustomAttrSpecParam apontada por WeaponReinforceParam+232 (bit k). Catalisador e elemento próprio da arma: só a escala muda.
Feitiço: AR = floor(AR do catalisador no elemento × damage_mult do PlayerDamageParam). O menu não mostra esse
número, então ele é "calculado" (não conferido no jogo). damage_mult 0 (teleguiados) = sem cálculo.
"""
import argparse
import json
import math
import struct
import sys
import unicodedata

import ds2regulation
from ds2save import SaveError, load_item_names


ELEMENTOS = {"magico": 2, "raio": 3, "fogo": 4, "sombrio": 5}  # elemento → índice de escala na WeaponStatsAffectParam
TIPO_DANO = {1: "magico", 2: "raio", 3: "fogo", 4: "sombrio"}  # PlayerDamageParam.damage_type_0
# Código da infusão (byte 1 do registro do save) -> (nome, elemento novo, pedra). Ordem pela máscara do jogo: cajado aceita
# 2 e 4 (Mágica e Sombria, wiki), sino 3 e 4 (Raio e Sombria); Magic Stone = 8 visto no save (Enchanted, wiki).
INFUSOES = {0: ("Normal", None, None), 1: ("Fogo", "fogo", "Firedrake Stone"), 2: ("Mágica", "magico", "Faintstone"),
            3: ("Raio", "raio", "Boltstone"), 4: ("Sombria", "sombrio", "Darknight Stone"), 5: ("Veneno", None, "Poison Stone"),
            6: ("Sangramento", None, "Bleed Stone"), 7: ("Raw", None, "Raw Stone"), 8: ("Enchanted", None, "Magic Stone"),
            9: ("Mundane", None, "Old Mundane Stone")}
DIVIDE = {5, 6}  # veneno e sangramento: metade da base vira o efeito (wiki: Poison +10 = 161 físico)
NAO_CONFERIDAS = {8, 9}  # Enchanted e Mundane: calculados pela tabela, ainda sem conferir no menu
REINFORCE_ESPEC = 232  # WeaponReinforceParam: id da linha da CustomAttrSpecParam (máscara das infusões)


def _piso(x: float) -> int:
    """floor tolerante ao float das tabelas (230 × 1,4 / 2 dá 160,99999...)."""
    return math.floor(x + 1e-6)


def _sem_acento(t: str) -> str:
    return unicodedata.normalize("NFKD", str(t)).encode("ascii", "ignore").decode().strip().lower()


def infusao_codigo(texto) -> int:
    """'2', 'magica', 'Mágica' ou 'magico' -> 2."""
    t = _sem_acento(texto)
    if t.isdigit() and int(t) in INFUSOES:
        return int(t)
    for k, (nome, elemento, _pedra) in INFUSOES.items():
        if t in (_sem_acento(nome), elemento):
            return k
    raise SaveError(f"infusão desconhecida: {texto}")


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
        self._mascara = {}
        if "CustomAttrSpecParam" in params:
            mascaras = rows(params["CustomAttrSpecParam"], {"mascara": ("I", 0)})
            espec = rows(params["WeaponReinforceParam"], {"espec": ("i", REINFORCE_ESPEC)})
            self._mascara = {rid: mascaras.get(v["espec"], {}).get("mascara", 0) for rid, v in espec.items()}
        self._affect_raw = params["WeaponStatsAffectParam"]
        self._affect_index = {
            row_id: offset for row_id, offset, _ in
            (struct.unpack_from("<QQQ", self._affect_raw, 0x40 + 24 * i)
             for i in range(struct.unpack_from("<H", self._affect_raw, 0x0A)[0]))
        }

    def _scaling(self, affect_id: int, level: int, kind: int) -> float:
        offset = self._affect_index[affect_id] + ds2regulation.scaling_offset(level, kind)
        return struct.unpack_from("<f", self._affect_raw, offset)[0]

    def _linha(self, item_id: int, level: int, o_que: str = "arma") -> dict:
        if item_id not in self.weapons:
            raise SaveError(f"{o_que} {item_id} não está na WeaponParam")
        row = self.reinforce[self.weapons[item_id]["reinforce_id"]]
        if not 0 <= level <= row["nivel_max"]:
            raise SaveError(f"nível +{level} fora do limite da arma (+{row['nivel_max']})")
        return row

    def infusoes(self, item_id: int) -> list[int]:
        """Códigos de infusão que a arma aceita (0 = normal sempre)."""
        if item_id not in self.weapons:
            raise SaveError(f"arma {item_id} não está na WeaponParam")
        mascara = self._mascara.get(self.weapons[item_id]["reinforce_id"], 0)
        return [0] + [k for k in range(1, 10) if mascara >> k & 1]

    def _affect(self, item_id: int, row: dict, infusao: int) -> int:
        if infusao not in INFUSOES:
            raise SaveError(f"infusão desconhecida: {infusao}")
        if infusao and infusao not in self.infusoes(item_id):
            raise SaveError(f"a arma {item_id} não aceita a infusão {INFUSOES[infusao][0]}")
        affect = row["stats_affect_id"] + infusao
        if affect not in self._affect_index:
            raise SaveError(f"sem escala para a infusão {INFUSOES[infusao][0]} da arma {item_id}")
        return affect

    def _mult(self, affect: int, level: int, row: dict) -> float:
        """Multiplicador de dano da infusão (cabeçalho da linha de escala), arredondado: as tabelas são float32."""
        a, b = struct.unpack_from("<2f", self._affect_raw, self._affect_index[affect])
        return round(a + (b - a) * level / max(row["nivel_max"], 1), 4)

    @staticmethod
    def _proprios(row: dict) -> list[str]:
        return [e for e in ELEMENTOS if row[f"mult_{e}"]]

    def _novo_elemento(self, row: dict, infusao: int) -> str | None:
        e = INFUSOES[infusao][1]
        return e if e and e not in self._proprios(row) else None

    def _base_fisica(self, row: dict, affect: int, level: int, infusao: int) -> float:
        base = row["dano_fisico"] + (row["dano_fisico_max"] - row["dano_fisico"]) * level / max(row["nivel_max"], 1)
        if infusao:
            divide = infusao in DIVIDE or self._novo_elemento(row, infusao) is not None
            base *= self._mult(affect, level, row) * (0.5 if divide else 1)
        return base

    def _bonus_fisico(self, affect: int, level: int, stats: dict, infusao: int) -> dict[str, float]:
        fontes = [("STR", 0, "bonus_str", stats["STR"]), ("DEX", 1, "bonus_dex", stats["DEX"])]
        if infusao == 8:  # Enchanted: o bônus de INT entra no físico (não conferido no menu)
            fontes.append(("INT", 2, "bonus_magico", stats["INT"]))
        return {stat: self._scaling(affect, level, kind) * self.stat_bonus[max(1, min(99, valor))][key]
                for stat, kind, key, valor in fontes}

    def physical_ar(self, item_id: int, level: int, stats: dict, infusao: int = 0) -> int:
        row = self._linha(item_id, level)
        affect = self._affect(item_id, row, infusao)
        bonus = sum(self._bonus_fisico(affect, level, stats, infusao).values())
        return _piso((self._base_fisica(row, affect, level, infusao) + bonus) * row["mult_fisico"] / 100)

    def physical_parts(self, item_id: int, level: int, stats: dict, infusao: int = 0) -> dict[str, int]:
        """Quanto do AR físico vem da arma e quanto vem de cada atributo (a soma pode diferir 1 do AR pelo arredondamento)."""
        row = self._linha(item_id, level)
        affect = self._affect(item_id, row, infusao)
        mult = row["mult_fisico"] / 100
        out = {"base": _piso(self._base_fisica(row, affect, level, infusao) * mult)}
        for stat, valor in self._bonus_fisico(affect, level, stats, infusao).items():
            if valor:
                out[stat] = _piso(valor * mult)
        return out

    def catalyst_parts(self, item_id: int, level: int, stats: dict, infusao: int = 0) -> dict[str, dict[str, int]]:
        """Por elemento próprio: quanto vem da peça e quanto vem dos atributos (INT, FÉ ou os dois)."""
        row = self._linha(item_id, level, "catalisador")
        affect = self._affect(item_id, row, infusao)
        lines = bonus_rows(stats)
        out = {}
        for element, kind in ELEMENTOS.items():
            mult = row[f"mult_{element}"] / 100
            if not mult:
                continue
            low, high = row[f"dano_{element}"], row[f"dano_{element}_max"]
            base = low + (high - low) * level / max(row["nivel_max"], 1)
            bonus = self._scaling(affect, level, kind) * self.stat_bonus[lines[element]][f"bonus_{element}"]
            out[element] = {"base": _piso(base * mult), "atributos": _piso(bonus * mult)}
        return out

    def catalyst_ar(self, item_id: int, level: int, stats: dict, infusao: int = 0) -> dict[str, int]:
        """AR por elemento próprio de um catalisador (ou da arma, como a Moonlight Greatsword)."""
        row = self._linha(item_id, level, "catalisador")
        affect = self._affect(item_id, row, infusao)
        lines = bonus_rows(stats)
        out = {}
        for element, kind in ELEMENTOS.items():
            mult = row[f"mult_{element}"]
            if not mult:
                continue
            low, high = row[f"dano_{element}"], row[f"dano_{element}_max"]
            base = low + (high - low) * level / max(row["nivel_max"], 1)
            bonus = self.stat_bonus[lines[element]][f"bonus_{element}"]
            out[element] = _piso((base + self._scaling(affect, level, kind) * bonus) * mult / 100)
        return out

    def _infundido(self, item_id: int, level: int, stats: dict, infusao: int) -> dict[str, dict[str, int]]:
        """Elemento novo que a infusão põe na arma: metade da base × multiplicador + escala da linha k."""
        row = self._linha(item_id, level)
        affect = self._affect(item_id, row, infusao)
        e = self._novo_elemento(row, infusao) if infusao else None
        if e is None:
            return {}
        low, high = row[f"dano_{e}"], row[f"dano_{e}_max"]
        base = (low + (high - low) * level / max(row["nivel_max"], 1)) * self._mult(affect, level, row) * 0.5
        bonus = self._scaling(affect, level, ELEMENTOS[e]) * self.stat_bonus[bonus_rows(stats)[e]][f"bonus_{e}"]
        return {e: {"base": _piso(base), "atributos": _piso(bonus), "ar": _piso(base + bonus)}}

    def weapon_ar(self, item_id: int, level: int, infusao: int, stats: dict) -> dict[str, int]:
        """AR por tipo de dano (só os maiores que 0) com a infusão: físico, elemento próprio e elemento da infusão."""
        out = {"fisico": self.physical_ar(item_id, level, stats, infusao)}
        for e, v in self.catalyst_ar(item_id, level, stats, infusao).items():
            out[e] = out.get(e, 0) + v
        for e, v in self._infundido(item_id, level, stats, infusao).items():
            out[e] = out.get(e, 0) + v["ar"]
        return {k: v for k, v in out.items() if v}

    def weapon_parts(self, item_id: int, level: int, infusao: int, stats: dict) -> dict[str, dict]:
        """Por tipo de dano: quanto vem da peça e quanto dos atributos, como physical_parts e catalyst_parts."""
        out = {}
        fis = self.physical_parts(item_id, level, stats, infusao)
        if fis["base"] or len(fis) > 1:
            out["fisico"] = fis
        out.update(self.catalyst_parts(item_id, level, stats, infusao))
        for e, v in self._infundido(item_id, level, stats, infusao).items():
            atual = out.get(e, {"base": 0, "atributos": 0})
            out[e] = {"base": atual["base"] + v["base"], "atributos": atual["atributos"] + v["atributos"]}
        return out

    def conferido(self, item_id: int, infusao: int) -> bool:
        """False quando o número sai só da tabela, sem conferência no menu: Enchanted, Mundane, e infusão em peça que já
        tem elemento próprio (catalisador, Heide Knight Sword)."""
        if not infusao:
            return True
        return infusao not in NAO_CONFERIDAS and not self._proprios(self._linha(item_id, 0))

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
    ar.add_argument("--int", dest="int_", type=int, default=10)
    ar.add_argument("--fth", type=int, default=10)
    ar.add_argument("--infusao", help="código (0-9) ou nome: fogo, magica, raio, sombria, veneno, sangramento, raw, enchanted, mundane")
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
        stats = {"STR": args.str, "DEX": args.dex, "INT": args.int_, "FTH": args.fth}
        k = infusao_codigo(args.infusao) if args.infusao is not None else 0
        out = {"arma": name, "item_id": item_id, "nivel": args.nivel, "str": args.str, "dex": args.dex,
               "ar_fisico": calc.physical_ar(item_id, args.nivel, stats, k)}
        if args.infusao is not None:
            out.update({"int": args.int_, "fth": args.fth, "infusao": INFUSOES[k][0],
                        "ar": calc.weapon_ar(item_id, args.nivel, k, stats), "conferido": calc.conferido(item_id, k)})
    except SaveError as err:
        print(json.dumps({"error": str(err)}, ensure_ascii=False))
        return 1
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
