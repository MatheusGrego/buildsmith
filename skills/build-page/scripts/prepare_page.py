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

import icones_wiki
import mapas_pagina
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


IMAGE_EXT = (".png", ".jpg", ".jpeg", ".gif", ".webp")


def icon_name(url: str) -> str:
    """Nome do arquivo do ícone: só o caminho da URL (sem ?query nem #fragmento) e sempre com extensão de
    imagem, para uma URL como .../Pagina#/CLAUDE.md não virar um CLAUDE.md no disco."""
    name = urlsplit(url).path.rstrip("/").rsplit("/", 1)[-1]
    name = re.sub(r"[^A-Za-z0-9._-]", "_", name).lstrip("._-") or "icone"
    return name if name.lower().endswith(IMAGE_EXT) else f"{name}.png"


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


TEMPLATE_JS = ("pagina.js", "mapa.js")
DS2_SCRIPTS = ROOT / "skills" / "ds2-save" / "scripts"
def _ds2mapa():
    if str(DS2_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(DS2_SCRIPTS))
    import ds2mapa

    return ds2mapa


def _jogo_instalado():
    _ds2mapa()
    import ds2arquivos

    game = ds2arquivos.game_dir_padrao()
    if game is None:
        raise OSError("DS2 SotFS não encontrado (defina BUILDSMITH_DS2_GAME)")
    return game


def carregar_area_do_jogo(cache_root: Path, jogo: str):
    def carregar(area: str) -> dict:
        return _ds2mapa().extrair_area(_jogo_instalado(), area, Path(cache_root) / jogo)
    return carregar


def listar_areas_do_jogo() -> list[str]:
    return [a["area"] for a in _ds2mapa().areas(_jogo_instalado())]


def montar_index(template_dir: Path) -> str:
    """Junta o esqueleto, o CSS e o JS num index.html só: o CSP da página só aceita script e estilo inline."""
    template_dir = Path(template_dir)
    html = (template_dir / "index.html").read_text(encoding="utf-8")
    css = (template_dir / "pagina.css").read_text(encoding="utf-8")
    js = "\n".join((template_dir / name).read_text(encoding="utf-8") for name in TEMPLATE_JS if (template_dir / name).exists())
    if "<!--CSS-->" not in html or "<!--JS-->" not in html:
        raise ValueError("template sem os marcadores <!--CSS--> e <!--JS-->")
    if "</style" in css.lower() or "</script" in js.lower():
        raise ValueError("CSS ou JS do template fecha a própria tag")
    return html.replace("<!--CSS-->", f"<style>\n{css}</style>", 1).replace("<!--JS-->", f"<script>\n{js}</script>", 1)


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


def prepare(plano_path, out_dir, jogo: str, cache_root=None, fetch=default_fetch, carregar_area=None,
            listar_areas=None) -> dict:
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

    for alvo, _fluxo in mapas_pagina.alvos(plano):
        alvo.pop("mapa", None)  # o mapa é sempre recalculado a partir dos pontos
    icones = icones_wiki.IconesWiki(cache_root / jogo / "icones.json", fetch)

    def icone_local(nome: str) -> str | None:
        url = icones.url(nome)
        return store.get(url) if url else None

    map_files = {}
    try:
        _ds2mapa()
        if carregar_area is None:
            carregar_area, listar_areas = carregar_area_do_jogo(cache_root, jogo), listar_areas or listar_areas_do_jogo
        map_files = mapas_pagina.preparar(plano, out_dir, carregar_area, listar_areas or (lambda: []), icone_local,
                                          icones.prebuscar)
    except ValueError:
        raise
    except Exception as err:  # jogo ausente, arquivo trocado por atualização: página sem mapa, com aviso
        store.avisos.append(f"mapa indisponível: {err}")
    (out_dir / "index.html").write_text(montar_index(SKILL_DIR / "template"), encoding="utf-8")
    (out_dir / "plano.json").write_text(json.dumps(plano, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "index": str(out_dir / "index.html"),
        "files": {"plano.json": str(out_dir / "plano.json"), **store.files, **map_files},
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
