"""Mapas que vão para a pasta da página: área limpa (planta por andar + pontos com ícone) e rotas do plano.

- Passo/fonte com nós de `ponto`: posição e andar de cada ponto e rota pelo chão entre pontos seguidos (na área do
  primeiro ponto), gravados em `mapa` no plano publicado. Ponto que não existe na área = ValueError.
- Áreas copiadas: as dos pontos e as MAX_AREAS_POR_NOME com mais itens do plano (pelo nome do item no jogo).
- `mapas/<area>.json`: nome, planta (andares com polígonos), fogueiras, itens (com ícone local, marca do plano, baú ou
  cadáver e se é chave), inimigos comuns (gerador de NPC e de chefe fica de fora) e os tipos deles (HP, almas e drops
  do jogo; nome pela linha do EnemyParam ou pelo modelo do jogo, ds2nomes; sem isso, pela wiki quando ela confirma; a
  prova vai junto), objetos (portas com a chave e onde pegá-la, alavancas, elevadores, névoas, baús...) — sem os
  triângulos do navmesh. `mapas/indice.json`: áreas na ordem do seletor.
- Área onde o personagem está (posição do save) entra sempre; depois, todas as outras áreas do jogo (o seletor separa
  liberadas e não liberadas pelas fogueiras acesas no save, que a página lê ao vivo do servidor).
- `indice.json`: por área, o rótulo (nome repetido ganha a 1ª fogueira, ex. "Majula · Old Akelarre"), os IDs das
  fogueiras e a posição na rota de progressão da wiki (games/ds2/rota.json; Majula e Things Betwixt primeiro).
"""
import json
from pathlib import Path

MAX_AREAS_POR_NOME = 4
ROTA = Path(__file__).resolve().parents[3] / "games" / "ds2" / "rota.json"


def _norm(area: str) -> str:
    return area.lower().replace("the ", "").replace("-", " ").strip()


def ordem_rota(nome: str, rota: dict | None = None) -> int:
    """Posição da área na rota de progressão: hubs = -1, fora da rota (memórias, DLC) = 100."""
    rota = rota or json.loads(ROTA.read_text(encoding="utf-8"))
    if any(_norm(nome) == _norm(h) for h in rota["hubs"]):
        return -1
    lista = [_norm(a) for a in rota["rota"]]
    return lista.index(_norm(nome)) if _norm(nome) in lista else 100


def rotulos(areas: list[dict]) -> dict[str, str]:
    """Rótulo de cada área no seletor: nome do jogo; nome repetido ganha a 1ª fogueira (ou "sem fogueira")."""
    contagem = {}
    for a in areas:
        contagem[a["nome"].strip()] = contagem.get(a["nome"].strip(), 0) + 1
    out = {}
    for a in areas:
        nome = a["nome"].strip()
        extra = a["fogueiras"][0]["nome"] if a.get("fogueiras") else "sem fogueira"
        out[a["area"]] = f"{nome} · {extra}" if contagem[nome] > 1 else nome
    return out


def alvos(plano: dict):
    for passo in plano["passos"]:
        yield passo, passo.get("fluxo", [])
    for item in plano["itens"]:
        for fonte in item.get("fontes", []):
            yield fonte, fonte.get("fluxo", [])


def precisa_de_npc(plano: dict) -> dict:
    """Nome do NPC (minúsculas) -> o que o plano precisa dele: itens cujas fontes passam pelo NPC e passos com ele."""
    out = {}
    for it in plano["itens"]:
        for f in it.get("fontes", []):
            for n in f.get("fluxo", []):
                if isinstance(n, dict) and n.get("nome"):
                    lista = out.setdefault(n["nome"].casefold(), [])
                    if it["item"]["nome"] not in lista:
                        lista.append(it["item"]["nome"])
    for s in plano["passos"]:
        for n in s.get("fluxo", []):
            if isinstance(n, dict) and n.get("tipo") == "npc" and n.get("nome"):
                lista = out.setdefault(n["nome"].casefold(), [])
                if s["titulo"] not in lista:
                    lista.append(s["titulo"])
    return out


def estado_chefes(plano: dict) -> dict:
    return {c["no"]["nome"].casefold(): c["estado"] for c in plano.get("progresso", {}).get("chefes", [])
            if isinstance(c, dict) and isinstance(c.get("no"), dict) and c["no"].get("nome")}


def _contagem_tipos(dados: dict) -> dict:
    contagem = {}
    for e in dados.get("inimigos", []):
        if e.get("tipo") and not e.get("papel"):
            contagem[str(e["tipo"])] = contagem.get(str(e["tipo"]), 0) + 1
    return contagem


def eh_chefe(base: str | None, chefes: list) -> bool:
    """O inimigo é um chefe de outra área aparecendo como inimigo comum (o Pursuer na Lost Bastille)."""
    b = (base or "").casefold().strip()
    return bool(b) and any(c["nome"].casefold() in (b, b + "s") for c in chefes)


def tipos_para_pagina(dados: dict, nomes: dict, pagina_wiki=None, icone_local=None, chefes: list | None = None) -> dict:
    """tipo -> HP, almas e drops do jogo, quantos há na área e o nome: pela linha/modelo do jogo (ds2nomes) ou pela
    wiki quando ela confirma (nomes); None sem nenhum dos dois. `fonte` diz de onde veio o nome."""
    import ds2nomes

    out = {}
    for t, n in _contagem_tipos(dados).items():
        jogo = dados.get("tipos_inimigo", {}).get(t, {})
        wiki = nomes.get(t) or {}
        doj = ds2nomes.nome_inimigo(t)
        if doj:
            base = doj["base"]
            link = wiki.get("wiki") if wiki.get("nome") == base else (pagina_wiki(base) if pagina_wiki else None)
            nome, prova, fonte = doj["nome"], doj["prova"], doj["fonte"]
        else:
            base, link, nome, prova = wiki.get("nome"), wiki.get("wiki"), wiki.get("nome"), wiki.get("prova")
            fonte = "wiki" if nome else None
        out[t] = {"nome": nome, "base": base, "wiki": link, "prova": prova, "fonte": fonte,
                  "chefe": eh_chefe(base, chefes or []), "retrato": icone_local(base) if (icone_local and base) else None,
                  "n": n, "hp": jogo.get("hp"), "almas": jogo.get("almas"), "drops": jogo.get("drops", [])}
    return out


def sem_nome_do_jogo(dados: dict) -> dict:
    """Tipos de inimigo da área que o jogo não nomeia (nem pela linha nem pelo modelo): só esses vão para a wiki."""
    import ds2nomes

    tipos = dados.get("tipos_inimigo", {})
    return {t: tipos.get(t, {}) for t in _contagem_tipos(dados) if not ds2nomes.nome_inimigo(t)}


def objetos_para_pagina(dados: dict, onde_chave, pagina_wiki=None, icone_local=None) -> list:
    """Objetos da área para a página; porta com chave leva o nome, o ícone e onde a chave está no chão do jogo."""
    out = []
    for o in dados.get("objetos", []):
        item = {k: o.get(k) for k in ("parte", "modelo", "cat", "nome", "pos", "rot", "andar", "zona", "lote")}
        if o.get("chave"):
            cid, cnome = o["chave"]
            item["chave"] = {"id": cid, "nome": cnome, "icone": icone_local(cnome) if icone_local else None,
                             "wiki": pagina_wiki(cnome) if pagina_wiki else None, "onde": onde_chave(cid)}
        out.append(item)
    return out


def area_para_pagina(dados: dict, nomes_plano: dict, icone_local, precisa: dict | None = None, chefes: dict | None = None,
                     pagina_wiki=None, nomes_inimigo: dict | None = None, onde_chave=None, chefes_jogo: list | None = None) -> dict:
    def ponto_item(p):
        nomes = [i["nome"] for i in p["itens"]]
        do_plano = [nomes_plano[n.casefold()] for n in nomes if n.casefold() in nomes_plano]
        principal = next((n for n in nomes if n.casefold() in nomes_plano), nomes[0] if nomes else None)
        itens = sorted(p["itens"], key=lambda i: i["nome"].casefold() not in nomes_plano)  # o do plano primeiro
        return {"lote": p["lote"], "pos": p["pos"], "andar": p.get("andar"), "zona": p.get("zona"), "itens": itens,
                "icone": icone_local(principal) if principal else None, "plano": bool(do_plano),
                "item_id": do_plano[0] if do_plano else None, "no": p.get("no"), "chave": bool(p.get("chave"))}

    precisa, chefes = precisa or {}, chefes or {}
    andares = [{k: a[k] for k in ("id", "altura", "min", "max", "poligonos")} for a in dados["planta"]["andares"]]
    return {
        "area": dados["area"], "nome": dados["nome"], "planta": {"andares": andares},
        "fogueiras": [{"id": f["id"], "nome": f["nome"], "pos": f["pos"], "andar": f.get("andar"), "zona": f.get("zona")} for f in dados["fogueiras"]],
        "itens": [ponto_item(p) for p in dados["itens"]],
        "inimigos": [{"id": e["id"], "pos": e["pos"], "rot": e.get("rot"), "andar": e.get("andar"), "zona": e.get("zona"), "tipo": str(e["tipo"])}
                     for e in dados.get("inimigos", []) if e.get("tipo") and not e.get("papel")],
        "tipos_inimigo": tipos_para_pagina(dados, nomes_inimigo or {}, pagina_wiki, icone_local, chefes_jogo),
        "objetos": objetos_para_pagina(dados, onde_chave or (lambda _id: []), pagina_wiki, icone_local),
        "npcs": [{"id": n["id"], "nome": n["nome"], "pos": n["pos"], "andar": n.get("andar"), "zona": n.get("zona"),
                  "modelo": n.get("modelo"), "rot": n.get("rot"),
                  "retrato": icone_local(n["nome"]), "plano": bool(precisa.get(n["nome"].casefold())),
                  "precisa": precisa.get(n["nome"].casefold(), [])} for n in dados.get("npcs", [])],
        "chefes": [{"flag": c["flag"], "nome": c["nome"], "wiki": (pagina_wiki(c["nome"]) if pagina_wiki else None) or c.get("wiki", ""), "pos": c["pos"], "andar": c.get("andar"),
                    "zona": c.get("zona"), "retrato": icone_local(c["nome"]), "estado": chefes.get(c["nome"].casefold())}
                   for c in dados.get("chefes", [])],
        "zonas": {"ordem_por": dados.get("zonas", {}).get("ordem_por", "nenhuma"),
                  "lista": [{k: z[k] for k in ("ordem", "fogueira", "nome", "poligonos")} for z in dados.get("zonas", {}).get("lista", [])]},
    }


def preparar(plano: dict, out_dir: Path, carregar_area, listar_areas, icone_local, prebuscar=None, pagina_wiki=None,
             nomes_inimigos=None, area_jogador: str | None = None, todas_areas: bool = True) -> dict:
    import ds2mapa
    import ds2planta

    cache = {}

    def area_de(area_id):
        if area_id not in cache:
            cache[area_id] = ds2mapa.com_zonas(carregar_area(area_id))
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
    if area_jogador and area_jogador not in ordem:
        try:
            area_de(area_jogador)
            ordem.append(area_jogador)
        except Exception:  # área sem mapa no jogo (ou nome estranho no save): fica sem
            pass
    if todas_areas:  # o resto do jogo, para o seletor mostrar o que já foi liberado e o que falta
        for area_id in listar_areas():
            if area_id not in ordem:
                try:
                    area_de(area_id)
                    ordem.append(area_id)
                except Exception:
                    pass

    import ds2nomes

    bases_inimigo = {n["base"] for a in ordem for t in _contagem_tipos(area_de(a)) if (n := ds2nomes.nome_inimigo(t))}
    chaves_portas = {o["chave"][1] for a in ordem for o in area_de(a).get("objetos", []) if o.get("chave")}
    if prebuscar:  # ícones de itens, NPCs, chefes, inimigos e chaves das áreas, de uma vez (em paralelo, com cache)
        prebuscar(sorted({i["nome"] for a in ordem for p in area_de(a)["itens"] for i in p["itens"][:1]}
                         | {i["nome"] for a in ordem for p in area_de(a)["itens"] for i in p["itens"]
                            if i["nome"].casefold() in nomes_plano}
                         | {x["nome"] for a in ordem for x in area_de(a).get("npcs", []) + area_de(a).get("chefes", [])}
                         | bases_inimigo | chaves_portas))

    def onde_chave(item_id: int) -> list:
        """Onde a chave está no chão (ou em baú/cadáver) nas áreas da página."""
        return [{"area": a, "nome": area_de(a)["nome"], "lote": p["lote"]} for a in ordem for p in area_de(a)["itens"]
                if any(i["id"] == item_id for i in p["itens"])]

    try:
        import ds2save

        chefes_jogo = json.loads((ds2save.GAME_DIR / "bosses.json").read_text(encoding="utf-8"))["chefes"]
    except (ImportError, OSError, ValueError, KeyError):
        chefes_jogo = []
    files, indice = {}, []
    nomes_rotulo = rotulos([area_de(a) for a in ordem])
    rota = json.loads(ROTA.read_text(encoding="utf-8"))
    for area_id in ordem:
        dados = area_de(area_id)
        nomes = {}
        faltam = sem_nome_do_jogo(dados)
        if nomes_inimigos and faltam:  # a wiki só para o que o jogo não nomeia (poupa centenas de páginas)
            try:
                nomes = nomes_inimigos(faltam, dados["nome"])
            except Exception:  # wiki fora do ar: inimigos ficam sem nome confirmado
                nomes = {}
        doc = area_para_pagina(dados, nomes_plano, icone_local, precisa_de_npc(plano), estado_chefes(plano), pagina_wiki, nomes,
                               onde_chave, chefes_jogo)
        destino = Path(out_dir) / "mapas" / f"{area_id}.json"
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        files[f"mapas/{area_id}.json"] = str(destino)
        indice.append({"area": area_id, "nome": nomes_rotulo[area_id], "itens_plano": sum(1 for p in doc["itens"] if p["plano"]),
                       "fogueiras": [f["id"] for f in doc["fogueiras"]], "ordem": ordem_rota(doc["nome"], rota)})
    if indice:
        destino = Path(out_dir) / "mapas" / "indice.json"
        destino.write_text(json.dumps(indice, ensure_ascii=False), encoding="utf-8")
        files["mapas/indice.json"] = str(destino)
    for alvo, mapa in atribuir:
        alvo["mapa"] = mapa
    return files
