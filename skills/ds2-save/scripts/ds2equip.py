#!/usr/bin/env python3
"""Bloco `equipamento` do plano: o que está equipado no save e como fica com as trocas do plano, slot por slot.

Números do jogo (ds2calc): AR físico ou por elemento, quanto vem da peça e quanto vem dos atributos, requisito,
sintonia com o AR de cada feitiço no catalisador da coluna. Anéis de atributo contam (ds2calc.ANEIS_ATRIBUTO).
Nível de upgrade e infusão do que está equipado = os da cópia de maior reforço no inventário (o save guarda só o id na
mão). Troca "R1=Old Knight Halberd:8:3" = nível 8, infusão 3 (ds2calc.INFUSOES; aceita o nome: "fogo", "magica").

  python ds2equip.py --snapshot S [--troca "L1=Lizard Staff:0"] [--troca "peito=Black Witch Robe"] [--troca "R3=-"]
                     [--sintonia "Great Soul Arrow,Great Heavy Soul Arrow,..."] [--atributo INT=35]
"""
import argparse
import json
import re
import sys

import ds2calc
from ds2save import ARMOR_ITEM_OFFSET, ARMOR_SLOTS, EMPTY_ARMOR, EMPTY_HAND, SaveError, load_item_names

SLOTS = [("direita", ["R1", "R2", "R3"]), ("esquerda", ["L1", "L2", "L3"]),
         ("armadura", list(ARMOR_SLOTS)), ("aneis", ["anel1", "anel2", "anel3", "anel4"])]
NOMES_SLOT = {"cabeca": "cabeça", "maos": "mãos", "anel1": "anel 1", "anel2": "anel 2", "anel3": "anel 3", "anel4": "anel 4"}
WIKI = "https://darksouls2.wiki.fextralife.com/"
ELEM = {"fisico": "físico", "magico": "mágico", "fogo": "fogo", "raio": "raio", "sombrio": "sombrio"}


def _catalisador(cat: str, nome: str) -> bool:
    return cat == "SpellTools" or nome.endswith("Pyromancy Flame")


def copias(snapshot: dict) -> dict[int, tuple[int, int]]:
    """Item -> (reforço, infusão) da cópia de maior reforço no inventário."""
    out = {}
    for it in snapshot["inventory"]:
        nivel = it.get("upgrade") or 0
        if it["id"] not in out or nivel > out[it["id"]][0]:
            out[it["id"]] = (nivel, it.get("infusao") or 0)
    return out


def peca(calc, names, item_id: int, nivel: int, stats: dict, infusao: int = 0) -> dict:
    cat, nome = names.get(item_id, ("?", f"#{item_id}"))
    out = {"id": item_id, "nome": nome, "link": WIKI + nome.replace(" ", "+"), "categoria": cat, "nivel": nivel}
    w = calc.weapons.get(item_id)
    if w is None:
        return out
    req = {k: w[f"req_{k.lower()}"] for k in ("STR", "DEX", "INT", "FTH") if w.get(f"req_{k.lower()}")}
    out["requisito"], out["requisito_ok"] = req, all(stats[k] >= v for k, v in req.items())
    out.update({"infusao": infusao, "infusao_nome": ds2calc.INFUSOES[infusao][0], "conferido": calc.conferido(item_id, infusao)})
    if _catalisador(cat, nome):
        out["tipo"] = "catalisador"
        out["ar"] = calc.catalyst_ar(item_id, nivel, stats, infusao)
        out["partes"] = calc.catalyst_parts(item_id, nivel, stats, infusao)
        if nome in ds2calc.ESCALA_HOLLOWING:
            out["aviso"] = ds2calc.ESCALA_HOLLOWING[nome]
    else:
        out["tipo"] = "escudo" if cat == "Shields" else "arma"
        ar = calc.weapon_ar(item_id, nivel, infusao, stats)
        if set(ar) <= {"fisico"}:
            out["ar"] = ar.get("fisico", 0)
            out["partes"] = calc.physical_parts(item_id, nivel, stats, infusao)
        else:  # dano elemental próprio (Moonlight Greatsword) ou da infusão
            out["ar"] = ar
            out["partes"] = calc.weapon_parts(item_id, nivel, infusao, stats)
    return out


def _resumo_peca(p: dict | None) -> str:
    if not p:
        return "vazio"
    nivel = f" +{p['nivel']}" if p.get("tipo") in ("arma", "escudo", "catalisador") else ""
    if p.get("infusao"):
        nivel += f" {p['infusao_nome']}"
    if isinstance(p.get("ar"), dict):
        return f"{p['nome']}{nivel} · " + " · ".join(f"{ELEM[k]} {v}" for k, v in p["ar"].items())
    if p.get("ar") is not None:
        return f"{p['nome']}{nivel} · AR {p['ar']}"
    return p["nome"]


def _numero(p: dict | None) -> int | None:
    if not p or p.get("ar") is None:
        return None
    return max(p["ar"].values()) if isinstance(p["ar"], dict) else p["ar"]


def _sintonia(calc, names_por_nome, lista: list[str], cats: list[dict], stats: dict) -> list[dict]:
    out = []
    for nome in lista:
        spell_id = names_por_nome.get(nome.casefold())
        if spell_id is None or spell_id not in calc.spells:
            raise SaveError(f"feitiço '{nome}' não encontrado")
        melhor = None
        for c in cats:
            r = calc.spell(spell_id, c["ar"], stats)
            if r["ar"] is not None and (melhor is None or r["ar"] > melhor[0]):
                melhor = (r["ar"], c["nome"])
        base = calc.spell(spell_id, {}, stats)
        out.append({"id": spell_id, "nome": names_por_nome[f"#nome:{spell_id}"], "link": WIKI + nome.replace(" ", "+"),
                    "ar": melhor[0] if melhor else None, "catalisador": melhor[1] if melhor else None,
                    "usos": base["usos"], "slots": base["slots"], "requisito_ok": base["requisito_ok"],
                    "requisito": {k: v for k, v in (("INT", base["req_int"]), ("FTH", base["req_fth"])) if v}})
    return out


def equipamento(calc, names: dict, snapshot: dict, trocas: dict | None = None, sintonia_plano: list[str] | None = None,
                atributos: dict | None = None) -> dict:
    """trocas: slot -> (nome ou None para vazio, nível[, infusão]). Devolve agora × plano por slot, sintonia e o resumo."""
    trocas = trocas or {}
    por_nome = {}
    for item_id, (_cat, nome) in names.items():
        por_nome.setdefault(nome.casefold(), item_id)
        por_nome[f"#nome:{item_id}"] = nome
    tem = copias(snapshot)
    eq = snapshot["equipped"]
    vazio = lambda i: i == EMPTY_HAND or i - ARMOR_ITEM_OFFSET in EMPTY_ARMOR  # noqa: E731 (snapshot antigo)
    ids_agora = {**{k: v["id"] for k, v in eq.get("hands", {}).items()}, **{k: v["id"] for k, v in eq.get("armor", {}).items()},
                 **{f"anel{i + 1}": r["id"] for i, r in enumerate(eq.get("rings", []))}}
    ids_agora = {k: v for k, v in ids_agora.items() if not vazio(v)}
    ids_plano = dict(ids_agora)
    niveis_plano = {}
    for slot, (nome, nivel, *infusao) in trocas.items():
        if not any(slot in s for _g, s in SLOTS):
            raise SaveError(f"slot desconhecido: {slot}")
        if nome is None:
            ids_plano.pop(slot, None)
            continue
        item_id = por_nome.get(nome.casefold())
        if item_id is None:
            raise SaveError(f"item '{nome}' não encontrado")
        ids_plano[slot] = item_id
        niveis_plano[slot] = (nivel, infusao[0] if infusao else tem.get(item_id, (0, 0))[1])

    def stats_de(ids: dict, extra: dict | None) -> tuple[dict, list[str]]:
        aneis = [{"name": names.get(ids[s], ("", ""))[1]} for s in ("anel1", "anel2", "anel3", "anel4") if s in ids]
        stats, fontes = ds2calc.atributos_efetivos({"stats": {**snapshot["stats"], **(extra or {})}, "equipped": {"rings": aneis}})
        return stats, fontes

    st_agora, fontes_agora = stats_de(ids_agora, None)
    st_plano, fontes_plano = stats_de(ids_plano, atributos)
    slots, resumo = [], []
    for grupo, nomes in SLOTS:
        for slot in nomes:
            a = peca(calc, names, ids_agora[slot], *tem.get(ids_agora[slot], (0, 0))[:1], st_agora,
                     tem.get(ids_agora[slot], (0, 0))[1]) if slot in ids_agora else None
            if slot in ids_plano:
                nivel, infusao = niveis_plano.get(slot, tem.get(ids_plano[slot], (0, 0)))
                b = peca(calc, names, ids_plano[slot], nivel, st_plano, infusao)
            else:
                b = None
            chave = lambda p: (p and p["id"], p and p["nivel"], p and p.get("infusao"))  # noqa: E731
            muda = chave(a) != chave(b) or _numero(a) != _numero(b)
            slots.append({"slot": slot, "nome_slot": NOMES_SLOT.get(slot, slot), "grupo": grupo, "agora": a, "plano": b,
                          "muda": bool(muda)})
            if muda:
                na, nb = _numero(a), _numero(b)
                efeito = f"{nb - na:+d}" if na is not None and nb is not None else ("troca" if a and b else "novo" if b else "tira")
                sinal = "+" if na is not None and nb is not None and nb > na else "-" if na is not None and nb is not None and nb < na else ""
                resumo.append({"dado": NOMES_SLOT.get(slot, slot).capitalize() if not slot[0].isupper() else slot,
                               "agora": _resumo_peca(a), "depois": _resumo_peca(b), "efeito": efeito, "sinal": sinal})
    cats_agora = [s["agora"] for s in slots if s["agora"] and s["agora"].get("tipo") == "catalisador" and "aviso" not in s["agora"]]
    cats_plano = [s["plano"] for s in slots if s["plano"] and s["plano"].get("tipo") == "catalisador" and "aviso" not in s["plano"]]
    lista_agora = [s["name"] for s in eq.get("spells", [])]
    sint_agora = _sintonia(calc, por_nome, lista_agora, cats_agora, st_agora)
    sint_plano = _sintonia(calc, por_nome, sintonia_plano if sintonia_plano is not None else lista_agora, cats_plano, st_plano)
    vistos = set()
    for f in sint_plano:
        if f["nome"] in vistos or f["ar"] is None:
            continue
        vistos.add(f["nome"])
        antes = next((x["ar"] for x in sint_agora if x["nome"] == f["nome"]), None)
        if antes != f["ar"]:
            resumo.append({"dado": f["nome"], "agora": "—" if antes is None else str(antes), "depois": str(f["ar"]),
                           "efeito": f"{f['ar'] - antes:+d}" if antes is not None else "novo",
                           "sinal": "+" if antes is None or f["ar"] > antes else "-"})
    return {"atributos": {"agora": {k: st_agora[k] for k in ("STR", "DEX", "INT", "FTH", "ATN")},
                          "plano": {k: st_plano[k] for k in ("STR", "DEX", "INT", "FTH", "ATN")},
                          "aneis_agora": fontes_agora, "aneis_plano": fontes_plano},
            "slots": slots,
            "sintonia": {"total": calc.attunement(st_plano["ATN"])["slots"]
                         + ds2calc.slots_dos_aneis(names.get(ids_plano[k], ("", ""))[1] for k in ids_plano if k.startswith("anel")),
                         "total_agora": calc.attunement(st_agora["ATN"])["slots"]
                         + ds2calc.slots_dos_aneis(names.get(ids_agora[k], ("", ""))[1] for k in ids_agora if k.startswith("anel")),
                         "agora": sint_agora, "plano": sint_plano},
            "resumo": resumo}


def ler_troca(texto: str) -> tuple[str, tuple[str | None, int]]:
    slot, sep, valor = texto.partition("=")
    if not sep or not slot.strip():
        raise ValueError(f"troca inválida: {texto!r} (use SLOT=Nome[:nível])")
    valor = valor.strip()
    if valor in ("-", ""):
        return slot.strip(), (None, 0)
    m = re.match(r"^(.*?)(?::(\d+))?(?::([^:]+))?$", valor)
    troca = (m.group(1).strip(), int(m.group(2) or 0))
    return slot.strip(), troca + ((ds2calc.infusao_codigo(m.group(3)),) if m.group(3) else ())


def main(argv=None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="ds2equip")
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--troca", action="append", default=[])
    parser.add_argument("--sintonia", help="feitiços do plano, separados por vírgula (repita para 2 cópias)")
    parser.add_argument("--atributo", action="append", default=[], help="atributo do plano, ex. INT=35")
    parser.add_argument("--jogo")
    args = parser.parse_args(argv)
    try:
        with open(args.snapshot, encoding="utf-8") as fh:
            snap = json.load(fh)
        trocas = dict(ler_troca(t) for t in args.troca)
        atributos = {}
        for t in args.atributo:
            k, _, v = t.partition("=")
            if k.strip().upper() not in snap["stats"] or not v.strip().isdigit():
                raise ValueError(f"atributo inválido: {t!r}")
            atributos[k.strip().upper()] = int(v)
        sint = [s.strip() for s in args.sintonia.split(",") if s.strip()] if args.sintonia else None
        calc = ds2calc.load(ds2calc.ds2regulation.find_regulation(args.jogo))
        out = equipamento(calc, load_item_names(), snap, trocas, sint, atributos)
    except (SaveError, OSError, ValueError) as err:
        print(json.dumps({"error": str(err)}, ensure_ascii=False))
        return 1
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
