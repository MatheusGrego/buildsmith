"""Mapas que vão para a pasta da página: área limpa (planta por andar + pontos com ícone) e rotas do plano.

- Passo/fonte com nós de `ponto`: posição e andar de cada ponto e rota pelo chão entre pontos seguidos (na área do
  primeiro ponto), gravados em `mapa` no plano publicado. Ponto que não existe na área = ValueError.
- Áreas copiadas: as dos pontos e as MAX_AREAS_POR_NOME com mais itens do plano (pelo nome do item no jogo).
- `mapas/<area>.json`: nome, planta (andares com polígonos), fogueiras, itens (com ícone local e marca do plano),
  inimigos — sem os triângulos do navmesh. `mapas/indice.json`: áreas na ordem do seletor.
"""
import json
from pathlib import Path

MAX_AREAS_POR_NOME = 4


def alvos(plano: dict):
    for passo in plano["passos"]:
        yield passo, passo.get("fluxo", [])
    for item in plano["itens"]:
        for fonte in item.get("fontes", []):
            yield fonte, fonte.get("fluxo", [])


def area_para_pagina(dados: dict, nomes_plano: dict, icone_local) -> dict:
    def ponto_item(p):
        nomes = [i["nome"] for i in p["itens"]]
        do_plano = [nomes_plano[n.casefold()] for n in nomes if n.casefold() in nomes_plano]
        principal = next((n for n in nomes if n.casefold() in nomes_plano), nomes[0] if nomes else None)
        itens = sorted(p["itens"], key=lambda i: i["nome"].casefold() not in nomes_plano)  # o do plano primeiro
        return {"lote": p["lote"], "pos": p["pos"], "andar": p.get("andar"), "itens": itens,
                "icone": icone_local(principal) if principal else None, "plano": bool(do_plano),
                "item_id": do_plano[0] if do_plano else None}

    andares = [{k: a[k] for k in ("id", "altura", "min", "max", "poligonos")} for a in dados["planta"]["andares"]]
    return {
        "area": dados["area"], "nome": dados["nome"], "planta": {"andares": andares},
        "fogueiras": [{"id": f["id"], "nome": f["nome"], "pos": f["pos"], "andar": f.get("andar")} for f in dados["fogueiras"]],
        "itens": [ponto_item(p) for p in dados["itens"]],
        "inimigos": [{"id": e["id"], "pos": e["pos"], "andar": e.get("andar")} for e in dados.get("inimigos", [])],
    }


def preparar(plano: dict, out_dir: Path, carregar_area, listar_areas, icone_local, prebuscar=None) -> dict:
    import ds2mapa
    import ds2planta

    cache = {}

    def area_de(area_id):
        if area_id not in cache:
            cache[area_id] = ds2mapa.com_planta(carregar_area(area_id))
        return cache[area_id]

    atribuir, ordem = [], []
    for alvo, fluxo in alvos(plano):
        nos = [(i + 1, n) for i, n in enumerate(fluxo) if isinstance(n, dict) and isinstance(n.get("ponto"), dict)]
        if not nos:
            continue
        area_id = nos[0][1]["ponto"]["area"]
        dados = area_de(area_id)
        pontos, nomes_areas = [], []
        for n_idx, node in nos:
            pt = node["ponto"]
            nome_area = area_de(pt["area"])["nome"]
            if nome_area not in nomes_areas:
                nomes_areas.append(nome_area)
            if pt["area"] != area_id:
                continue
            try:
                pos = ds2mapa.ponto_de(dados, pt["tipo"], pt["ref"])
            except KeyError:
                raise ValueError(f"ponto {pt['tipo']}:{pt['ref']} não existe em {area_id}") from None
            pontos.append({"n": n_idx, "tipo": pt["tipo"], "ref": pt["ref"], "pos": pos, "nome": node.get("nome", ""),
                           "andar": ds2planta.andar_de(dados["planta"], pos[1])})
        trechos = [ds2mapa.rota(dados, a["pos"], b["pos"]) for a, b in zip(pontos, pontos[1:])]
        atribuir.append((alvo, {"area": area_id, "nome": dados["nome"], "pontos": pontos,
                                "trechos": [t["pontos"] if t else None for t in trechos],
                                "metros": round(sum(t["metros"] for t in trechos if t), 1), "areas": nomes_areas}))
        if area_id not in ordem:
            ordem.append(area_id)

    nomes_plano = {it["item"]["nome"].casefold(): it["id"] for it in plano["itens"]}
    contagem = {}
    for area_id in listar_areas():
        n = sum(1 for p in area_de(area_id)["itens"] if any(i["nome"].casefold() in nomes_plano for i in p["itens"]))
        if n:
            contagem[area_id] = n
    for area_id in sorted(contagem, key=lambda a: -contagem[a])[:MAX_AREAS_POR_NOME]:
        if area_id not in ordem:
            ordem.append(area_id)

    if prebuscar:  # ícones de todos os itens das áreas, de uma vez (em paralelo, com cache)
        prebuscar(sorted({i["nome"] for a in ordem for p in area_de(a)["itens"] for i in p["itens"][:1]}
                         | {i["nome"] for a in ordem for p in area_de(a)["itens"] for i in p["itens"]
                            if i["nome"].casefold() in nomes_plano}))
    files, indice = {}, []
    for area_id in ordem:
        doc = area_para_pagina(area_de(area_id), nomes_plano, icone_local)
        destino = Path(out_dir) / "mapas" / f"{area_id}.json"
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        files[f"mapas/{area_id}.json"] = str(destino)
        indice.append({"area": area_id, "nome": doc["nome"], "itens_plano": sum(1 for p in doc["itens"] if p["plano"])})
    if indice:
        destino = Path(out_dir) / "mapas" / "indice.json"
        destino.write_text(json.dumps(indice, ensure_ascii=False), encoding="utf-8")
        files["mapas/indice.json"] = str(destino)
    for alvo, mapa in atribuir:
        alvo["mapa"] = mapa
    return files
