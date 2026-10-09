"""Ícone de um item pela página dele na wiki do DS2 (Fextralife), com cache por nome.

O ícone é a primeira imagem do quadro do item (`class="infobox"`) e só vale se vier dos servidores de imagem da
Fextralife. O cache guarda também quando a página não tem ícone (tenta de novo depois de 30 dias).
"""
import json
import re
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import quote, urlsplit

WIKI = "https://darksouls2.wiki.fextralife.com/"
HOSTS = ("fextralifeimages.com", "fextralife.com")
REFAZER_FALTA = timedelta(days=30)
IMG = re.compile(r"<img[^>]*?\ssrc=[\"']([^\"']+)[\"']", re.I)


def pagina_item(nome: str) -> str:
    return WIKI + quote(nome.strip().replace(" ", "_"), safe="_'()&,-.")


def _da_fextralife(url: str) -> bool:
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    return parts.scheme == "https" and any(host == h or host.endswith("." + h) for h in HOSTS)


def icone_da_pagina(html: str) -> str | None:
    inicio = html.find('class="infobox"')
    if inicio < 0:
        return None
    fim = html.find("</table>", inicio)
    m = IMG.search(html, inicio, fim if fim > 0 else len(html))
    if not m:
        return None
    url = m.group(1)
    return url if _da_fextralife(url) else None


class IconesWiki:
    def __init__(self, cache_path, fetch):
        self.cache_path = Path(cache_path)
        self.fetch = fetch
        try:
            self.cache = json.loads(self.cache_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.cache = {}
        self.mudou = False

    def _guardado(self, nome: str) -> dict | None:
        g = self.cache.get(nome.strip().casefold())
        if g and (g.get("url") or date.fromisoformat(g["data"]) > date.today() - REFAZER_FALTA):
            return g
        return None

    def _buscar(self, nome: str) -> str | None:
        try:
            return icone_da_pagina(self.fetch(pagina_item(nome)).decode("utf-8", errors="replace"))
        except Exception:  # rede, 404: fica sem ícone e tenta de novo depois
            return None

    def _guardar(self, nome: str, url: str | None) -> None:
        self.cache[nome.strip().casefold()] = {"url": url, "data": date.today().isoformat()}
        self.mudou = True

    def url(self, nome: str) -> str | None:
        g = self._guardado(nome)
        if g:
            return g.get("url")
        url = self._buscar(nome)
        self._guardar(nome, url)
        self.salvar()
        return url

    def prebuscar(self, nomes, workers: int = 6) -> None:
        """Busca de uma vez (em paralelo) os ícones que ainda não estão no cache."""
        from concurrent.futures import ThreadPoolExecutor

        faltam = [n for n in dict.fromkeys(nomes) if n and not self._guardado(n)]
        if not faltam:
            return
        with ThreadPoolExecutor(max_workers=workers) as ex:
            for nome, url in zip(faltam, ex.map(self._buscar, faltam)):
                self._guardar(nome, url)
        self.salvar()

    def salvar(self) -> None:
        if not self.mudou:
            return
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.cache_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.cache, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(self.cache_path)
        self.mudou = False
