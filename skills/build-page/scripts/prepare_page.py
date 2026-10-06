#!/usr/bin/env python3
"""Prepara a pasta da página: valida o plano, baixa os ícones (com cache) e lista os arquivos a publicar."""
import argparse
import json
import re
import shutil
import sys
import urllib.request
from pathlib import Path

import validate_plano

SKILL_DIR = Path(__file__).resolve().parents[1]
ROOT = SKILL_DIR.parents[1]
HEADERS = {"User-Agent": "Mozilla/5.0 (buildsmith)"}


def default_fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=20) as response:
        return response.read()


def icon_name(url: str) -> str:
    name = url.split("?")[0].rstrip("/").rsplit("/", 1)[-1]
    return re.sub(r"[^A-Za-z0-9._-]", "_", name) or "icone.png"


class IconStore:
    """Baixa cada ícone uma vez para o cache e copia para <saida>/icons/."""

    def __init__(self, cache_dir: Path, out_dir: Path, fetch):
        self.cache_dir = cache_dir
        self.icons_dir = out_dir / "icons"
        self.fetch = fetch
        self.files: dict[str, str] = {}
        self.avisos: list[str] = []

    def get(self, url: str, name: str | None = None) -> str | None:
        cached = self.cache_dir / icon_name(url)
        name = name or cached.name
        if not cached.exists():
            try:
                data = self.fetch(url)
            except Exception as err:  # rede, 404, timeout: o nó só fica sem ícone
                self.avisos.append(f"ícone não baixou: {url} ({err})")
                return None
            cached.parent.mkdir(parents=True, exist_ok=True)
            cached.write_bytes(data)
        target = self.icons_dir / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(cached, target)
        rel = f"icons/{name}"
        self.files[rel] = str(target)
        return rel


def _nodes(plano: dict):
    yield from plano["personagem"].get("equipado", [])
    for step in plano["passos"]:
        yield from step.get("fluxo", [])
    for item in plano["itens"]:
        yield item["item"]
        yield from item.get("onde", [])
    for build in plano["comparacao"]:
        yield from build.get("ajuste", [])
    progresso = plano.get("progresso", {})
    for boss in progresso.get("chefes", []):
        yield boss["no"]
    for buy in progresso.get("compras", []):
        yield buy["loja"]
        yield buy["item"]
    for row in plano.get("dano", []):
        yield row["arma"]
        yield from row.get("por_causa", [])


def prepare(plano_path, out_dir, jogo: str, cache_root=None, fetch=default_fetch) -> dict:
    plano = json.loads(Path(plano_path).read_text(encoding="utf-8"))
    problems = validate_plano.validate(plano)
    if problems:
        raise ValueError("plano inválido: " + "; ".join(problems))
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    cache_root = Path(cache_root) if cache_root else Path.home() / ".buildsmith" / "cache"
    store = IconStore(cache_root / jogo / "icons", out_dir, fetch)

    for node in _nodes(plano):
        url = node.get("icone", "")
        if url.startswith("https://"):
            rel = store.get(url)
            if rel:
                node["icone"] = rel
            else:
                node.pop("icone")

    extras = json.loads((ROOT / "games" / jogo / "icons.json").read_text(encoding="utf-8"))
    for stat, url in extras["stats"].items():
        store.get(url, f"stat-{stat}.png")
    store.get(extras["almas"], "almas.png")

    shutil.copyfile(SKILL_DIR / "template" / "index.html", out_dir / "index.html")
    (out_dir / "plano.json").write_text(json.dumps(plano, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "index": str(out_dir / "index.html"),
        "files": {"plano.json": str(out_dir / "plano.json"), **store.files},
        "avisos": store.avisos,
    }


def main(argv=None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="prepare_page")
    parser.add_argument("plano", help="plano.json montado pela skill build")
    parser.add_argument("saida", help="pasta da página (no scratchpad)")
    parser.add_argument("--jogo", default="ds2")
    parser.add_argument("--cache", help="raiz do cache (padrão ~/.buildsmith/cache)")
    args = parser.parse_args(argv)
    try:
        out = prepare(args.plano, args.saida, args.jogo, cache_root=args.cache, fetch=default_fetch)
    except ValueError as err:
        print(json.dumps({"error": str(err)}, ensure_ascii=False))
        return 1
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
