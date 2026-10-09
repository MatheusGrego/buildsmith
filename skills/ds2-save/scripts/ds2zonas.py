"""Zonas de fogueira de uma área: cada triângulo do navmesh fica com a fogueira mais perto andando.

- Dijkstra com várias origens (todas as fogueiras ao mesmo tempo) no grafo de triângulos do navmesh.
- Ordem das zonas: distância a pé desde o início do mapa (ponto `マップ開始地点` do MSB); sem início, pelo ID.
- Contorno de cada zona por andar com a mesma grade da planta (ds2planta), para encaixar no desenho.
"""
import bisect
import heapq
from collections import defaultdict

import ds2planta

ZONAS_VERSAO = 1


def _dijkstra(vizinhos, centros, origens: dict) -> tuple[dict, dict]:
    """origens: triângulo -> rótulo. Devolve (distância, rótulo) por triângulo alcançado."""
    dist, rotulo, fila = {}, {}, []
    for t, r in origens.items():
        dist[t], rotulo[t] = 0.0, r
        heapq.heappush(fila, (0.0, t))
    while fila:
        d, t = heapq.heappop(fila)
        if d > dist[t]:
            continue
        for n in vizinhos[t]:
            nd = d + sum((centros[t][k] - centros[n][k]) ** 2 for k in range(3)) ** 0.5
            if nd < dist.get(n, float("inf")):
                dist[n], rotulo[n] = nd, rotulo[t]
                heapq.heappush(fila, (nd, n))
    return dist, rotulo


def zonas(area: dict, grafo) -> dict:
    """grafo: (centros, vizinhos) dos triângulos na ordem de ds2planta.triangulos(area)."""
    centros, vizinhos = grafo
    tris = list(ds2planta.triangulos(area))
    fogueiras = area.get("fogueiras", [])
    if not tris or not fogueiras:
        return {"versao": ZONAS_VERSAO, "ordem_por": "nenhuma", "lista": [], "triangulo": []}
    perto = lambda pos: min(range(len(centros)), key=lambda t: sum((centros[t][k] - pos[k]) ** 2 for k in range(3)))  # noqa: E731
    semente = {f["id"]: perto(f["pos"]) for f in fogueiras}
    _dist, rotulo = _dijkstra(vizinhos, centros, {t: fid for fid, t in semente.items()})
    inicio = area.get("inicio")
    if inicio:
        d_inicio, _ = _dijkstra(vizinhos, centros, {perto(inicio): 0})
        chave = lambda f: (d_inicio.get(semente[f["id"]], float("inf")), f["id"])  # noqa: E731
        ordem_por = "inicio"
    else:
        chave = lambda f: (f["id"],)  # noqa: E731
        ordem_por = "id"
    ordem = {f["id"]: i + 1 for i, f in enumerate(sorted(fogueiras, key=chave))}
    pl = area["planta"]
    x0, z0 = ds2planta.origem_grade(tris)
    grupos = defaultdict(list)
    for t, tri in enumerate(tris):
        if t in rotulo:
            andar = bisect.bisect(pl["cortes"], sum(p[1] for p in tri) / 3)
            grupos[(rotulo[t], andar)].append(tri)
    lista = []
    for f in sorted(fogueiras, key=lambda f: ordem[f["id"]]):
        poligonos = {}
        for (fid, andar), ts in grupos.items():
            if fid == f["id"]:
                polys = ds2planta.contornar(ts, x0, z0)
                if polys:
                    poligonos[str(andar)] = polys
        lista.append({"ordem": ordem[f["id"]], "fogueira": f["id"], "nome": f["nome"], "poligonos": poligonos})
    zona_do_triangulo = [ordem[rotulo[t]] if t in rotulo else None for t in range(len(tris))]
    return {"versao": ZONAS_VERSAO, "ordem_por": ordem_por, "lista": lista, "triangulo": zona_do_triangulo}
