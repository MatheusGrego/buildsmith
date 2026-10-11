#!/usr/bin/env python3
"""Onde pegar um item, ordenado por código para um personagem (sem IA).

Recebe uma entrada do índice (ds2itens) e o estado do personagem lido do save (fogueiras acesas, nível, almas,
atributos, inventário, equipado, chefes derrotados) e devolve as fontes com:
- acesso: "agora" = área com fogueira acesa no save (Majula e Things Betwixt sempre, rota.json); "em_breve" = área não
  liberada até a próxima depois da mais avançada liberada na rota de progressão (games/ds2/rota.json, da wiki);
  "tarde" = o resto (inclusive o que está fora da rota: DLC, memórias);
- rota: da fogueira acesa da área mais perto do ponto (NPC, item, inimigo, chefe) até ele, pelo chão (ds2mapa), com as
  portas do caminho, a chave de cada uma, se está aberta no save e se você tem a chave;
- faltam: almas (preço acima do que você tem), chave (porta fechada sem a chave), alma de chefe (troca);
- destaques: uma "mais_cedo" (a primeira que dá para pegar: área liberada, mais perto da fogueira) e no máximo uma
  "mais_rentavel" (loja de estoque ilimitado ou, sem ela, drop repetível de inimigo);
- feito: item do chão já pego ou chefe já derrotado (fica por último);
- condicao: o que só a wiki diz (loja que abre por evento, chance de drop) aparece como "ver na wiki".
E o requisito do item contra os atributos (com anel que soma atributo): quantos níveis e almas faltam (level_costs).

  python ds2fontes.py fontes --item X [--personagem NOME | --slot N] [--plano]
"""
import argparse
import json
import math
import re
import sys
from pathlib import Path
from urllib.parse import quote

ACESSOS = ("agora", "em_breve", "tarde")
TIPOS = ("compra", "troca", "chao", "drop", "recompensa")
ROTAS_POR_ITEM = 8  # rotas pelo chão calculadas por item (as mais perto em linha reta); o resto ordena pela linha reta
WIKI = "https://darksouls2.wiki.fextralife.com/"
EQUIPAVEIS = {"arma", "escudo", "catalisador", "armadura", "anel", "feitico", "milagre", "piromancia", "hex"}
CONDICAO_LOJA = "a loja pode abrir só depois de um evento — ver na wiki"
CONDICAO_DROP = "chance de drop não lida — ver na wiki"
PASSO_DA_FONTE = {"compra": "compra", "troca": "troca", "chao": "explorar", "drop": "farm", "recompensa": "chefe"}
NO_ITEM = {"bau": "baú", "cadaver": "cadáver"}


def wiki(nome: str) -> str:
    return WIKI + quote(nome.strip().replace(" ", "+"), safe="+&()',-.")


def almas(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def _curto(texto: str, limite: int) -> str:
    return texto if len(texto) <= limite else texto[:limite - 1].rstrip() + "…"


def acesso_areas(areas: dict, acesas) -> dict[str, str]:
    acesas = set(acesas)
    liberadas = {a for a, info in areas.items() if info.get("ordem") == -1 or acesas & set(info.get("fogueiras", []))}
    mais_longe = max((areas[a]["ordem"] for a in liberadas if 0 <= areas[a].get("ordem", 100) < 100), default=-1)
    return {a: "agora" if a in liberadas else "em_breve" if 0 <= info.get("ordem", 100) <= mais_longe + 1 else "tarde"
            for a, info in areas.items()}


def _dist(a, b) -> float:
    return math.dist(a, b)


def _inventario(pers: dict) -> dict[str, int]:
    out = {}
    for it in pers.get("itens", []):
        out[it["nome"].casefold()] = out.get(it["nome"].casefold(), 0) + (it.get("qtd") or 0)
    return out


def atributos(pers: dict) -> dict:
    """Atributos com os anéis que somam atributo (ds2calc.ANEIS_ATRIBUTO), como o jogo usa no requisito."""
    import ds2calc

    aneis = [{"name": n} for n in pers.get("equipado", [])]
    return ds2calc.atributos_efetivos({"stats": pers["stats"], "equipped": {"rings": aneis}})[0]


def requisito(item: dict, pers: dict) -> dict | None:
    import ds2save

    stats = atributos(pers)
    faltam = {k: v - stats.get(k, 0) for k, v in item.get("req", {}).items() if stats.get(k, 0) < v}
    if not faltam:
        return None
    niveis = sum(faltam.values())
    custo = ds2save.level_costs()
    nivel = pers.get("nivel") or 0
    precos = [custo.get(n) for n in range(nivel + 1, nivel + niveis + 1)]
    return {"faltam": faltam, "niveis": niveis, "almas": sum(precos) if nivel and None not in precos else None}


def _npc_no_mapa(dados: dict, linha: int, nome: str) -> list[dict]:
    return [n for n in dados.get("npcs", []) if n["id"] == linha // 10000 or n["nome"].casefold() == (nome or "").casefold()]


def _gerador_npc(dados: dict, npc_id: int, pos) -> int | None:
    gens = [e for e in dados.get("inimigos", []) if e.get("papel") == "npc" and (e.get("personagem") or 0) // 10000 == npc_id]
    return min(gens, key=lambda e: _dist(e["pos"], pos))["id"] if gens else None


def _destinos(fonte: dict, dados: dict) -> list[dict]:
    """Pontos do mapa onde a fonte está: {pos, tipo, ref, nome} (tipo/ref = ponto do mapa da página, ds2mapa.ponto_de)."""
    t = fonte["tipo"]
    if t == "chao":
        return [{"pos": fonte["pos"], "tipo": "item", "ref": fonte["lote"], "nome": fonte.get("item_nome", "")}]
    if t in ("compra", "troca"):
        return [{"pos": n["pos"], "tipo": "inimigo", "ref": _gerador_npc(dados, n["id"], n["pos"]), "nome": n["nome"]}
                for n in _npc_no_mapa(dados, fonte["linha"], fonte["npc"])]
    if t == "drop":
        return [{"pos": e["pos"], "tipo": "inimigo", "ref": e["id"], "nome": fonte.get("inimigo") or ""}
                for e in dados.get("inimigos", [])
                if e.get("tipo") in (fonte.get("tipos_inimigo") or [fonte["tipo_inimigo"]]) and not e.get("papel")]
    return [{"pos": c["pos"], "tipo": "inimigo", "ref": None, "nome": c["nome"]}
            for c in dados.get("chefes", []) if c.get("flag") == fonte["flag"]]


def _andar(dados: dict, y: float):
    if not dados.get("planta"):
        return None
    import ds2planta

    return ds2planta.andar_de(dados["planta"], y)


def _rota(fonte: dict, dados: dict, grafo, acesas: set, estado: dict | None, tem: dict, caixas=None) -> dict | None:
    """Rota da fogueira acesa mais perto (em linha reta) até o ponto mais perto dela, com as portas e o desenho do mapa."""
    import ds2mapa

    fogueiras = [f for f in dados.get("fogueiras", []) if f["id"] in acesas]
    destinos = [d for d in _destinos(fonte, dados) if d["pos"]]
    if not fogueiras or not destinos:
        return None
    fog, alvo = min(((f, d) for f in fogueiras for d in destinos), key=lambda fd: _dist(fd[0]["pos"], fd[1]["pos"]))
    r = ds2mapa.rota(dados, fog["pos"], alvo["pos"], grafo, caixas)
    if r is None:
        return None
    objetos = {o["parte"]: o for o in dados.get("objetos", [])}
    estado_obj = (estado or {}).get("objetos") or {}
    portas, desenho = [], []
    for p in r["portas"]:
        o = objetos.get(p["parte"], {})
        chave = o.get("chave")
        portas.append({"parte": p["parte"], "nome": p["nome"] or "Porta", "metros": p["metros"],
                       "chave": chave[1] if chave else None, "aberta": estado_obj.get(p["parte"]),
                       "tem_chave": bool(chave and tem.get(chave[1].casefold()))})
        desenho.append({**p, "chave": {"id": chave[0], "nome": chave[1], "fonte": o.get("chave_fonte") or "modelo"} if chave else None})
    pontos = [{"n": 1, "tipo": "fogueira", "ref": fog["id"], "pos": list(fog["pos"]), "nome": fog["nome"],
               "andar": _andar(dados, fog["pos"][1])},
              {"n": 2, "tipo": alvo["tipo"], "ref": alvo["ref"], "pos": list(alvo["pos"]), "nome": alvo["nome"],
               "andar": _andar(dados, alvo["pos"][1])}]
    return {"de": {"id": fog["id"], "nome": fog["nome"]}, "metros": r["metros"], "portas": portas,
            "mapa": {"area": dados["area"], "nome": dados["nome"], "pontos": pontos, "trechos": [r["pontos"]],
                     "metros": r["metros"], "areas": [dados["nome"]], "portas": desenho}}


def _linha_reta(fonte: dict, dados: dict, acesas: set) -> float | None:
    fogs = [f["pos"] for f in dados.get("fogueiras", []) if f["id"] in acesas]
    dest = [d["pos"] for d in _destinos(fonte, dados) if d["pos"]]
    return min((_dist(f, d) for f in fogs for d in dest), default=None)


def _rendimento(f: dict) -> str:
    t = f["tipo"]
    if t == "compra":
        return f"{'ilimitado' if f['estoque'] is None else f['estoque']} · {almas(f['preco'])} almas cada"
    if t == "troca":
        return f"1 · alma + {almas(f['preco'])} almas"
    if t == "chao":
        return f"×{f['qtd']} · uma vez"
    if t == "drop":
        return f"drop de {f['quantos']} inimigo{'s' if f['quantos'] != 1 else ''} · repete"
    return "1 · uma vez"


def fontes(item: dict, indice: dict, pers: dict, carregar_area=None, estado_area=None, caixas_de=None) -> dict:
    """Fontes do item ordenadas para o personagem. carregar_area(area) -> (dados do ds2mapa, grafo ou None);
    estado_area(area) -> {"objetos": {parte: aberta}, "lotes": {lote: pego}} do save (ou None)."""
    acesso = acesso_areas(indice["areas"], pers.get("fogueiras", []))
    acesas = set(pers.get("fogueiras", []))
    tem = _inventario(pers)
    derrotados = {c.casefold() for c in pers.get("chefes", [])}
    areas_info = indice["areas"]
    cache_area, cache_estado = {}, {}

    def area(a):
        if a not in cache_area:
            try:
                cache_area[a] = carregar_area(a) if carregar_area else None
            except Exception:  # área sem mapa no jogo: a fonte fica sem rota
                cache_area[a] = None
        return cache_area[a]

    def estado(a):
        if a not in cache_estado:
            try:
                cache_estado[a] = estado_area(a) if estado_area else None
            except Exception:  # save sendo gravado: sem estado do mundo
                cache_estado[a] = None
        return cache_estado[a]

    out = []
    for bruta in item.get("fontes", []):
        f = {**bruta, "item_nome": item["nome"]}
        if f["tipo"] in ("compra", "troca"):
            candidatas = f.get("areas") or []
            f["area"] = min(candidatas, key=lambda a: (ACESSOS.index(acesso.get(a, "tarde")), areas_info.get(a, {}).get("ordem", 100)),
                            default=None)
            f["wiki"], f["condicao"] = wiki(f["npc"] or ""), CONDICAO_LOJA
        elif f["tipo"] == "drop":
            base = re.sub(r"\s*\(.*\)$", "", f.get("inimigo") or "")
            f["wiki"], f["condicao"] = (wiki(base) if base else None), CONDICAO_DROP
        elif f["tipo"] == "recompensa":
            f["wiki"] = wiki(f["chefe"])
        f["acesso"] = acesso.get(f.get("area"), "tarde")
        f["nome_area"] = areas_info.get(f.get("area"), {}).get("nome")
        f["feito"] = False
        if f["tipo"] == "chao" and f.get("area"):
            st = estado(f["area"]) or {}
            f["feito"] = bool((st.get("lotes") or {}).get(str(f["lote"])))
        if f["tipo"] == "recompensa":
            f["feito"] = f["chefe"].casefold() in derrotados
        f["faltam"] = []
        if f["tipo"] == "troca":
            c = f.get("chefe") or {}
            f["chefe_derrotado"] = bool(c.get("nome")) and c["nome"].casefold() in derrotados
            if not tem.get(f["alma"].casefold()):
                f["faltam"].append({"tipo": "alma", "item": f["alma"], "chefe": c.get("nome"), "derrotado": f["chefe_derrotado"]})
        if f["tipo"] in ("compra", "troca") and f["preco"] > (pers.get("almas") or 0):
            f["faltam"].append({"tipo": "almas", "valor": f["preco"] - (pers.get("almas") or 0)})
        f["rota"], f["mapa"], f["rendimento"] = None, None, _rendimento(f)
        dados = area(f["area"])[0] if f["acesso"] == "agora" and f.get("area") and area(f["area"]) else None
        f["_reta"] = _linha_reta(f, dados, acesas) if dados else None
        out.append(f)

    com_reta = sorted((f for f in out if f["_reta"] is not None), key=lambda f: f["_reta"])
    for f in com_reta[:ROTAS_POR_ITEM]:
        dados, grafo = area(f["area"])
        r = _rota(f, dados, grafo, acesas, estado(f["area"]), tem, caixas_de(f["area"]) if caixas_de else None)
        if r:
            f["mapa"] = r.pop("mapa")
            f["rota"] = r
            f["faltam"] += [{"tipo": "chave", "item": p["chave"], "porta": p["nome"]} for p in r["portas"]
                            if p["chave"] and p["aberta"] is not True and not p["tem_chave"]]

    def chave(f):
        metros = f["rota"]["metros"] if f["rota"] else f["_reta"] if f["_reta"] is not None else math.inf
        return (f["feito"], ACESSOS.index(f["acesso"]), metros, areas_info.get(f.get("area"), {}).get("ordem", 100),
                TIPOS.index(f["tipo"]))

    out.sort(key=chave)
    for f in out:
        f["destaques"] = []
        del f["_reta"], f["item_nome"]
    if out:
        cedo = next((f for f in out if not f["feito"]), out[0])
        cedo["destaques"].append("mais_cedo")
        rentaveis = [f for f in out if not f["feito"] and (f["tipo"] == "compra" and f["estoque"] is None or f["tipo"] == "drop")]
        if rentaveis:
            melhor = min(rentaveis, key=lambda f: (ACESSOS.index(f["acesso"]), f["tipo"] != "compra",
                                                   f.get("preco", 0), -f.get("quantos", 0)))
            melhor["destaques"].append("mais_rentavel")
    return {"item": {k: item[k] for k in ("id", "nome", "cat", "req") if k in item} | ({"icone": item["icone"]} if item.get("icone") else {}),
            "tem": tem.get(item["nome"].casefold(), 0),
            "equipado": item["nome"].casefold() in {n.casefold() for n in pers.get("equipado", [])},
            "requisito": requisito(item, pers), "fontes": out}


# ---- Formato do plano (página) -----------------------------------------------------------------------------------

def _no_item(res: dict, sub: str = "") -> dict:
    it = res["item"]
    return {"tipo": "item", "nome": it["nome"], "link": wiki(it["nome"]), **({"icone": it["icone"]} if it.get("icone") else {}),
            **({"sub": _curto(sub, 30)} if sub else {})}


def _no(tipo: str, nome: str, sub: str = "", link: str | None = None) -> dict:
    return {"tipo": tipo, "nome": nome, "link": link or wiki(nome), **({"sub": _curto(sub, 30)} if sub else {})}


def _ponto(f: dict, n: int) -> dict | None:
    p = (f.get("mapa") or {}).get("pontos", [])
    p = next((x for x in p if x["n"] == n), None)
    return {"area": f["mapa"]["area"], "tipo": p["tipo"], "ref": p["ref"]} if p and p.get("ref") else None


def _com_ponto(no: dict, ponto) -> dict:
    return {**no, "ponto": ponto} if ponto else no


def _fogueira(f: dict, area: str) -> list[dict]:
    """Nó da fogueira de onde a rota sai (com o ponto do mapa): o prepare_page refaz a rota entre os pontos do fluxo."""
    if not f.get("rota"):
        return []
    return [_com_ponto(_no("local", f["rota"]["de"]["nome"], "fogueira", wiki(area) if area else None), _ponto(f, 1))]


def fluxo(f: dict, res: dict) -> list[dict]:
    """Nós da fonte: da fogueira acesa (quando há rota) até o NPC, item, inimigo ou chefe, e o item."""
    area = f.get("nome_area") or ""
    t = f["tipo"]
    if t == "compra":
        return _fogueira(f, area) + [_com_ponto(_no("npc", f["npc"], area), _ponto(f, 2)), _no_item(res, f"{almas(f['preco'])} almas")]
    if t == "troca":
        nos = [_no("chefe", f["chefe"]["nome"], "derrotado" if f.get("chefe_derrotado") else "vivo")] if f.get("chefe") else []
        falta_alma = any(x["tipo"] == "alma" for x in f["faltam"])
        nos.append({**_no("item", f["alma"], "falta" if falta_alma else "tem"), **({} if falta_alma else {"tem": True})})
        return nos + _fogueira(f, area) + [_com_ponto(_no("npc", f["npc"], area), _ponto(f, 2)),
                                           _no_item(res, f"{almas(f['preco'])} almas")]
    if t == "chao":
        onde = NO_ITEM.get(f.get("no"), "chão")
        inicio = _fogueira(f, area) or [_no("local", area or f.get("area") or "?", "área", wiki(area) if area else None)]
        return inicio + [_com_ponto(_no_item(res, f"{onde} ×{f['qtd']}"), _ponto(f, 2))]
    if t == "drop":
        nome = f.get("inimigo") or f"inimigo {f['tipo_inimigo']}"
        return _fogueira(f, area) + [_com_ponto(_no("inimigo", nome, area, f.get("wiki")), _ponto(f, 2)), _no_item(res, "drop")]
    return _fogueira(f, area) + [_com_ponto(_no("chefe", f["chefe"], area), _ponto(f, 2)), _no_item(res, "recompensa")]


def _texto_falta(x: dict) -> str:
    if x["tipo"] == "almas":
        return f"faltam {almas(x['valor'])} almas"
    if x["tipo"] == "chave":
        return f"falta {x['item']} ({x['porta']})"
    if x["tipo"] == "alma":
        return f"falta {x['item']}" + (f" ({x['chefe']})" if x.get("chefe") else "")
    return ""


def requisito_texto(f: dict) -> str:
    partes = [_texto_falta(x) for x in f["faltam"]]
    if f.get("condicao"):
        partes.append(f["condicao"])
    return _curto(" · ".join(p for p in partes if p), 80) if partes else ""


def dados_requisito(res: dict) -> list[dict]:
    req = res.get("requisito")
    if not req:
        return []
    linhas = []
    for k, falta in req["faltam"].items():
        alvo = res["item"]["req"][k]
        linhas.append({"dado": k, "agora": str(alvo - falta), "depois": str(alvo), "sinal": "-",
                       "efeito": f"{req['niveis']} níveis" + (f" · {almas(req['almas'])} almas" if req.get("almas") else "")})
    return linhas


def pagina(res: dict) -> dict:
    """Entrada de "Onde pegar" no formato do plano (itens[]): o que a página e o validador já entendem."""
    vivas = [f for f in res["fontes"] if not f["feito"]] or res["fontes"]
    fontes_pag = []
    for f in vivas:
        fp = {"tipo": f["tipo"], "fluxo": fluxo(f, res), "acesso": f["acesso"], "rendimento": f["rendimento"],
              "destaques": list(f["destaques"])}
        req = requisito_texto(f)
        if req:
            fp["requisito"] = req
        if f.get("mapa"):
            fp["mapa"] = f["mapa"]
        fontes_pag.append(fp)
    return {"id": f"quero-{res['item']['id']}", "item": _no_item(res), "fonte": wiki(res["item"]["nome"]),
            "fontes": fontes_pag, "dados": dados_requisito(res)}


def passos(res: dict, pers: dict) -> list[dict]:
    """Passos do item marcado: pegar pela fonte mais cedo (comprar, trocar, explorar, farmar, chefe), upar o que falta
    do requisito e equipar o que já está no inventário."""
    it, out = res["item"], []
    base = f"quero-{it['id']}"
    if not res["tem"]:
        cedo = next((f for f in res["fontes"] if "mais_cedo" in f["destaques"]), None)
        if cedo and not cedo["feito"]:
            tipo = PASSO_DA_FONTE[cedo["tipo"]]
            verbo = {"compra": "Comprar", "troca": "Trocar por", "explorar": "Pegar", "farm": "Farmar", "chefe": "Derrotar"}[tipo]
            alvo = cedo["chefe"] if tipo == "chefe" else it["nome"]
            passo = {"id": f"{base}-{tipo}", "tipo": tipo, "titulo": _curto(f"{verbo} {alvo}", 40), "fluxo": fluxo(cedo, res),
                     "dados": []}
            if cedo.get("mapa"):
                passo["mapa"] = cedo["mapa"]
            out.append(passo)
    req = res.get("requisito")
    if req:
        stats = atributos(pers)
        for k, falta in req["faltam"].items():
            out.append({"id": f"{base}-nivel-{k.lower()}", "tipo": "nivel", "titulo": _curto(f"Upar {k} para {it['nome']}", 40),
                        "fluxo": [{"tipo": "atributo", "nome": k, "sub": f"{stats.get(k, 0)} → {stats.get(k, 0) + falta}"}],
                        "dados": [{"dado": "Almas", "agora": almas(pers.get("almas") or 0),
                                   "depois": almas(req["almas"]) if req.get("almas") else "—", "efeito": f"{req['niveis']} níveis",
                                   "sinal": "-"}]})
    if res["tem"] and not res["equipado"] and it.get("cat") in EQUIPAVEIS and not req:
        out.append({"id": f"{base}-equipar", "tipo": "equipar", "titulo": _curto(f"Equipar {it['nome']}", 40),
                    "fluxo": [_no_item(res, "entra")], "dados": []})
    return out


def para_plano(res: dict, pers: dict) -> dict:
    """Entrada de itens[] e os passos para o plano.json da skill build: sem o desenho da rota (o prepare_page refaz pelo
    `ponto` dos nós), o que também poupa texto."""
    item = pagina(res)
    for f in item["fontes"]:
        f.pop("mapa", None)
    passos_ = passos(res, pers)
    for s in passos_:
        s.pop("mapa", None)
    return {"item": item, "passos": passos_}


# ---- Personagem pelo save ----------------------------------------------------------------------------------------

def personagem_do_save(path, slug: str, names=None) -> dict | None:
    """Estado do personagem que as fontes usam: ao vivo (nível, almas, atributos, inventário, equipado, chefes) e as
    fogueiras acesas, numa leitura do save."""
    import ds2save

    vivo = ds2save.ao_vivo(path, names).get(slug)
    pos = ds2save.posicoes(path).get(slug)
    if vivo is None or pos is None:
        return None
    return {**vivo, "fogueiras": pos["fogueiras"], "area": pos["area"], "pos": pos["pos"]}


def estado_do_save(path, slug: str, carregar_area):
    """estado_area(area) para fontes(): portas e lotes da área com estado conferido no save."""
    import ds2save

    mundo = ds2save.mundos(path).get(slug, b"")

    def estado(area: str) -> dict:
        dados = carregar_area(area)[0]
        objetos = {o["parte"]: o["estado_ref"] for o in dados.get("objetos", []) if o.get("estado_ref")}
        lotes = {str(p["lote"]): p["estado_ref"] for p in dados.get("itens", []) if p.get("estado_ref")}
        st = ds2save.estado_mundo(mundo, [*objetos.values(), *lotes.values()])
        return {"objetos": {k: st[r] for k, r in objetos.items() if st[r] is not None},
                "lotes": {k: st[r] for k, r in lotes.items() if st[r] is not None}}
    return estado


def main(argv=None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    import ds2arquivos
    import ds2itens
    import ds2mapa
    import ds2save

    parser = argparse.ArgumentParser(prog="ds2fontes")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("fontes", help="onde pegar o item, ordenado para o personagem do save")
    p.add_argument("--item", required=True, help="nome ou ID do item")
    p.add_argument("--personagem", help="nome do personagem ou slug da página")
    p.add_argument("--slot", type=int)
    p.add_argument("--save")
    p.add_argument("--plano", action="store_true", help="sai no formato de itens[] do plano (+ passos)")
    p.add_argument("--game", help="pasta Game do DS2 (padrão: a instalação da Steam)")
    p.add_argument("--cache", help="pasta do cache (padrão: ~/.buildsmith/cache/ds2)")
    args = parser.parse_args(argv)
    try:
        game = Path(args.game) if args.game else ds2arquivos.game_dir_padrao()
        if game is None:
            raise ds2mapa.MapaError("DS2 SotFS não encontrado; defina BUILDSMITH_DS2_GAME com a pasta Game")
        cache = Path(args.cache) if args.cache else ds2mapa._cache_padrao()
        indice = ds2itens.carregar(game, cache)
        item = ds2itens.achar(indice, args.item)
        if item is None:
            raise ds2mapa.MapaError(f"item '{args.item}' não está nas listas de itens")
        save = Path(args.save) if args.save else ds2save.find_save()
        lista = ds2save.personagens(save)
        if args.personagem:
            alvo = next((c for c in lista if args.personagem in (c["slug"], c["nome"])), None)
            if alvo is None:
                alvo = next(c for c in lista if c["slot"] == ds2save.slot_by_name(save, args.personagem))
        elif args.slot is not None:
            alvo = next((c for c in lista if c["slot"] == args.slot), None)
        elif len(lista) == 1:
            alvo = lista[0]
        else:
            raise ds2save.SaveError(f"mais de um personagem no save; use --personagem (opções: {[c['nome'] for c in lista]})")
        if alvo is None:
            raise ds2save.SaveError("personagem não está no save")
        grafos = {}

        def carregar_area(area):
            if area not in grafos:
                dados = ds2mapa.extrair_area(game, area, cache)
                grafos[area] = (dados, ds2mapa._grafo(dados))
            return grafos[area]

        pers = personagem_do_save(save, alvo["slug"])
        res = fontes(item, indice, pers, carregar_area, estado_do_save(save, alvo["slug"], carregar_area),
                     lambda area: ds2mapa.caixas_da_cena(cache, area))
        out = para_plano(res, pers) if args.plano else res
    except (ds2mapa.MapaError, ds2arquivos.ArquivoError, ds2save.SaveError, OSError, ValueError, KeyError, StopIteration) as err:
        print(json.dumps({"error": str(err) or type(err).__name__}, ensure_ascii=False))
        return 1
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
