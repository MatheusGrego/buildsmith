#!/usr/bin/env python3
"""Índice de itens do DS2 SotFS: categoria, requisitos e todas as fontes que as tabelas do jogo dão, sem IA.

Por item das listas de games/ds2/ids/*: nome, categoria, requisitos (WeaponParam, SpellParam), ícone (só do cache da
wiki, sem rede) e as fontes:
- compra: ShopLineupParam sem material (preço, estoque) com o NPC de lojas.json e as áreas onde o NPC aparece no mapa.
  O prefixo da linha da loja (linha // 10000) é o ID do NPC no npcmenu.fmg e nos geradores do mapa: conferido em 21
  lojas (McDuff 7643 na Lost Bastille, Straid 7680, Chloanne 7620 em Majula...); variante de ID (Agdayne 5065, Vengarl
  3071) casa pelo nome.
- troca: ShopLineupParam com material (alma de chefe) e o chefe que dá a alma.
- chao: lote de item no chão, baú ou cadáver de cada mapa (ds2mapa).
- drop: lotes de drop do EnemyParam (+0x4C e +0x134, ItemLotParam2_Chr) dos inimigos comuns de cada mapa, com quantos
  (variantes do mesmo inimigo na área juntas).
- recompensa: lote do BossBattleParam em +0x08 (ItemLotParam2_Other); a flag do chefe está em +0x14. Conferido em 30+
  chefes: The Pursuer 318000 = Soul of the Pursuer, The Last Giant 309600, Lud & Zallen 679010 = as duas almas.

Cache em ~/.buildsmith/cache/ds2/itens.json (versão + assinatura do jogo; gravação atômica).

  python ds2itens.py montar            refaz (ou reaproveita) o índice e diz quantos itens e fontes
  python ds2itens.py item --item X     o item com todas as fontes
"""
import argparse
import json
import os
import struct
import sys
from collections import defaultdict
from pathlib import Path

INDICE_VERSAO = 2  # 2: drops do mesmo inimigo na mesma área juntos (tipos_inimigo)
CATEGORIA_ARQUIVO = {"MeleeWeapons": "arma", "RangedWeapons": "arma", "Shields": "escudo", "SpellTools": "catalisador",
                     "Armor": "armadura", "Rings": "anel", "Ammo": "municao", "Consumeables": "consumivel",
                     "UseableItems": "consumivel", "UpgradeMaterials": "material", "KeyItems": "chave"}
# Escola do feitiço pelo prefixo do ID (ID // 1.000.000), conferido na wiki: 31 = feitiço (Soul Arrow, Soul Spear),
# 32 = milagre (Heal, Lightning Spear), 33 = piromancia (Fireball, Poison Mist), 34 e 35 = hex (Dark Orb, Dark Hail;
# Resonant Soul, Scraps of Life).
ESCOLA = {31: "feitico", 32: "milagre", 33: "piromancia", 34: "hex", 35: "hex"}
BB_LOTE, BB_FLAG = 0x08, 0x14  # BossBattleParam
STATS_REQ = (("STR", "req_str"), ("DEX", "req_dex"), ("INT", "req_int"), ("FTH", "req_fth"))


def categoria(arquivo: str, item_id: int, nome: str) -> str:
    if arquivo == "Spells":
        return ESCOLA.get(item_id // 1_000_000, "feitico")
    if arquivo == "MeleeWeapons" and nome.endswith("Pyromancy Flame"):  # a chama é arma no jogo, mas conjura
        return "catalisador"
    return CATEGORIA_ARQUIVO.get(arquivo, "outro")


def _norm(area: str) -> str:
    return area.lower().replace("the ", "").replace("-", " ").strip()


def ordem_rota(nome: str, rota: dict) -> int:
    """Posição da área na rota de progressão da wiki (games/ds2/rota.json): hubs = -1, fora da rota = 100."""
    if any(_norm(nome) == _norm(h) for h in rota["hubs"]):
        return -1
    lista = [_norm(a) for a in rota["rota"]]
    return lista.index(_norm(nome)) if _norm(nome) in lista else 100


def recompensas_chefes(boss_param: bytes, lotes_other: dict) -> dict[int, dict]:
    """flag do chefe -> mapa (linha // 1000 = AABB), lote da recompensa e os itens dele."""
    import ds2mapa

    out = {}
    for rid, raw in ds2mapa.linhas_param(boss_param):
        if len(raw) < BB_FLAG + 4:
            continue
        lote, flag = struct.unpack_from("<i", raw, BB_LOTE)[0], struct.unpack_from("<i", raw, BB_FLAG)[0]
        itens = [i for i, _q in lotes_other.get(lote, [])]
        if flag and itens and flag not in out:
            out[flag] = {"mapa": f"m{rid // 100000:02d}_{rid // 1000 % 100:02d}_00_00", "lote": lote, "itens": itens}
    return out


def drops_por_tipo(enemy_param: bytes, lotes_chr: dict, tipos) -> dict[int, list[int]]:
    """Linha do EnemyParam -> itens dos dois lotes de drop dela (sem repetir, na ordem dos lotes)."""
    import ds2mapa

    linhas = dict(ds2mapa.linhas_param(enemy_param))
    out = {}
    for tipo in sorted(set(tipos)):
        raw = linhas.get(tipo)
        if raw is None or len(raw) < max(ds2mapa.EP_LOTES) + 4:
            continue
        itens = []
        for off in ds2mapa.EP_LOTES:
            for item_id, _qtd in lotes_chr.get(struct.unpack_from("<i", raw, off)[0], []):
                if item_id not in itens:
                    itens.append(item_id)
        if itens:
            out[tipo] = itens
    return out


def _areas_do_npc(areas: list[dict]) -> tuple[dict, dict]:
    por_id, por_nome = defaultdict(list), defaultdict(list)
    for a in areas:
        for n in a.get("npcs", []):
            for lista, chave in ((por_id, n["id"]), (por_nome, n["nome"].casefold())):
                if a["area"] not in lista[chave]:
                    lista[chave].append(a["area"])
    return por_id, por_nome


def montar(names: dict, data, areas: list[dict], drops: dict[int, list[int]], chefes: list[dict], spells=None,
           icones=None, nome_inimigo=None, rota=None) -> dict:
    """Índice a partir do que já foi lido do jogo (testável sem o jogo).

    data: ds2data.Data (lojas, trocas, armas); areas: saídas do ds2mapa.extrair_area; drops: tipo de inimigo -> itens;
    chefes: bosses.json com "mapa" e "itens" (recompensa); spells: SpellParam (req_int, req_fth); icones: cache da wiki
    (nome em minúsculas -> {"url"})."""
    if nome_inimigo is None:
        import ds2nomes

        nome_inimigo = ds2nomes.nome_inimigo
    if rota is None:
        import ds2save

        rota = json.loads((ds2save.GAME_DIR / "rota.json").read_text(encoding="utf-8"))
    spells, icones = spells or {}, icones or {}
    fontes = defaultdict(list)
    npc_id, npc_nome = _areas_do_npc(areas)

    def areas_npc(linha: int, nome: str | None) -> list[str]:
        vistas = list(npc_id.get(linha // 10000, []))
        return vistas + [a for a in npc_nome.get((nome or "").casefold(), []) if a not in vistas]

    vendidos = {row["item_id"] for row in data.shop.values() if row["material_id"] == 0}
    for item_id in sorted(vendidos):
        for loja in data.shops_for(item_id):
            fontes[item_id].append({"tipo": "compra", "npc": loja["loja"], "linha": loja["linha"], "preco": loja["preco"],
                                    "estoque": loja["estoque"], "areas": areas_npc(loja["linha"], loja["loja"])})
    chefe_da_alma = {i: c for c in chefes for i in c.get("itens", [])}
    for t in data.trades():
        c = chefe_da_alma.get(t["alma_id"])
        fontes[t["item_id"]].append({
            "tipo": "troca", "npc": t["npc"], "linha": t["linha"], "preco": t["preco"], "alma_id": t["alma_id"],
            "alma": names[t["alma_id"]][1] if t["alma_id"] in names else f"#{t['alma_id']}",
            "chefe": {"flag": c["flag"], "nome": c["nome"], "area": c["mapa"]} if c else None,
            "areas": areas_npc(t["linha"], t["npc"])})
    for a in areas:
        for p in a.get("itens", []):
            for it in p["itens"]:
                fontes[it["id"]].append({"tipo": "chao", "area": a["area"], "lote": p["lote"], "pos": p["pos"],
                                         "no": p.get("no"), "qtd": it["qtd"], "estado_ref": p.get("estado_ref")})
        contagem = defaultdict(int)
        for e in a.get("inimigos", []):
            if e.get("tipo") and not e.get("papel"):
                contagem[e["tipo"]] += 1
        juntos = {}  # o mesmo inimigo em linhas diferentes do EnemyParam (variantes) vira uma fonte só por área
        for tipo, quantos in sorted(contagem.items()):
            nome = (nome_inimigo(tipo) or {}).get("nome")
            for item_id in drops.get(tipo, []):
                if (item_id, nome or tipo) in juntos:
                    junto = juntos[(item_id, nome or tipo)]
                    junto["quantos"] += quantos
                    junto["tipos_inimigo"].append(tipo)
                    continue
                junto = {"tipo": "drop", "area": a["area"], "inimigo": nome, "tipo_inimigo": tipo, "tipos_inimigo": [tipo],
                         "quantos": quantos}
                juntos[(item_id, nome or tipo)] = junto
                fontes[item_id].append(junto)
    for c in chefes:
        for item_id in c.get("itens", []):
            fontes[item_id].append({"tipo": "recompensa", "chefe": c["nome"], "flag": c["flag"], "area": c["mapa"]})

    itens = {}
    for item_id, (arquivo, nome) in names.items():
        req = {}
        if item_id in data.weapons:
            req = {k: data.weapons[item_id][campo] for k, campo in STATS_REQ if data.weapons[item_id][campo]}
        elif item_id in spells:
            req = {k: spells[item_id][campo] for k, campo in (("INT", "req_int"), ("FTH", "req_fth")) if spells[item_id][campo]}
        icone = (icones.get(nome.casefold()) or {}).get("url")
        itens[str(item_id)] = {"id": item_id, "nome": nome, "cat": categoria(arquivo, item_id, nome), "arquivo": arquivo,
                               "req": req, **({"icone": icone} if icone else {}), "fontes": fontes.get(item_id, [])}
    return {"itens": itens,
            "areas": {a["area"]: {"nome": a["nome"], "fogueiras": [f["id"] for f in a.get("fogueiras", [])],
                                  "ordem": ordem_rota(a["nome"], rota)} for a in areas}}


def assinatura_jogo(game_dir) -> str:
    """Índices do jogo (ds2arquivos) + o regulation (lojas, lotes, inimigos): muda quando o jogo atualiza."""
    import ds2arquivos

    reg = Path(game_dir) / "enc_regulation.bnd.dcx"
    st = reg.stat() if reg.is_file() else None
    return ds2arquivos.assinatura(game_dir) + (f"|regulation:{st.st_size}:{int(st.st_mtime)}" if st else "")


def montar_do_jogo(game_dir, cache_dir) -> dict:
    """Lê o jogo instalado (mapas pelo cache do ds2mapa) e monta o índice."""
    import ds2data
    import ds2mapa
    import ds2regulation
    import ds2save

    names = ds2save.load_item_names()
    params = ds2regulation.load_params(ds2regulation.find_regulation(game_dir))
    data = ds2data.Data(params)
    areas = [ds2mapa.extrair_area(game_dir, a["area"], cache_dir, names) for a in ds2mapa.areas(game_dir)]
    tipos = [e["tipo"] for a in areas for e in a.get("inimigos", []) if e.get("tipo") and not e.get("papel")]
    drops = drops_por_tipo(params["EnemyParam"], ds2mapa.lotes_itens(params["ItemLotParam2_Chr"]), tipos)
    rec = recompensas_chefes(params["BossBattleParam"], ds2mapa.lotes_itens(params["ItemLotParam2_Other"]))
    bosses = json.loads((ds2save.GAME_DIR / "bosses.json").read_text(encoding="utf-8"))["chefes"]
    chefes = [{**b, "mapa": rec[b["flag"]]["mapa"], "itens": rec[b["flag"]]["itens"]} for b in bosses if b["flag"] in rec]
    spells = ds2regulation.param_rows(params["SpellParam"], ds2regulation.LAYOUTS["SpellParam"]) if "SpellParam" in params else {}
    try:
        icones = json.loads((Path(cache_dir) / "icones.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        icones = {}
    return montar(names, data, areas, drops, chefes, spells, icones if isinstance(icones, dict) else {})


def _gravar(destino: Path, dados: dict) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    tmp = destino.with_suffix(".tmp")
    tmp.write_text(json.dumps(dados, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    os.replace(tmp, destino)


def carregar(game_dir, cache_dir, montar_jogo=None, destino=None, forcar: bool = False) -> dict:
    """Índice do cache se a versão e a assinatura do jogo batem; senão monta de novo e grava (atômico)."""
    destino = Path(destino) if destino else Path(cache_dir) / "itens.json"
    assinatura = assinatura_jogo(game_dir)
    if not forcar and destino.is_file():
        try:
            pronto = json.loads(destino.read_text(encoding="utf-8"))
            if pronto.get("versao") == INDICE_VERSAO and pronto.get("assinatura") == assinatura:
                return pronto
        except ValueError:
            pass
    dados = {"versao": INDICE_VERSAO, "assinatura": assinatura, **(montar_jogo or montar_do_jogo)(game_dir, cache_dir)}
    _gravar(destino, dados)
    return dados


def achar(indice: dict, valor: str) -> dict | None:
    """Item pelo ID ou pelo nome (sem diferença de maiúscula)."""
    if valor.strip().isdigit():
        return indice["itens"].get(valor.strip())
    alvo = valor.strip().casefold()
    return next((i for i in indice["itens"].values() if i["nome"].casefold() == alvo), None)


def main(argv=None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    import ds2arquivos
    import ds2mapa
    from ds2save import SaveError

    parser = argparse.ArgumentParser(prog="ds2itens")
    sub = parser.add_subparsers(dest="cmd", required=True)
    for nome in ("montar", "item"):
        p = sub.add_parser(nome)
        p.add_argument("--game", help="pasta Game do DS2 (padrão: a instalação da Steam)")
        p.add_argument("--cache", help="pasta do cache (padrão: ~/.buildsmith/cache/ds2)")
    sub.choices["montar"].add_argument("--forcar", action="store_true", help="refaz mesmo com o cache em dia")
    sub.choices["item"].add_argument("--item", required=True, help="nome ou ID do item")
    args = parser.parse_args(argv)
    game = Path(args.game) if args.game else ds2arquivos.game_dir_padrao()
    cache = Path(args.cache) if args.cache else ds2mapa._cache_padrao()
    try:
        if game is None:
            raise ds2mapa.MapaError("DS2 SotFS não encontrado; defina BUILDSMITH_DS2_GAME com a pasta Game")
        indice = carregar(game, cache, forcar=getattr(args, "forcar", False))
        if args.cmd == "montar":
            out = {"itens": len(indice["itens"]), "fontes": sum(len(i["fontes"]) for i in indice["itens"].values()),
                   "areas": len(indice["areas"]), "cache": str(cache / "itens.json")}
        else:
            out = achar(indice, args.item)
            if out is None:
                raise ds2mapa.MapaError(f"item '{args.item}' não está nas listas de itens")
    except (ds2mapa.MapaError, ds2arquivos.ArquivoError, SaveError, OSError, ValueError, KeyError) as err:
        print(json.dumps({"error": str(err)}, ensure_ascii=False))
        return 1
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
