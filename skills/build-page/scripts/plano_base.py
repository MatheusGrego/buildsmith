#!/usr/bin/env python3
"""Plano sem IA: a página de cada personagem do save existe mesmo sem o Claude.

Só o que o save diz (nome, nível, almas, atributos, equipado), sem objetivo, passos nem itens: o resto da página sai por
código (Catálogo, Onde pegar e Passos dos itens marcados, Equipamento, Mapa, save ao vivo). O /buildsmith:build troca
este plano por um com objetivo e comparação; "sem_ia": true marca que ele ainda não passou pela IA.

  python plano_base.py [--home ~/.buildsmith]   cria a página de quem ainda não tem e imprime as criadas
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DS2_SCRIPTS = ROOT / "skills" / "ds2-save" / "scripts"
SEGMENT = re.compile(r"^[a-z0-9][a-z0-9._-]{0,180}$")  # o mesmo do servidor: pasta com outro nome não vira página
SUB_ARMADURA = {"cabeca": "cabeça", "peito": "peito", "maos": "mãos", "pernas": "pernas"}


def _ds2save():
    if str(DS2_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(DS2_SCRIPTS))
    import ds2save

    return ds2save


def plano_base(snap: dict, gerado_em: str) -> dict:
    eq = snap["equipped"]
    conhecido = lambda x: x and not x["name"].startswith("desconhecido")  # noqa: E731
    equipado = [{"tipo": "item", "nome": x["name"], "sub": slot} for slot, x in eq["hands"].items() if conhecido(x)]
    equipado += [{"tipo": "item", "nome": x["name"], "sub": SUB_ARMADURA[slot]} for slot, x in eq["armor"].items() if conhecido(x)]
    equipado += [{"tipo": "item", "nome": x["name"], "sub": "anel"} for x in eq["rings"] if conhecido(x)]
    return {"versao": 2, "gerado_em": gerado_em, "jogo": "ds2", "objetivo": "", "sem_ia": True,
            "personagem": {"name": snap["name"], "level": snap["level"], "souls": snap["souls"],
                           "soul_memory": snap["soul_memory"], "stats": dict(snap["stats"]), "equipado": equipado},
            "alvo_stats": dict(snap["stats"]), "mudancas": [], "passos": [], "fases": [], "itens": [], "comparacao": [],
            "fontes": []}


def _preparar(plano_path: Path, jogo: str) -> dict:
    import prepare_page

    try:
        return prepare_page.prepare(plano_path, plano_path.parent, jogo)
    except ValueError as err:
        return {"error": str(err)}


def criar_paginas(home, save=None, preparar=None, regulation=None, avisa=lambda texto: None) -> list[str]:
    """Página sem IA de cada personagem do save que ainda não tem página. Devolve as criadas ("ds2/<slug>")."""
    ds2save = _ds2save()
    preparar = preparar or _preparar
    try:
        save = Path(save) if save else ds2save.find_save()
        lista = ds2save.personagens(save)
    except (ds2save.SaveError, OSError, ImportError) as err:  # sem save (ou sem pycryptodome): nada a criar
        avisa(f"não li o save do DS2, nenhuma página nova: {ds2save.erro_do_save(err)}")
        return []
    criadas = []
    for p in lista:
        pasta = Path(home) / "paginas" / "ds2" / p["slug"]
        if not SEGMENT.match(p["slug"]) or (pasta / "plano.json").is_file():
            continue
        avisa(f"criando a página de {p['nome']} (sem IA)...")
        try:
            snap = ds2save.snapshot(save, p["slot"], regulation=regulation)
        except (ds2save.SaveError, OSError) as err:
            avisa(f"  não deu ({err})")
            continue
        plano = plano_base(snap, datetime.now(timezone.utc).isoformat(timespec="seconds"))
        pasta.mkdir(parents=True, exist_ok=True)
        destino = pasta / "plano.json"
        tmp = destino.with_suffix(".tmp")
        tmp.write_text(json.dumps(plano, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, destino)
        out = preparar(destino, "ds2")
        if out.get("error"):
            avisa(f"  não deu ({out['error']})")
            destino.unlink(missing_ok=True)
            continue
        criadas.append(f"ds2/{p['slug']}")
    return criadas


def main(argv=None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="plano_base")
    parser.add_argument("--home", default=os.environ.get("BUILDSMITH_HOME", str(Path.home() / ".buildsmith")))
    parser.add_argument("--save")
    args = parser.parse_args(argv)
    print(json.dumps({"criadas": criar_paginas(Path(args.home), args.save, avisa=lambda t: print(t, file=sys.stderr))},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
