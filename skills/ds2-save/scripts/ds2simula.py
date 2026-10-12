#!/usr/bin/env python3
"""Simulador de arma: AR de uma arma em qualquer reforço e infusão com os atributos do save, e o que falta para chegar lá
a partir da cópia que o jogador tem (reforço, pedra, almas, ferreiro). Sem IA: tabelas do jogo (ds2calc, ds2data) e o save.

Infusão: 2.000 almas + a pedra; tirar: 1.000 almas + Palestone; só o Steady Hand McDuff infunde (wiki, cache
steady-hand-mcduff.md). Reforço: qualquer ferreiro. O jogo não desfaz reforço.

  python ds2simula.py [--personagem NOME | --slot N | --snapshot S] --item NOME|ID --nivel N [--infusao fogo|3]
"""
import argparse
import json
import sys
from pathlib import Path

import ds2calc
import ds2equip
from ds2save import SaveError

INFUSAO_ALMAS, TIRAR_ALMAS = 2000, 1000
PALESTONE = "Palestone"
MCDUFF = "Steady Hand McDuff"
CATEGORIAS_ARMA = ("MeleeWeapons", "RangedWeapons", "SpellTools", "Shields")


def _id_do_nome(names: dict, nome: str) -> int:
    for item_id, (_cat, n) in names.items():
        if n.casefold() == nome.casefold():
            return item_id
    raise SaveError(f"item '{nome}' não está nas listas de itens")


def armas_do_inventario(names: dict, snap: dict) -> list[dict]:
    """Armas, escudos e catalisadores do inventário, uma vez cada, com o reforço e a infusão da melhor cópia."""
    tem = ds2equip.copias(snap)
    out = []
    for item_id, (nivel, infusao) in tem.items():
        cat, nome = names.get(item_id, ("?", f"#{item_id}"))
        if cat in CATEGORIAS_ARMA:
            out.append({"id": item_id, "nome": nome, "categoria": cat, "nivel": nivel, "infusao": infusao,
                        "infusao_nome": ds2calc.INFUSOES[infusao][0]})
    return sorted(out, key=lambda a: a["nome"])


def simular(calc, data, names: dict, snap: dict, item_id: int, nivel: int, infusao: int, atributos: dict | None = None) -> dict:
    stats, aneis = ds2calc.atributos_efetivos({"stats": {**snap["stats"], **(atributos or {})}, "equipped": snap["equipped"]})
    peca = ds2equip.peca(calc, names, item_id, nivel, stats, infusao)  # SaveError: arma, nível ou infusão inválidos
    copia = ds2equip.copias(snap).get(item_id)
    agora = ds2equip.peca(calc, names, item_id, copia[0], stats, copia[1]) if copia else None
    qtd = {}
    for it in snap["inventory"]:
        qtd[it["id"]] = qtd.get(it["id"], 0) + (it.get("quantity") or 0)
    de_nivel, de_inf = copia or (0, 0)
    falta = {"almas": 0, "almas_tem": snap.get("souls") or 0, "materiais": [], "ferreiro": None, "avisos": []}
    if copia is None:
        falta["avisos"].append("não está no inventário: custo a partir de +0 normal")

    def material(mat_id: int, n: int) -> None:
        falta["materiais"].append({"item": names.get(mat_id, ("", f"#{mat_id}"))[1], "id": mat_id, "qtd": n, "tem": qtd.get(mat_id, 0)})

    if nivel > de_nivel:
        custo = data.upgrade_cost(item_id, de_nivel, nivel)
        falta["almas"] += custo["almas_total"]
        for mat_id, n in custo["materiais"].items():
            if mat_id:
                material(mat_id, n)
        falta["ferreiro"] = "qualquer ferreiro"
    elif nivel < de_nivel:
        falta["avisos"].append(f"o jogo não desfaz reforço: a sua está em +{de_nivel}")
    if infusao != de_inf:
        pedra = ds2calc.INFUSOES[infusao][2] or PALESTONE
        material(_id_do_nome(names, pedra), 1)
        falta["almas"] += INFUSAO_ALMAS if infusao else TIRAR_ALMAS
        falta["ferreiro"] = MCDUFF
    return {"item": {"id": item_id, "nome": peca["nome"]}, "nivel": nivel, "infusao": infusao,
            "infusao_nome": ds2calc.INFUSOES[infusao][0], "peca": peca, "agora": agora,
            "nivel_max": calc.reinforce[calc.weapons[item_id]["reinforce_id"]]["nivel_max"],
            "infusoes": [{"k": k, "nome": ds2calc.INFUSOES[k][0], "pedra": ds2calc.INFUSOES[k][2]} for k in calc.infusoes(item_id)],
            "conferido": calc.conferido(item_id, infusao), "falta": falta,
            "atributos": {k: stats[k] for k in ("STR", "DEX", "INT", "FTH")}, "aneis": aneis}


def main(argv=None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    import ds2data
    import ds2save

    parser = argparse.ArgumentParser(prog="ds2simula")
    parser.add_argument("--personagem")
    parser.add_argument("--slot", type=int)
    parser.add_argument("--snapshot", help="saída do ds2save.py snapshot (em vez de ler o save)")
    parser.add_argument("--item", required=True, help="nome ou id da arma")
    parser.add_argument("--nivel", type=int, default=0)
    parser.add_argument("--infusao", default="0", help="código (0-9) ou nome: fogo, magica, raio, sombria, raw...")
    args = parser.parse_args(argv)
    try:
        names = ds2save.load_item_names()
        if args.snapshot:
            snap = json.loads(Path(args.snapshot).read_text(encoding="utf-8"))
        else:
            save = ds2save.find_save()
            snap = ds2save.snapshot(save, ds2save.slot_by_name(save, args.personagem) if args.personagem else args.slot)
        item_id = int(args.item) if args.item.isdigit() else _id_do_nome(names, args.item)
        out = simular(ds2calc.load(), ds2data.load(), names, snap, item_id, args.nivel, ds2calc.infusao_codigo(args.infusao))
    except (SaveError, OSError, ValueError, KeyError) as err:
        print(json.dumps({"error": str(err)}, ensure_ascii=False))
        return 1
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
