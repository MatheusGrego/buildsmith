"""Planta limpa de uma área do DS2 a partir do navmesh: andares por altura e contorno de cada andar.

O navmesh é feito para a IA andar: triângulos de todo tamanho, pedaços com frestas entre si e andares empilhados.
Para virar mapa:
1. andares = picos do histograma de área por altura (1 m), separados no vale entre dois picos;
2. cada andar é pintado numa grade de CELULA metros, as frestas são fechadas (dilatar e erodir uma célula);
3. o contorno da grade vira polígono (borda entre célula cheia e vazia, chão à esquerda) e é simplificado
   (Douglas-Peucker) para não ficar com degraus de grade.
"""
import bisect
import math
from collections import defaultdict

PLANTA_VERSAO = 1
CELULA = 1.0
PICO_MIN = 0.01  # fração da área total para um pico de altura virar andar
PICO_DISTANCIA = 3  # metros mínimos entre dois andares
TOLERANCIA = 0.75  # metros de desvio aceitos ao simplificar o contorno
AREA_MIN = 2.0  # m²: contorno menor que isso é ruído


def triangulos(area: dict):
    for m in area.get("malhas", []):
        v, f = m["v"], m["f"]
        for i in range(0, len(f) - 2, 3):
            yield tuple((v[3 * k], v[3 * k + 1], v[3 * k + 2]) for k in (f[i], f[i + 1], f[i + 2]))


def _area_xz(t) -> float:
    (ax, _, az), (bx, _, bz), (cx, _, cz) = t
    return abs((bx - ax) * (cz - az) - (cx - ax) * (bz - az)) / 2


def _altura(t) -> float:
    return (t[0][1] + t[1][1] + t[2][1]) / 3


def detectar_andares(tris: list) -> list[float]:
    """Limites entre andares (alturas de corte, crescentes). Lista vazia = um andar só."""
    hist = defaultdict(float)
    for t in tris:
        hist[math.floor(_altura(t))] += max(_area_xz(t), 0.01)
    if not hist:
        return []
    lo, hi = min(hist), max(hist)
    arr = [hist.get(b, 0.0) for b in range(lo, hi + 1)]
    total = sum(arr)
    s = [(arr[i - 1] if i else 0) + 2 * arr[i] + (arr[i + 1] if i + 1 < len(arr) else 0) for i in range(len(arr))]
    picos = []
    for i, val in enumerate(s):
        vizinhos = s[max(0, i - 2):i + 3]
        if val >= max(vizinhos) and val / 4 >= PICO_MIN * total:
            if picos and i - picos[-1] < PICO_DISTANCIA:
                if val > s[picos[-1]]:
                    picos[-1] = i
                continue
            picos.append(i)
    cortes = []
    for a, b in zip(picos, picos[1:]):
        vale = min(range(a + 1, b), key=lambda i: s[i]) if b - a > 1 else b
        cortes.append(lo + vale + 0.5 if b - a > 1 else lo + b)
    return cortes


def _pintar(tris: list, x0: float, z0: float) -> set:
    cel = set()
    for t in tris:
        xs, zs = [p[0] for p in t], [p[2] for p in t]
        (ax, _, az), (bx, _, bz), (cx, _, cz) = t
        d = (bz - cz) * (ax - cx) + (cx - bx) * (az - cz)
        for i in range(math.floor((min(xs) - x0) / CELULA), math.floor((max(xs) - x0) / CELULA) + 1):
            for j in range(math.floor((min(zs) - z0) / CELULA), math.floor((max(zs) - z0) / CELULA) + 1):
                px, pz = x0 + (i + 0.5) * CELULA, z0 + (j + 0.5) * CELULA
                if d == 0:
                    continue
                l1 = ((bz - cz) * (px - cx) + (cx - bx) * (pz - cz)) / d
                l2 = ((cz - az) * (px - cx) + (ax - cx) * (pz - cz)) / d
                if l1 >= -1e-9 and l2 >= -1e-9 and l1 + l2 <= 1 + 1e-9:
                    cel.add((i, j))
        # triângulo fino (passarela, rampa estreita) pode não cobrir centro de célula: marca vértices e centro;
        # o vértice anda 2 cm para dentro, senão o canto na borda da célula marca a célula de fora
        gx, gz = (ax + bx + cx) / 3, (az + bz + cz) / 3
        for px, pz in ((ax, az), (bx, bz), (cx, cz), (gx, gz)):
            dx, dz = gx - px, gz - pz
            n = math.hypot(dx, dz)
            if n > 0.02:
                px, pz = px + dx / n * 0.02, pz + dz / n * 0.02
            cel.add((math.floor((px - x0) / CELULA), math.floor((pz - z0) / CELULA)))
    return cel


VIZ8 = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]


def _fechar(cel: set) -> set:
    dil = set(cel)
    for i, j in cel:
        for di, dj in VIZ8:
            dil.add((i + di, j + dj))
    return {c for c in dil if all((c[0] + di, c[1] + dj) in dil for di, dj in VIZ8)}


def _contornos(cel: set) -> list[list[tuple[int, int]]]:
    """Laços da borda da grade, com o chão à esquerda (externo anti-horário, buraco horário)."""
    saidas = defaultdict(list)
    for i, j in cel:
        if (i, j - 1) not in cel:
            saidas[(i, j)].append((i + 1, j))
        if (i + 1, j) not in cel:
            saidas[(i + 1, j)].append((i + 1, j + 1))
        if (i, j + 1) not in cel:
            saidas[(i + 1, j + 1)].append((i, j + 1))
        if (i - 1, j) not in cel:
            saidas[(i, j + 1)].append((i, j))
    lacos = []
    while saidas:
        inicio = next(iter(saidas))
        laco, atual, direcao = [inicio], inicio, None
        while True:
            opcoes = saidas[atual]
            if direcao is None or len(opcoes) == 1:
                prox = opcoes[0]
            else:  # vértice tocado por duas células na diagonal: vira à esquerda primeiro
                esq = (-direcao[1], direcao[0])
                prox = min(opcoes, key=lambda p: 0 if (p[0] - atual[0], p[1] - atual[1]) == esq
                           else 1 if (p[0] - atual[0], p[1] - atual[1]) == direcao else 2)
            opcoes.remove(prox)
            if not opcoes:
                del saidas[atual]
            direcao = (prox[0] - atual[0], prox[1] - atual[1])
            atual = prox
            if atual == inicio:
                break
            laco.append(atual)
        lacos.append(laco)
    return lacos


def _dp(pts: list, tol: float) -> list:
    if len(pts) < 3:
        return pts
    (ax, az), (bx, bz) = pts[0], pts[-1]
    dx, dz = bx - ax, bz - az
    norma = math.hypot(dx, dz) or 1e-9
    dist = [abs(dz * (px - ax) - dx * (pz - az)) / norma for px, pz in pts[1:-1]]
    k = max(range(len(dist)), key=dist.__getitem__)
    if dist[k] <= tol:
        return [pts[0], pts[-1]]
    return _dp(pts[:k + 2], tol)[:-1] + _dp(pts[k + 1:], tol)


def simplificar(laco: list, tol: float) -> list:
    if len(laco) < 4:
        return laco
    longe = max(range(len(laco)), key=lambda i: (laco[i][0] - laco[0][0]) ** 2 + (laco[i][1] - laco[0][1]) ** 2)
    a = _dp(laco[:longe + 1], tol)
    b = _dp(laco[longe:] + [laco[0]], tol)
    return a[:-1] + b[:-1]


def _area_poligono(poly: list) -> float:
    return sum(poly[i - 1][0] * poly[i][1] - poly[i][0] * poly[i - 1][1] for i in range(len(poly))) / 2


def origem_grade(tris: list) -> tuple[int, int]:
    """Canto da grade comum a todos os desenhos da área (planta e zonas ficam alinhadas)."""
    return (math.floor(min(p[0] for t in tris for p in t)) - 2, math.floor(min(p[2] for t in tris for p in t)) - 2)


def contornar(tris: list, x0: float, z0: float) -> list:
    """Polígonos simplificados do chão coberto pelos triângulos (raster, frestas fechadas, contorno)."""
    poligonos = []
    for laco in _contornos(_fechar(_pintar(tris, x0, z0))):
        mundo = [(x0 + i * CELULA, z0 + j * CELULA) for i, j in laco]
        simples = simplificar(mundo, TOLERANCIA)
        if len(simples) >= 3 and abs(_area_poligono(simples)) >= AREA_MIN:
            poligonos.append([[round(x, 1), round(z, 1)] for x, z in simples])
    return poligonos


def planta(area: dict) -> dict:
    tris = list(triangulos(area))
    cortes = detectar_andares(tris)
    grupos = defaultdict(list)
    for t in tris:
        grupos[bisect.bisect(cortes, _altura(t))].append(t)
    if not tris:
        return {"versao": PLANTA_VERSAO, "celula": CELULA, "cortes": cortes, "andares": []}
    x0, z0 = origem_grade(tris)
    andares = []
    for idx in range(len(cortes) + 1):
        ts = grupos.get(idx, [])
        if not ts:
            continue
        peso = sum(max(_area_xz(t), 0.01) for t in ts)
        altura = sum(_altura(t) * max(_area_xz(t), 0.01) for t in ts) / peso
        poligonos = contornar(ts, x0, z0)
        andares.append({"id": idx, "altura": round(altura, 1), "min": round(min(_altura(t) for t in ts), 1),
                        "max": round(max(_altura(t) for t in ts), 1), "poligonos": poligonos})
    return {"versao": PLANTA_VERSAO, "celula": CELULA, "cortes": cortes, "andares": andares}


def andar_de(pl: dict, altura: float) -> int | None:
    """Andar de um ponto pela altura (o mesmo corte usado nos triângulos)."""
    ids = [a["id"] for a in pl["andares"]]
    if not ids:
        return None
    idx = bisect.bisect(pl["cortes"], altura)
    return idx if idx in ids else min(ids, key=lambda i: abs(i - idx))
