"""Letras de escala (S/A/B/C/D/E) por item e nível de upgrade, pela tabela de upgrades da página do item na wiki.

O jogo guarda só o coeficiente (WeaponStatsAffectParam) e a letra do menu não sai dele por um limiar simples, então a
letra vem da wiki. Linhas usadas: "Regular" ou o nome do item (+0) e "Regular +N" / "<Nome> +N"; infusões ficam de
fora. Colunas de bônus, nesta ordem: FOR, DES, mágico, fogo, raio, sombrio (logo depois de durabilidade/peso).
Cache por 30 dias, inclusive quando a página não tem tabela.
"""
import json
import re
from datetime import date, timedelta
from html import unescape
from pathlib import Path

import icones_wiki

REFAZER = timedelta(days=30)
CACHE_VERSAO = 1
CHAVES = ["STR", "DEX", "magico", "fogo", "raio", "sombrio"]
LETRA = re.compile(r"^\*?([SABCDE])$")
LINHA = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S | re.I)
CELULA = re.compile(r"<t[hd][^>]*>(.*?)</t[hd]>", re.S | re.I)


def _texto(html: str) -> str:
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", html))).strip()


def _nivel(rotulo: str, nome: str) -> int | None:
    r = rotulo.strip().casefold()
    for base in ("regular", nome.strip().casefold()):
        if r == base:
            return 0
        m = re.fullmatch(re.escape(base) + r"\s*\+\s*(\d+)", r)
        if m:
            return int(m.group(1))
    return None


def letras_da_pagina(html: str, nome: str) -> dict[str, dict[str, str]]:
    """nível -> {atributo/elemento: letra}; só as colunas com letra."""
    ini = html.find('id="mw-content-text"')
    corpo = html[ini:] if ini >= 0 else html
    out = {}
    for linha in LINHA.findall(corpo):
        cels = [_texto(c) for c in CELULA.findall(linha)]
        if len(cels) < 13:
            continue
        nivel = _nivel(cels[0], nome)
        if nivel is None or str(nivel) in out:
            continue
        bonus = cels[7:13]
        if not all(LETRA.match(c) or c in ("", "-", "–", "^") for c in bonus):
            continue
        out[str(nivel)] = {k: LETRA.match(c).group(1) for k, c in zip(CHAVES, bonus) if LETRA.match(c)}
    return out


class EscalaWiki:
    def __init__(self, cache_path, fetch):
        self.cache_path = Path(cache_path)
        self.fetch = fetch
        try:
            self.cache = json.loads(self.cache_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.cache = {}
        if self.cache.get("v") != CACHE_VERSAO:
            self.cache = {"v": CACHE_VERSAO, "itens": {}}

    def _entrada(self, nome: str) -> dict:
        chave = nome.strip().casefold()
        g = self.cache["itens"].get(chave)
        try:
            vale = g and date.today() - REFAZER < date.fromisoformat(g["data"]) <= date.today()
        except (TypeError, ValueError):
            vale = False
        if vale:
            return g
        achado = {"url": None, "niveis": {}}
        for candidato in icones_wiki.candidatos(nome):
            url = icones_wiki.pagina_item(candidato)
            try:
                niveis = letras_da_pagina(self.fetch(url).decode("utf-8", errors="replace"), candidato)
            except Exception:  # rede, 404
                continue
            if niveis:
                achado = {"url": url, "niveis": niveis}
                break
        g = self.cache["itens"][chave] = {**achado, "data": date.today().isoformat()}
        self.salvar()
        return g

    def letras(self, nome: str, nivel: int) -> dict | None:
        """Letras do nível pedido; sem a linha desse nível, as do maior nível listado abaixo dele."""
        g = self._entrada(nome)
        abaixo = sorted((int(n) for n in g["niveis"] if int(n) <= nivel), reverse=True)
        if not abaixo:
            return None
        return {"letras": g["niveis"][str(abaixo[0])], "nivel": abaixo[0], "fonte": g["url"]}

    def salvar(self) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.cache_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.cache, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.cache_path)
