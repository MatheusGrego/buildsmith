#!/usr/bin/env python3
"""O que dá para pegar agora no DS2 SotFS: itens no chão das áreas liberadas e nas lojas, com o número que importa.

Área liberada = acesso "agora" pelos chefes derrotados do snapshot (ds2data.area_status). Chão = lotes do MSB de cada
mapa (ds2mapa, cache em ~/.buildsmith/cache/ds2/mapas). Loja = ShopLineupParam: o NPC pode pedir um evento antes de
vender (confira na wiki). Drop de inimigo não aparece aqui.

  python ds2perto.py catalisadores --snapshot S [--nome REGEX]   AR por elemento no +0 e no máximo (com anéis)
  python ds2perto.py armas --snapshot S [--nome REGEX]           AR físico no +0 e no máximo, requisito de FOR/DES
  python ds2perto.py armaduras --snapshot S [--nome REGEX]       peças por set (para o visual)
"""
import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import ds2arquivos
import ds2calc
import ds2data
import ds2mapa
from ds2save import SaveError, load_item_names

TIPOS = {"catalisadores", "armas", "armaduras"}
PECA = re.compile(r"\s+(Hood|Robes?|Gloves|Boots|Skirt|Top|Cuffs|Bottoms|Mask|Hat|Gauntlets|Leggings|Manchettes|"
                  r"Trousers|Shoes|Crown|Attire|Long Gloves|Wrappings|Waistcloth|Pants|Armor|Helm|Bracelets|Tiara|"
                  r"Headpiece|Gown|Garb|Tunic|Cloak|Sandals|Veil|Chainmail)$")


def no_chao(game_dir, cache_dir, status: dict) -> dict[int, list[dict]]:
    """item_id -> pontos no chão de todos os mapas, com o acesso da área."""
    out = defaultdict(list)
    for a in ds2mapa.areas(game_dir):
        dados = ds2mapa.extrair_area(game_dir, a["area"], cache_dir)
        acesso = status.get(ds2data._norm(dados["nome"]), "?")
        for p in dados["itens"]:
            for it in p["itens"]:
                out[it["id"]].append({"area": dados["area"], "nome_area": dados["nome"], "lote": p["lote"], "acesso": acesso})
    return out


def perto(tipo: str, snapshot: dict, names: dict, data, calc, chao: dict, nome_re=None) -> list[dict]:
    stats, _ = ds2calc.atributos_efetivos(snapshot)
    tem = {i["id"] for i in snapshot["inventory"]}
    filtro = re.compile(nome_re, re.I) if nome_re else None
    out = []
    for item_id, (cat, nome) in names.items():
        catalisador = cat == "SpellTools" or nome.endswith("Pyromancy Flame")
        if tipo == "catalisadores" and not catalisador or tipo == "armas" and (cat != "MeleeWeapons" or catalisador) \
                or tipo == "armaduras" and cat != "Armor" or filtro and not filtro.search(nome):
            continue
        agora = [p for p in chao.get(item_id, []) if p["acesso"] == "agora"]
        lojas = data.shops_for(item_id)
        if not agora and not lojas:
            continue
        linha = {"id": item_id, "nome": nome, "tem": item_id in tem, "chao": agora[:3],
                 "lojas": [{"loja": l["loja"], "preco": l["preco"], "estoque": l["estoque"]} for l in lojas[:3]]}
        if tipo != "armaduras":
            if item_id not in data.weapons:
                continue
            w = data.weapons[item_id]
            linha["requisito"] = {k: w[f"req_{k.lower()}"] for k in ("STR", "DEX", "INT", "FTH") if w[f"req_{k.lower()}"]}
            linha["requisito_ok"] = all(stats[k] >= v for k, v in linha["requisito"].items())
            maximo = calc.reinforce[w["reinforce_id"]]["nivel_max"]
            if tipo == "catalisadores":
                linha["ar"], linha["ar_max"] = calc.catalyst_ar(item_id, 0, stats), calc.catalyst_ar(item_id, maximo, stats)
                if not linha["ar"]:
                    continue
                if nome in ds2calc.ESCALA_HOLLOWING:
                    linha["aviso"] = ds2calc.ESCALA_HOLLOWING[nome]
            else:
                linha["ar"], linha["ar_max"] = calc.physical_ar(item_id, 0, stats), calc.physical_ar(item_id, maximo, stats)
            linha["nivel_max"] = maximo
        else:
            linha["set"] = PECA.sub("", nome)
        out.append(linha)
    if tipo == "armaduras":
        return sorted(out, key=lambda l: (l["set"], l["nome"]))
    valor = (lambda l: max(l["ar"].values())) if tipo == "catalisadores" else (lambda l: l["ar"])
    return sorted(out, key=lambda l: ("aviso" in l, not l["requisito_ok"], -valor(l)))


def main(argv=None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="ds2perto")
    parser.add_argument("tipo", choices=sorted(TIPOS))
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--nome", help="filtro (regex) no nome do item")
    args = parser.parse_args(argv)
    try:
        snap = json.loads(Path(args.snapshot).read_text(encoding="utf-8"))
        game = ds2arquivos.game_dir_padrao()
        if game is None:
            raise SaveError("DS2 SotFS não encontrado (defina BUILDSMITH_DS2_GAME)")
        status = {ds2data._norm(a["area"]): a["acesso"] for a in ds2data.area_status(snap)["areas"]}
        chao = no_chao(game, ds2mapa._cache_padrao(), status)
        out = perto(args.tipo, snap, load_item_names(), ds2data.load(), ds2calc.load(), chao, args.nome)
    except (SaveError, OSError, ValueError, re.error) as err:
        print(json.dumps({"error": str(err)}, ensure_ascii=False))
        return 1
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
