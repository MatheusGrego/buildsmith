#!/usr/bin/env python3
"""Prepara a pasta da página: valida o plano, baixa os ícones (com cache) e lista os arquivos a publicar."""
import argparse
import json
import re
import shutil
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

import validate_plano

SKILL_DIR = Path(__file__).resolve().parents[1]
ROOT = SKILL_DIR.parents[1]
HEADERS = {"User-Agent": "Mozilla/5.0 (buildsmith)"}
# Ícone só baixa da wiki: o plano é escrito pelo modelo, e uma URL qualquer viraria um jeito de mandar dados para fora.
ICON_HOSTS = ("fextralifeimages.com", "fextralife.com")
LOCAL_ICON = re.compile(r"^icons/[A-Za-z0-9._-]+$")


def wiki_icon(url) -> bool:
    parts = urlsplit(url) if isinstance(url, str) else None
    host = (parts.hostname or "").lower() if parts else ""
    return (parts is not None and parts.scheme == "https" and not parts.username and parts.port in (None, 443)
            and any(host == h or host.endswith("." + h) for h in ICON_HOSTS))


class WikiRedirects(urllib.request.HTTPRedirectHandler):
    """Redirecionamento só para a wiki: um redirect aberto levaria a URL (e o que vai nela) para fora."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not wiki_icon(newurl):
            raise urllib.error.HTTPError(newurl, code, "redirecionamento para fora da wiki", headers, fp)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def default_fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.build_opener(WikiRedirects).open(request, timeout=20) as response:
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
        if not wiki_icon(url):
            self.avisos.append(f"ícone fora da wiki ignorado: {url}")
            return None
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
        for source in item.get("fontes", []):
            yield from source.get("fluxo", [])
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
    yield from plano.get("agora", {}).get("faltam", [])
    spells = plano.get("feiticos")
    if spells:
        yield spells["catalisador"]
        for spell in spells.get("lista", []):
            yield spell["no"]


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
        url = node.get("icone")
        if not url or LOCAL_ICON.match(str(url)):
            continue
        rel = store.get(url)
        if rel:
            node["icone"] = rel
        else:
            node.pop("icone")  # a página só mostra ícone local (icons/...)

    extras = json.loads((ROOT / "games" / jogo / "icons.json").read_text(encoding="utf-8"))
    for stat, url in extras["stats"].items():
        store.get(url, f"stat-{stat}.png")
    store.get(extras["almas"], "almas.png")
    store.get(extras["fogueira"], "fogueira.png")

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
