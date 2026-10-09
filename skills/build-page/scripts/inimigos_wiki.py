"""Nome dos inimigos comuns pela wiki do DS2 (Fextralife), cruzando com o que o jogo diz de cada tipo.

O jogo não guarda nome de inimigo comum (só de chefe e NPC). Cada tipo do jogo (linha do EnemyParam) tem almas e
itens de drop; a página de cada inimigo da wiki tem almas ("NG: 180 Souls") e links para os drops; a página da área
lista os inimigos dela. Pontos de um inimigo da wiki para um tipo do jogo:

- cada item de drop do jogo que aparece na página e em no máximo COMUM_MAX páginas de inimigo: 1 ponto
  ("Varangian Set" na wiki vale para "Varangian Helm" do jogo); só conta se a página cita pelo menos metade desses
  itens (um lote genérico com duas peças de um set não vira aquele inimigo);
- almas do jogo iguais a um valor "NG: N Souls" da página: 2 pontos;
- inimigo listado na página da área: 1 ponto.

O tipo só ganha nome quando o melhor tem MINIMO pontos ou mais (almas sozinhas não bastam: 300 almas é comum) e nenhum
outro empata com ele; a prova vai junto. Tipo sem nome herda o de outro tipo da mesma família do EnemyParam
(linha // 100 = mesmo modelo no jogo) quando todos os confirmados da família têm o mesmo nome.
Cache das páginas por 30 dias.
"""
import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from html import unescape
from pathlib import Path

import icones_wiki

WIKI = icones_wiki.WIKI
LISTA = WIKI + "Enemies"
REFAZER = timedelta(days=30)
CACHE_VERSAO = 1
COMUM_MAX = 3
MINIMO = 3
LINK = re.compile(r'<a href="/([^"#:?]+)" title="([^"]+)"')
ALMAS = re.compile(r"NG\s*:\s*([\d][\d,.]*)\s*Souls", re.I)
FIM_CONTEUDO = ('class="printfooter"', 'id="catlinks"')


def _conteudo(html: str) -> str:
    ini = html.find('id="mw-content-text"')
    corpo = html[ini:] if ini >= 0 else html
    fins = [i for i in (corpo.find(m) for m in FIM_CONTEUDO) if i > 0]
    return corpo[:min(fins)] if fins else corpo


def lista_inimigos(html: str) -> list[tuple[str, str]]:
    """(nome, URL) da aba "All Enemies by Name" da página Enemies."""
    ini = html.find('id="tabber-All_Enemies_by_Name"')
    if ini < 0:
        return []
    fim = html.find('id="tabber-Enemies_by_Location"', ini)
    out = {}
    for caminho, titulo in LINK.findall(html[ini:fim if fim > 0 else len(html)]):
        out.setdefault(unescape(titulo), WIKI + caminho)
    return list(out.items())


def dados_pagina(html: str) -> dict:
    corpo = _conteudo(html)
    texto = unescape(re.sub(r"<[^>]+>", " ", corpo))
    almas = sorted({int(re.sub(r"[,.]", "", m)) for m in ALMAS.findall(texto)})
    return {"almas": almas, "links": sorted({unescape(t) for _c, t in LINK.findall(corpo)})}


def inimigos_da_area(html: str) -> list[str]:
    """Nomes (título do link) da lista logo depois do título "Enemies" da página da área."""
    ini = html.find('id="Enemies"')
    if ini < 0:
        return []
    ul = html.find("<ul>", ini)
    fim = html.find("</ul>", ul)
    proximo = html.find("<h", ini + 12)
    if ul < 0 or fim < 0 or (0 < proximo < ul):
        return []
    return [unescape(t) for _c, t in LINK.findall(html[ul:fim])]


def _cita(links: set, item: str) -> bool:
    return item in links or any(l.endswith(" Set") and item.startswith(l[:-4] + " ") for l in links)


def nomear(tipo: dict, paginas: dict, da_area: set) -> dict | None:
    """tipo: {almas, drops}; paginas: nome -> {url, almas, links}. Devolve {nome, wiki, prova} ou None."""
    citacoes = {d: sum(1 for p in paginas.values() if _cita(set(p["links"]), d)) for d in tipo.get("drops", [])}
    distintos = [d for d in tipo.get("drops", []) if 0 < citacoes[d] <= COMUM_MAX]
    placar = []
    for nome, p in paginas.items():
        links = set(p["links"])
        drops = [d for d in distintos if _cita(links, d)]
        if 2 * len(drops) < len(distintos):
            drops = []
        almas = bool(tipo.get("almas")) and tipo["almas"] in p["almas"]
        na_area = nome in da_area
        pontos = len(drops) + 2 * almas + na_area
        if pontos:
            prova = ([f"drops: {', '.join(drops)}"] if drops else []) + ([f"almas: {tipo['almas']}"] if almas else []) \
                + (["listado na página da área"] if na_area else [])
            placar.append((pontos, nome, p["url"], prova))
    placar.sort(key=lambda x: -x[0])
    if not placar or placar[0][0] < MINIMO or (len(placar) > 1 and placar[1][0] == placar[0][0]):
        return None
    return {"nome": placar[0][1], "wiki": placar[0][2], "prova": "; ".join(placar[0][3])}


def por_familia(nomes: dict, tipos) -> dict:
    """Completa os tipos sem nome com o nome único dos confirmados da mesma família (tipo // 100)."""
    familias = {}
    for t, n in nomes.items():
        familias.setdefault(int(t) // 100, {}).setdefault(n["nome"], (t, n))
    out = dict(nomes)
    for t in tipos:
        f = familias.get(int(t) // 100, {})
        if t not in out and len(f) == 1:
            origem, n = next(iter(f.values()))
            out[t] = {"nome": n["nome"], "wiki": n["wiki"], "prova": f"mesmo modelo do jogo que o tipo {origem} ({n['prova']})"}
    return out


class InimigosWiki:
    def __init__(self, cache_path, fetch, workers: int = 6):
        self.cache_path = Path(cache_path)
        self.fetch = fetch
        self.workers = workers
        try:
            self.cache = json.loads(self.cache_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.cache = {}
        if self.cache.get("v") != CACHE_VERSAO:
            self.cache = {"v": CACHE_VERSAO, "paginas": {}, "areas": {}}

    def _vencido(self, data: str | None) -> bool:
        try:
            return date.fromisoformat(data) <= date.today() - REFAZER or date.fromisoformat(data) > date.today()
        except (TypeError, ValueError):
            return True

    def _html(self, url: str) -> str | None:
        try:
            return self.fetch(url).decode("utf-8", errors="replace")
        except Exception:  # rede, 404: fica sem a página
            return None

    def paginas(self) -> dict:
        """nome -> {url, almas, links} de todos os inimigos da wiki (busca em paralelo, guarda por 30 dias)."""
        if self._vencido(self.cache.get("data")) or not self.cache["paginas"]:
            html = self._html(LISTA)
            lista = lista_inimigos(html) if html else []
            if lista:
                with ThreadPoolExecutor(max_workers=self.workers) as ex:
                    htmls = list(ex.map(lambda nu: self._html(nu[1]), lista))
                self.cache["paginas"] = {n: {"url": u, **dados_pagina(h)} for (n, u), h in zip(lista, htmls) if h}
                self.cache["data"] = date.today().isoformat()
                self.salvar()
        return self.cache["paginas"]

    def da_area(self, nome_area: str) -> set:
        g = self.cache["areas"].get(nome_area)
        if not g or self._vencido(g.get("data")):
            nomes = []
            for candidato in icones_wiki.candidatos(nome_area):
                html = self._html(icones_wiki.pagina_item(candidato))
                if html and (nomes := inimigos_da_area(html)):
                    break
            g = self.cache["areas"][nome_area] = {"inimigos": nomes, "data": date.today().isoformat()}
            self.salvar()
        return set(g["inimigos"])

    def nomes(self, tipos: dict, nome_area: str) -> dict:
        """tipo -> {nome, wiki, prova} para os tipos com nome confirmado."""
        paginas = self.paginas()
        if not paginas:
            return {}
        area = self.da_area(nome_area)
        return por_familia({t: n for t, dados in tipos.items() if (n := nomear(dados, paginas, area))}, tipos)

    def salvar(self) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.cache_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.cache, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.cache_path)
