#!/usr/bin/env python3
"""Mapa do DS2 SotFS a partir dos arquivos do jogo: chão andável (navmesh), fogueiras, itens e inimigos de uma área,
e rota pelo chão entre dois pontos.

Formatos lidos (conferidos contra a Lost Bastille, m10_16_00_00):
- MSB: listas a partir de 0x10 (versão, qtd+1, nome, offsets; o último offset é a próxima lista). Em PARTS_PARAM_ST,
  cada parte tem nome relativo em +0, tipo em +8, posição (3 floats) em +0x10; objeto tem a referência em +0xA0
  (linha da MapObjectInstanceParam ou lote da ItemLotParam2_Other). A navmesh (tipo 4) está na origem das
  coordenadas relativas dos params e do NVG2.
- Param por mapa: contagem u16 em 0x0A, linhas de 24 bytes (id, offset, nome) a partir de 0x40; fim = u32 em 0x00.
- NVG2: malhas em 0x08; em 0x20 vêm malhas+4 offsets (4 seções de ligação e as malhas); malha: vértices em +0x28,
  faces em +0x2C, offsets de vértices/atributos/faces em +0x40; face = 3 índices no começo de 12 bytes.
- FMG (texto do jogo): grupos em 0x0C, textos em 0x10, tabela de offsets em 0x14; grupo = (índice, primeiro, último).
"""
import argparse
from collections import defaultdict
import json
import os
import re
import struct
import sys
from pathlib import Path

from ds2planta import PLANTA_VERSAO  # noqa: F401 (versão da planta guardada no cache)

AREA = re.compile(r"^m(\d\d)_(\d\d)_(\d\d)_(\d\d)$")
EXTRACAO_VERSAO = 3  # 2: NPCs e chefes; 3: início do mapa (zonas); muda quando o que sai do jogo muda
INICIO_MAPA = "マップ開始地点"  # nome do ponto de início no MSB (texto do próprio jogo)
JUNTAR_NPC = 15.0  # metros: geradores do mesmo NPC mais perto que isso viram um marcador só
TIPO_NAVMESH, TIPO_COLISAO, TIPO_OBJETO = 4, 3, 1


class MapaError(Exception):
    pass


def _wstr(data: bytes, off: int) -> str:
    end = off
    while data[end:end + 2] != b"\0\0":
        end += 2
    return data[off:end].decode("utf-16-le", errors="replace")


def _listas_msb(data: bytes) -> dict[str, list[int]]:
    if data[:4] != b"MSB ":
        raise MapaError("MSB em formato inesperado")
    listas, off, vistos = {}, 0x10, set()
    while off and off not in vistos:
        vistos.add(off)
        _versao, count = struct.unpack_from("<ii", data, off)
        nome = _wstr(data, struct.unpack_from("<q", data, off + 8)[0])
        offsets = struct.unpack_from(f"<{count}q", data, off + 16)
        listas[nome] = list(offsets[:-1])
        off = offsets[-1]
    return listas


def partes_msb(data: bytes) -> list[dict]:
    out = []
    for e in _listas_msb(data).get("PARTS_PARAM_ST", []):
        nome = _wstr(data, e + struct.unpack_from("<q", data, e)[0])
        tipo = struct.unpack_from("<H", data, e + 8)[0]
        pos = struct.unpack_from("<3f", data, e + 0x10)
        ref = struct.unpack_from("<I", data, e + 0xA0)[0] if tipo == TIPO_OBJETO else 0
        out.append({"nome": nome, "tipo": tipo, "pos": pos, "ref": ref})
    return out


def pontos_msb(data: bytes) -> list[dict]:
    """Regiões/pontos do MSB (POINT_PARAM_ST): nome e posição (+0x10, como nas partes)."""
    out = []
    for e in _listas_msb(data).get("POINT_PARAM_ST", []):
        nome = _wstr(data, e + struct.unpack_from("<q", data, e)[0])
        out.append({"nome": nome, "pos": struct.unpack_from("<3f", data, e + 0x10)})
    return out


def origem(partes: list[dict]) -> tuple[float, float, float]:
    """Posição da navmesh (ou da colisão) no MSB: a origem das coordenadas relativas da área."""
    for tipo in (TIPO_NAVMESH, TIPO_COLISAO):
        for p in partes:
            if p["tipo"] == tipo:
                return tuple(p["pos"])
    return (0.0, 0.0, 0.0)


def linhas_param(data: bytes) -> list[tuple[int, bytes]]:
    count = struct.unpack_from("<H", data, 0x0A)[0]
    entradas = [struct.unpack_from("<QQQ", data, 0x40 + 24 * i) for i in range(count)]
    fim_total = struct.unpack_from("<I", data, 0)[0]
    out = []
    for i, (rid, off, _nome) in enumerate(entradas):
        fim = entradas[i + 1][1] if i + 1 < count else (fim_total if fim_total > off else len(data))
        out.append((rid, data[off:fim]))
    return out


def malhas_nvg2(data: bytes, base: tuple) -> list[dict]:
    if data[:4] != b"NVG2":
        raise MapaError("navmesh em formato inesperado")
    n = struct.unpack_from("<i", data, 0x08)[0]
    offsets = struct.unpack_from(f"<{n + 4}q", data, 0x20)
    malhas = []
    for o in offsets[4:]:
        vcount = struct.unpack_from("<I", data, o + 0x28)[0]
        fcount = struct.unpack_from("<H", data, o + 0x2C)[0]
        voff, _aoff, foff = struct.unpack_from("<qqq", data, o + 0x40)
        verts = [tuple(c + base[k] for k, c in enumerate(struct.unpack_from("<3f", data, voff + 12 * i))) for i in range(vcount)]
        faces = [struct.unpack_from("<3H", data, foff + 12 * i) for i in range(fcount)]
        if any(max(f) >= vcount for f in faces):
            raise MapaError("navmesh com índice de vértice inválido")
        malhas.append({"v": verts, "f": faces})
    return malhas


def textos_fmg(data: bytes) -> dict[int, str]:
    grupos, textos, str_off = struct.unpack_from("<iii", data, 0x0C)
    offs = struct.unpack_from(f"<{textos}i", data, str_off)
    out = {}
    for g in range(grupos):
        idx, primeiro, ultimo = struct.unpack_from("<iii", data, 0x1C + 12 * g)
        for k, i in enumerate(range(primeiro, ultimo + 1)):
            o = offs[idx + k]
            if o:
                out[i] = _wstr(data, o)
    return out


def nome_mapa_id(area: str) -> int:
    """ID do nome da área em mapname.fmg: m10_16_00_00 -> 10160000."""
    m = AREA.match(area)
    if not m:
        raise ValueError(f"área inválida: {area!r}")
    return int(m.group(1)) * 1_000_000 + int(m.group(2)) * 10_000


def com_planta(area: dict) -> dict:
    """Garante a planta limpa (andares e contornos, ds2planta) e o andar de cada ponto; não refaz a mesma versão."""
    import ds2planta

    if area.get("planta", {}).get("versao") == ds2planta.PLANTA_VERSAO:
        return area
    pl = ds2planta.planta(area)
    area["planta"] = pl
    for lista in ("fogueiras", "itens", "inimigos", "npcs", "chefes"):
        for p in area.get(lista, []):
            p["andar"] = ds2planta.andar_de(pl, p["pos"][1])
    return area


def montar_atores(locais: dict, personagens: dict, base: tuple, nomes_npc: dict, chefes_mapa: list) -> tuple[list, list]:
    """NPCs (personagem // 10000 com nome no npcmenu.fmg) e chefes (família do personagem listada no BossBattleParam).

    locais: gerador -> posição relativa; personagens: gerador -> ID do personagem (generatorparam +8).
    """
    absoluto = {g: tuple(c + base[k] for k, c in enumerate(rel)) for g, rel in locais.items()}
    npcs = []
    for g in sorted(absoluto):
        npc = personagens.get(g, 0) // 10000
        if npc not in nomes_npc:
            continue
        pos = absoluto[g]
        if any(n["id"] == npc and _dist(n["pos"], pos) < JUNTAR_NPC for n in npcs):
            continue
        npcs.append({"id": npc, "nome": nomes_npc[npc], "pos": _r(pos)})
    chefes = []
    for c in chefes_mapa:
        familias = {f // 10 for f in c["familias"] if f}
        pts = [absoluto[g] for g in sorted(absoluto) if personagens.get(g, 0) // 100000 in familias]
        if not pts:
            continue
        media = tuple(sum(p[k] for p in pts) / len(pts) for k in range(3))
        chefes.append({"flag": c["flag"], "nome": c["nome"], "wiki": c.get("wiki", ""), "pos": _r(media)})
    return npcs, chefes


def chefes_do_mapa(boss_param: bytes, area: str, bosses: list) -> list:
    """Linhas do BossBattleParam desta área (id // 1000 = AABB): flag em +20, personagens em +44/+48/+52."""
    m = AREA.match(area)
    chave = int(m.group(1)) * 100 + int(m.group(2))
    por_flag = {b["flag"]: b for b in bosses}
    out = []
    for rid, raw in linhas_param(boss_param):
        if rid // 1000 != chave or len(raw) < 56:
            continue
        flag = struct.unpack_from("<i", raw, 20)[0]
        if flag in por_flag:
            out.append({"flag": flag, "nome": por_flag[flag]["nome"], "wiki": por_flag[flag].get("wiki", ""),
                        "familias": list(struct.unpack_from("<3i", raw, 44))})
    return out


def com_zonas(area: dict) -> dict:
    """Garante as zonas de fogueira (ds2zonas) e a zona de cada ponto; não refaz a mesma versão."""
    import ds2zonas

    area = com_planta(area)
    if area.get("zonas", {}).get("versao") == ds2zonas.ZONAS_VERSAO:
        return area
    grafo = _grafo(area)
    z = ds2zonas.zonas(area, grafo)
    tri_zona = z.pop("triangulo")
    area["zonas"] = z
    centros = grafo[0]
    baldes = defaultdict(list)  # centróides por quadrado de 8 m, para achar o triângulo mais perto sem varrer todos
    for t, c in enumerate(centros):
        baldes[(int(c[0] // 8), int(c[2] // 8))].append(t)

    def zona_de(pos):
        if not tri_zona:  # área sem fogueira: sem zonas
            return None
        bx, bz = int(pos[0] // 8), int(pos[2] // 8)
        for raio in (1, 3, 8):
            cand = [t for dx in range(-raio, raio + 1) for dz in range(-raio, raio + 1) for t in baldes.get((bx + dx, bz + dz), [])]
            if cand:
                return tri_zona[min(cand, key=lambda t: _dist(centros[t], pos))]
        return None

    for lista in ("fogueiras", "itens", "inimigos", "npcs", "chefes"):
        for p in area.get(lista, []):
            p["zona"] = zona_de(p["pos"])
    return area


def lotes_itens(data: bytes) -> dict[int, list[tuple[int, int]]]:
    """ItemLotParam2_Other: quantidades (10 bytes) em +0x04 e IDs (10 int) em +0x2C; ID <= 10 = vazio."""
    out = {}
    for rid, raw in linhas_param(data):
        if len(raw) < 0x54:
            continue
        ids = struct.unpack_from("<10i", raw, 0x2C)
        out[rid] = [(ids[k], raw[0x04 + k]) for k in range(10) if ids[k] > 10 and raw[0x04 + k]]
    return out


def _r(v) -> list[float]:
    return [round(float(c), 1) + 0.0 for c in v]


def montar_area(area: str, nome: str, partes: list[dict], instancias: dict, nomes_fogueira: dict, lotes: dict,
                nomes_itens: dict, malhas: list[dict], geradores: list, assinatura: str) -> dict:
    """Junta o que veio dos arquivos numa área: objeto que aponta para fogueira vira fogueira, para lote com item
    vira ponto de item; geradores (inimigos/NPCs) vêm em coordenada relativa à origem."""
    base = origem(partes)
    fogueiras, itens = [], []
    for p in partes:
        if p["tipo"] != TIPO_OBJETO or not p["ref"]:
            continue
        fog = instancias.get(p["ref"])
        if fog in nomes_fogueira:
            fogueiras.append({"id": fog, "nome": nomes_fogueira[fog], "pos": _r(p["pos"])})
        elif lotes.get(p["ref"]):
            itens.append({"lote": p["ref"], "pos": _r(p["pos"]),
                          "itens": [{"id": i, "nome": nomes_itens.get(i, f"#{i}"), "qtd": q} for i, q in lotes[p["ref"]]]})
    inimigos = [{"id": gid, "pos": _r(c + base[k] for k, c in enumerate(rel))} for gid, rel in geradores]
    return {
        "area": area, "nome": nome, "assinatura": assinatura, "origem": _r(base),
        "malhas": [{"v": [c for v in m["v"] for c in _r(v)], "f": [i for f in m["f"] for i in f]} for m in malhas],
        "fogueiras": fogueiras, "itens": itens, "inimigos": inimigos,
    }


def _texto(arq, nome: str) -> dict[int, str]:
    return textos_fmg(arq.ler(f"/menu/text/english/{nome}.fmg"))


def extrair_area(game_dir, area: str, cache_dir, names=None) -> dict:
    """Extrai uma área para <cache>/mapas/<area>.json (reaproveita se os arquivos do jogo não mudaram)."""
    import ds2arquivos
    import ds2regulation
    import ds2save

    nome_mapa_id(area)  # valida o nome antes de virar caminho
    destino = Path(cache_dir) / "mapas" / f"{area}.json"
    assinatura = ds2arquivos.assinatura(game_dir)
    if destino.is_file():
        try:
            pronto = json.loads(destino.read_text(encoding="utf-8"))
            if pronto.get("assinatura") == assinatura and pronto.get("versao_extracao") == EXTRACAO_VERSAO:
                import ds2zonas

                if (pronto.get("planta", {}).get("versao") == PLANTA_VERSAO
                        and pronto.get("zonas", {}).get("versao") == ds2zonas.ZONAS_VERSAO):
                    return pronto
                return _gravar(destino, com_zonas(pronto))
        except ValueError:
            pass
    arq = ds2arquivos.Arquivo(game_dir, "GameData")
    partes = partes_msb(arq.ler(f"/map/{area}/{area}.msb"))
    base = origem(partes)
    malhas = malhas_nvg2(arq.ler(f"/map/{area}/{area}.ngp"), base) if arq.tem(f"/map/{area}/{area}.ngp") else []
    inst_path = f"/param/mapobjectinstanceparam_{area}.param"
    instancias = {rid: struct.unpack_from("<i", raw)[0] for rid, raw in linhas_param(arq.ler(inst_path)) if len(raw) >= 4} if arq.tem(inst_path) else {}
    ger_path = f"/param/generatorlocation_{area}.param"
    geradores = [(rid, struct.unpack_from("<3f", raw)) for rid, raw in linhas_param(arq.ler(ger_path)) if len(raw) >= 12] if arq.tem(ger_path) else []
    lotes = lotes_itens(ds2regulation.load_params(ds2regulation.find_regulation(game_dir))["ItemLotParam2_Other"])  # noqa: E501
    names = names if names is not None else ds2save.load_item_names()
    nomes_itens = {i: n for i, (_cat, n) in names.items()}
    nome = _texto(arq, "mapname").get(nome_mapa_id(area), area)
    out = montar_area(area, nome, partes, instancias, _texto(arq, "bonfirename"), lotes, nomes_itens, malhas, geradores, assinatura)
    gen_path = f"/param/generatorparam_{area}.param"
    personagens = {rid: struct.unpack_from("<i", raw, 8)[0] for rid, raw in linhas_param(arq.ler(gen_path)) if len(raw) >= 12} if arq.tem(gen_path) else {}
    bosses = json.loads((ds2save.GAME_DIR / "bosses.json").read_text(encoding="utf-8"))["chefes"]
    params = ds2regulation.load_params(ds2regulation.find_regulation(game_dir))
    out["npcs"], out["chefes"] = montar_atores(dict(geradores), personagens, base, _texto(arq, "npcmenu"),
                                               chefes_do_mapa(params["BossBattleParam"], area, bosses))
    inicio = [q["pos"] for q in pontos_msb(arq.ler(f"/map/{area}/{area}.msb")) if q["nome"] == INICIO_MAPA]
    out["inicio"] = _r(inicio[0]) if inicio else None
    out["versao_extracao"] = EXTRACAO_VERSAO
    return _gravar(destino, com_zonas(out))


def _gravar(destino: Path, dados: dict) -> dict:
    destino.parent.mkdir(parents=True, exist_ok=True)
    tmp = destino.with_suffix(".tmp")
    tmp.write_text(json.dumps(dados, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    os.replace(tmp, destino)
    return dados


def areas(game_dir) -> list[dict]:
    """Áreas com mapa e navmesh no jogo, com o nome do próprio jogo (mapname.fmg)."""
    import ds2arquivos

    arq = ds2arquivos.Arquivo(game_dir, "GameData")
    out = []
    for mid, nome in sorted(_texto(arq, "mapname").items()):
        if mid % 10_000:
            continue
        area = f"m{mid // 1_000_000:02d}_{mid // 10_000 % 100:02d}_00_00"
        if arq.tem(f"/map/{area}/{area}.msb") and arq.tem(f"/map/{area}/{area}.ngp") and all(a["area"] != area for a in out):
            out.append({"area": area, "nome": nome})
    return out


def onde(game_dir, cache_dir, item: str, areas_filtro=None) -> list[dict]:
    """Todos os pontos do jogo com o item (nome sem diferença de maiúscula)."""
    alvo = item.strip().casefold()
    lista = areas_filtro or [a["area"] for a in areas(game_dir)]
    out = []
    for area in lista:
        dados = extrair_area(game_dir, area, cache_dir)
        for p in dados["itens"]:
            if any(i["nome"].casefold() == alvo for i in p["itens"]):
                out.append({"area": area, "nome_area": dados["nome"], "lote": p["lote"], "pos": p["pos"], "itens": p["itens"]})
    return out


TIPOS_PONTO = {"fogueira": ("fogueiras", "id"), "item": ("itens", "lote"), "inimigo": ("inimigos", "id")}


def ponto_de(area: dict, tipo: str, ref: int) -> list[float]:
    """Posição de um ponto da área: fogueira pelo ID do jogo, item pelo lote, inimigo pelo gerador."""
    if tipo not in TIPOS_PONTO:
        raise KeyError(f"tipo de ponto desconhecido: {tipo}")
    lista, chave = TIPOS_PONTO[tipo]
    for p in area[lista]:
        if p[chave] == ref:
            return list(p["pos"])
    raise KeyError(f"ponto {tipo}:{ref} não existe em {area.get('area')}")


def _grafo(area: dict):
    """Triângulos da área (centróides) e vizinhos por aresta compartilhada, inclusive entre malhas."""
    centros, vizinhos, arestas = [], [], {}
    for m in area["malhas"]:
        v, f = m["v"], m["f"]
        pts = [tuple(v[i:i + 3]) for i in range(0, len(v), 3)]
        for i in range(0, len(f), 3):
            a, b, c = pts[f[i]], pts[f[i + 1]], pts[f[i + 2]]
            t = len(centros)
            centros.append(tuple((a[k] + b[k] + c[k]) / 3 for k in range(3)))
            vizinhos.append(set())
            for u, w in ((a, b), (b, c), (c, a)):
                key = (u, w) if u <= w else (w, u)
                for outro in arestas.setdefault(key, []):
                    vizinhos[t].add(outro)
                    vizinhos[outro].add(t)
                arestas[key].append(t)
    return centros, vizinhos


def _dist(a, b) -> float:
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2) ** 0.5


def rota(area: dict, de, ate) -> dict | None:
    """Caminho mais curto pelo chão (centróides dos triângulos) de um ponto a outro; None se não há caminho."""
    import heapq

    centros, vizinhos = _grafo(area)
    if not centros:
        return None
    perto = lambda p: min(range(len(centros)), key=lambda t: _dist(centros[t], p))  # noqa: E731
    s, g = perto(de), perto(ate)
    custo, anterior, fila = {s: 0.0}, {s: None}, [(0.0, s)]
    while fila:
        c, t = heapq.heappop(fila)
        if t == g:
            break
        if c > custo[t]:
            continue
        for n in vizinhos[t]:
            nc = c + _dist(centros[t], centros[n])
            if nc < custo.get(n, float("inf")):
                custo[n], anterior[n] = nc, t
                heapq.heappush(fila, (nc, n))
    if g not in anterior:
        return None
    caminho, t = [], g
    while t is not None:
        caminho.append(_r(centros[t]))
        t = anterior[t]
    pontos = [list(de)] + caminho[::-1] + [list(ate)]
    metros = sum(_dist(pontos[i], pontos[i + 1]) for i in range(len(pontos) - 1))
    return {"pontos": pontos, "metros": round(metros, 1)}


def _ponto_cli(texto: str) -> tuple[str, int]:
    tipo, _, ref = texto.partition(":")
    if tipo not in TIPOS_PONTO or not ref.isdigit():
        raise ValueError(f"ponto inválido: {texto!r} (use fogueira:<id>, item:<lote> ou inimigo:<id>)")
    return tipo, int(ref)


def _cache_padrao() -> Path:
    return Path(os.environ.get("BUILDSMITH_HOME", Path.home() / ".buildsmith")) / "cache" / "ds2"


def main(argv=None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    import ds2arquivos

    parser = argparse.ArgumentParser(prog="ds2mapa")
    sub = parser.add_subparsers(dest="cmd", required=True)
    for nome in ("areas", "extrair", "onde", "rota"):
        p = sub.add_parser(nome)
        p.add_argument("--game", help="pasta Game do DS2 (padrão: a instalação da Steam)")
        p.add_argument("--cache", help="pasta do cache (padrão: ~/.buildsmith/cache/ds2)")
    sub.choices["extrair"].add_argument("--area", required=True)
    sub.choices["onde"].add_argument("--item", required=True)
    sub.choices["onde"].add_argument("--area", action="append", help="limita a busca (pode repetir)")
    sub.choices["rota"].add_argument("--area", required=True)
    sub.choices["rota"].add_argument("--de", required=True, help="fogueira:<id>, item:<lote> ou inimigo:<id>")
    sub.choices["rota"].add_argument("--ate", required=True)
    args = parser.parse_args(argv)
    game = Path(args.game) if args.game else ds2arquivos.game_dir_padrao()
    cache = Path(args.cache) if args.cache else _cache_padrao()
    try:
        if game is None:
            raise MapaError("DS2 SotFS não encontrado; defina BUILDSMITH_DS2_GAME com a pasta Game")
        if args.cmd == "areas":
            out = areas(game)
        elif args.cmd == "extrair":
            dados = extrair_area(game, args.area, cache)
            out = {"area": dados["area"], "nome": dados["nome"], "fogueiras": len(dados["fogueiras"]), "itens": len(dados["itens"]),
                   "inimigos": len(dados["inimigos"]), "malhas": len(dados["malhas"]), "cache": str(cache / "mapas" / f"{args.area}.json")}
        elif args.cmd == "rota":
            dados = extrair_area(game, args.area, cache)
            de, ate = (ponto_de(dados, *_ponto_cli(x)) for x in (args.de, args.ate))
            out = rota(dados, de, ate)
            if out is None:
                raise MapaError("sem caminho pelo chão entre os dois pontos")
        else:
            out = onde(game, cache, args.item, args.area)
    except (MapaError, ds2arquivos.ArquivoError, ValueError, OSError, KeyError) as err:
        print(json.dumps({"error": str(err)}, ensure_ascii=False))
        return 1
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
