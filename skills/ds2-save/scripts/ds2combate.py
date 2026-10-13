#!/usr/bin/env python3
"""Combate pelo save, com ou sem plano: Equipamento (agora × melhor), Feitiços, Dano e as compras do Progresso.

- Equipamento: o equipado no save × o melhor. "Melhor" = a arma (R1) e o catalisador de maior AR, com o requisito
  cumprido pelos seus atributos de agora (anéis contam), entre o que você tem e o que dá para pegar agora (índice de
  itens: chão ou loja numa área com fogueira acesa; troca só com a alma no inventário). Com plano da IA, as trocas
  dele valem por cima (ds2equip refaz os números com o save de agora).
- Feitiços: a sintonia do save (ds2calc.sintonia), com o AR no catalisador da mão e no melhor; os sugeridos do plano
  ficam depois.
- Dano: cada arma equipada na mão direita com o próximo reforço e o máximo (almas e materiais, quanto você tem) e a
  troca da R1, se houver.
- Metas (estado da página, coleção `metas`): cada meta ligada simulada (ds2simula) na lista `metas`; a da arma que está
  numa mão vai também em `slot["meta"]`. `armas` = as armas do inventário para o seletor do simulador.

  python ds2combate.py [--personagem NOME | --slot N]
"""
import argparse
import json
import sys
from pathlib import Path

import ds2calc
import ds2equip
import ds2simula
from ds2fontes import acesso_areas, almas, wiki
from ds2save import SaveError, _slug

MAOS = ("R1", "R2", "R3", "L1", "L2", "L3")


def _inventario(snap: dict) -> tuple[dict[int, int], dict[int, int]]:
    """(item -> maior reforço, item -> quantidade) do inventário."""
    nivel, qtd = {}, {}
    for it in snap["inventory"]:
        nivel[it["id"]] = max(nivel.get(it["id"], 0), it.get("upgrade") or 0)
        qtd[it["id"]] = qtd.get(it["id"], 0) + (it.get("quantity") or 0)
    return nivel, qtd


def _pega_agora(item: dict, acesso: dict, almas_tem: set) -> bool:
    for f in item.get("fontes", []):
        areas = f.get("areas") or [f.get("area")]
        if not any(acesso.get(a) == "agora" for a in areas):
            continue
        if f["tipo"] in ("chao", "compra") or f["tipo"] == "troca" and f.get("alma_id") in almas_tem:
            return True
    return False


def _menu(p: dict | None) -> int:
    ar = (p or {}).get("ar")
    return sum(ar.values()) if isinstance(ar, dict) else ar or 0


def _escola(p: dict | None) -> str | None:
    """Elemento principal do catalisador pela tabela do jogo: mágico = cajado, raio = sino, fogo = chama. Só se compara
    catalisador da mesma escola (a chama não conjura feitiço de cajado)."""
    ar = (p or {}).get("ar")
    return max(ar, key=ar.get) if isinstance(ar, dict) and ar else None


def melhores(calc, names, snap: dict, stats: dict, indice: dict | None) -> dict:
    """Trocas por código: slot -> (nome, nível) da arma e do catalisador melhores que o equipado."""
    copias = ds2equip.copias(snap)  # (reforço, infusão) da melhor cópia: a arma infundida conta com a infusão
    candidatos = {i: c for i, c in copias.items() if i in calc.weapons}
    if indice:
        acesso = acesso_areas(indice["areas"], snap["progresso"].get("fogueiras", []))
        tem = {it["id"] for it in snap["inventory"]}
        for item in indice["itens"].values():
            if item["cat"] in ("arma", "catalisador") and item["id"] in calc.weapons and item["id"] not in candidatos \
                    and _pega_agora(item, acesso, tem):
                candidatos[item["id"]] = (0, 0)
    pecas = [ds2equip.peca(calc, names, i, n, stats, k) for i, (n, k) in candidatos.items()]
    pecas = [p for p in pecas if p.get("requisito_ok") and "aviso" not in p]
    maos = {k: v["id"] for k, v in snap["equipped"].get("hands", {}).items() if v["id"] != ds2equip.EMPTY_HAND}
    atual = {k: ds2equip.peca(calc, names, i, *copias.get(i, (0, 0))[:1], stats, copias.get(i, (0, 0))[1]) for k, i in maos.items()}
    trocas = {}
    armas = [p for p in pecas if p.get("tipo") == "arma" and p["categoria"] == "MeleeWeapons"]
    if armas and ("R1" not in atual or atual["R1"].get("tipo") == "arma"):
        melhor = max(armas, key=lambda p: ds2equip._numero(p) or 0)
        if (ds2equip._numero(melhor) or 0) > (ds2equip._numero(atual.get("R1")) or 0):
            trocas["R1"] = (melhor["nome"], melhor["nivel"])
    cats = [p for p in pecas if p.get("tipo") == "catalisador"]
    usados = {atual[k]["nome"] for k in MAOS if atual.get(k, {}).get("tipo") == "catalisador"}
    for k in MAOS:  # cada catalisador na mão contra os da mesma escola
        if atual.get(k, {}).get("tipo") != "catalisador":
            continue
        mesma = [p for p in cats if _escola(p) == _escola(atual[k]) and p["nome"] not in usados]
        melhor = max(mesma, key=_menu, default=None)
        if melhor and _menu(melhor) > _menu(atual[k]):
            trocas[k] = (melhor["nome"], melhor["nivel"])
            usados.add(melhor["nome"])
    return trocas


def _trocas_do_plano(plano: dict | None, names: dict) -> dict:
    conhecidos = {n.casefold() for _c, n in names.values()}
    out = {}
    for s in ((plano or {}).get("equipamento") or {}).get("slots", []):
        if not isinstance(s, dict) or not s.get("muda"):
            continue
        p = s.get("plano")
        if p is None:
            out[s["slot"]] = (None, 0)
        elif isinstance(p, dict) and str(p.get("nome", "")).casefold() in conhecidos:
            out[s["slot"]] = (p["nome"], int(p.get("nivel") or 0))
    return out


def _icones(eq: dict, indice: dict | None) -> None:
    for s in eq["slots"]:
        for lado in ("agora", "plano"):
            p = s.get(lado)
            icone = ((indice or {}).get("itens", {}).get(str(p["id"])) or {}).get("icone") if p else None
            if icone:
                p["icone"] = icone


def _no_item(nome: str, sub: str = "", **extra) -> dict:
    return {"tipo": "item", "nome": nome, "link": wiki(nome), **({"sub": sub} if sub else {}), **extra}


def feiticos(calc, snap: dict, eq: dict, plano: dict | None) -> dict:
    """Bloco `feiticos` da página pelo save: catalisador da mão, slots e cada feitiço com o AR agora e no melhor."""
    novos = [(s["plano"]["id"], s["plano"]["nome"], s["plano"]["nivel"]) for s in eq["slots"]
             if s["muda"] and s.get("plano") and s["plano"].get("tipo") == "catalisador"]
    sint = ds2calc.sintonia(calc, snap, candidatos=novos)
    mao = next((c for c in sint["catalisadores"] if c["equipado"]), None)
    if mao:
        catalisador = _no_item(mao["nome"], f"+{mao['nivel']} · menu {mao['menu']}", tem=True)
    else:
        catalisador = {"tipo": "item", "nome": "sem catalisador na mão"}
    lista = []
    for f in sint["feiticos"]:
        m = f.get("melhor")
        sub = f"{m['catalisador']}: {m['ar']}" if m and m["ar"] is not None and m["catalisador"] != f["catalisador_atual"] else ""
        req = " · ".join(t for t in (f"INT {f['req_int']}" if f["req_int"] else "", f"FTH {f['req_fth']}" if f["req_fth"] else "") if t)
        lista.append({"id": _slug(f["nome"]), "no": _no_item(f["nome"], sub, tem=True),
                      "estado": "equipado" if f["equipado"] else "tem", "elemento": ds2equip.ELEM.get(f["elemento"], "—"),
                      "ar": f["ar_atual"], "usos": f["usos"], "slots": f["slots"], "requisito": req or "—",
                      "requisito_ok": f["requisito_ok"]})
    vistos = {s["id"] for s in lista}
    for s in ((plano or {}).get("feiticos") or {}).get("lista", []):
        if isinstance(s, dict) and s.get("estado") == "sugerido" and s.get("id") not in vistos:
            lista.append(s)
            vistos.add(s.get("id"))
    total = sint["slots"]["slots"] + sint["slots"]["aneis"]
    return {"catalisador": catalisador, "ar": mao["ar"] if mao else {}, "slots": {"total": total, "faixa": sint["slots"]["faixa"]},
            "lista": lista}


def _custo(data, names, qtd: dict, almas_tem: int, item_id: int, de: int, ate: int) -> list[dict]:
    try:
        c = data.upgrade_cost(item_id, de, ate)
    except (SaveError, KeyError, IndexError):  # arma sem tabela de reforço no jogo
        return []
    nos = []
    for mat, precisa in c["materiais"].items():
        if not mat or mat not in names:
            continue
        tem = qtd.get(mat, 0)
        nos.append(_no_item(names[mat][1], f"×{precisa} · tem {tem}", **({"tem": True} if tem >= precisa else {})))
    if c["almas_total"]:
        nos.append({"tipo": "almas", "nome": f"{almas(c['almas_total'])} almas", "sub": f"tem {almas(almas_tem)}"})
    return nos


def dano(calc, data, names, snap: dict, stats: dict, eq: dict) -> list[dict]:
    """Linhas da aba Dano: reforço seguinte e máximo de cada arma da mão direita e a troca da R1."""
    _nivel, qtd = _inventario(snap)
    out = []
    for s in eq["slots"]:
        a = s.get("agora")
        if s["slot"] not in ("R1", "R2", "R3") or not a or a.get("tipo") != "arma" or not ds2equip._numero(a):
            continue  # ferramenta na mão (Binoculars, tocha) tem AR 0: nada a reforçar
        maximo = calc.reinforce[calc.weapons[a["id"]]["reinforce_id"]]["nivel_max"]
        arma = _no_item(a["nome"], f"+{a['nivel']}", tem=True, **({"icone": a["icone"]} if a.get("icone") else {}))
        alvos = [a["nivel"] + 1] + ([maximo] if a["nivel"] + 1 < maximo else []) if a["nivel"] < maximo else []
        for k in alvos:
            depois = ds2equip.peca(calc, names, a["id"], k, stats, a.get("infusao") or 0)
            out.append({"arma": arma, "agora": ds2equip._numero(a), "depois": ds2equip._numero(depois),
                        "detalhe": f"reforço +{a['nivel']} → +{k}",
                        "por_causa": _custo(data, names, qtd, snap.get("souls") or 0, a["id"], a["nivel"], k)})
    r1 = next((s for s in eq["slots"] if s["slot"] == "R1"), None)
    if r1 and r1["muda"] and r1.get("agora") and r1.get("plano") and r1["plano"].get("tipo") == "arma":
        a, b = r1["agora"], r1["plano"]
        out.append({"arma": _no_item(b["nome"], f"+{b['nivel']}", **({"icone": b["icone"]} if b.get("icone") else {})),
                    "agora": ds2equip._numero(a), "depois": ds2equip._numero(b),
                    "detalhe": f"troca: {a['nome']} +{a['nivel']} → {b['nome']} +{b['nivel']}", "por_causa": []})
    return out


def compras(snap: dict) -> list[dict]:
    out = []
    for c in snap.get("progresso", {}).get("compras", []):
        loja, item = c.get("loja") or "?", c.get("item") or f"linha {c.get('linha')}"
        out.append({"loja": {"tipo": "npc", "nome": loja, "link": wiki(loja)}, "item": {"tipo": "item", "nome": item, "link": wiki(item)},
                    "qtd": c.get("qtd") or 0})
    return out


def metas_simuladas(calc, data, names: dict, snap: dict, eq: dict, metas: dict | None) -> list[dict]:
    """Metas ligadas com o resultado do simulador; documento estranho fica de fora, arma inválida vem com `erro`."""
    lista, por_id = [], {}
    for doc in (metas or {}).values():
        if not isinstance(doc, dict) or doc.get("ativa") is not True:
            continue
        try:
            item_id, nivel, infusao = int(doc["item_id"]), int(doc["nivel"]), int(doc["infusao"])
        except (KeyError, TypeError, ValueError):
            continue
        m = {"item_id": item_id, "nivel": nivel, "infusao": infusao}
        try:
            m["resultado"] = ds2simula.simular(calc, data, names, snap, item_id, nivel, infusao)
        except (SaveError, KeyError, IndexError) as err:
            m.update({"erro": str(err), "nome": names.get(item_id, ("", f"#{item_id}"))[1]})
        lista.append(m)
        por_id[item_id] = m
    for s in eq["slots"]:
        m = por_id.get((s.get("agora") or {}).get("id"))
        if s["slot"] in MAOS and m and "resultado" in m:
            s["meta"] = m["resultado"]
    return lista


def combate(calc, data, names: dict, snap: dict, indice: dict | None = None, plano: dict | None = None,
            metas: dict | None = None) -> dict:
    stats, _fontes = ds2calc.atributos_efetivos(snap)
    trocas = melhores(calc, names, snap, stats, indice)
    do_plano = _trocas_do_plano(plano, names)
    trocas.update(do_plano)
    eq = ds2equip.equipamento(calc, names, snap, trocas)
    eq["origem"] = "plano" if do_plano else "melhor que dá para pegar agora" if indice else "o que você tem"
    _icones(eq, indice)
    return {"equipamento": eq, "feiticos": feiticos(calc, snap, eq, plano), "dano": dano(calc, data, names, snap, stats, eq),
            "compras": compras(snap), "metas": metas_simuladas(calc, data, names, snap, eq, metas),
            "armas": ds2simula.armas_do_inventario(names, snap)}


def main(argv=None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    import ds2arquivos
    import ds2data
    import ds2itens
    import ds2mapa
    import ds2save

    parser = argparse.ArgumentParser(prog="ds2combate")
    parser.add_argument("--personagem", help="nome do personagem")
    parser.add_argument("--slot", type=int)
    parser.add_argument("--save")
    args = parser.parse_args(argv)
    try:
        save = Path(args.save) if args.save else ds2save.find_save()
        slot = ds2save.slot_by_name(save, args.personagem) if args.personagem else args.slot
        snap = ds2save.snapshot(save, slot)
        game = ds2arquivos.game_dir_padrao()
        indice = ds2itens.carregar(game, ds2mapa._cache_padrao()) if game else None
        out = combate(ds2calc.load(), ds2data.load(), ds2save.load_item_names(), snap, indice)
    except (SaveError, OSError, ValueError, KeyError) as err:
        print(json.dumps({"error": str(err)}, ensure_ascii=False))
        return 1
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
