#!/usr/bin/env python3
"""Servidor local do buildsmith.

Mostra as páginas de ~/.buildsmith/paginas/<jogo>/<personagem>/ e guarda o que a página grava
(fila de pesquisa, fogueiras de feito, seleção de feitiços, itens marcados no Catálogo) em
~/.buildsmith/estado/<jogo>/<personagem>.json.
Só biblioteca padrão. Escuta apenas em 127.0.0.1.

  pythonw serve.py --open          sobe o servidor (ou reaproveita o que já está de pé) e abre o navegador
  python serve.py estado ...       imprime o estado de um personagem (usado pela skill)
  python serve.py responder ...    marca um pedido da fila como respondido
  python serve.py confirmar ...    grava a confirmação de um passo marcado como feito

Os botões "Atualizar plano" e "Responder fila" da página rodam a skill sem janela (claude -p) pelo runner.py.
O mapa da página pergunta a posição do personagem (relida do save) e a rota pelo chão até um ponto.
O Catálogo lista todos os itens do jogo (ds2itens) e "Onde pegar" dos marcados sai por código (ds2fontes), sem IA.
Pedidos que gravam ou rodam algo exigem o cabeçalho X-Buildsmith: 1 e Host/Origin locais.
"""
import argparse
import html
import json
import mimetypes
import os
import re
import sys
import threading
import math
import unicodedata
import urllib.request
from collections import OrderedDict
import webbrowser
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

import abrir
import retrato
from runner import Busy, Runner

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "skills" / "ds2-save" / "scripts"))

PORT = 8642
VERSAO = abrir.versao_codigo()  # o abridor compara com a do disco: código novo depois de um pull = reinicia
SEGMENT = re.compile(r"^[a-z0-9][a-z0-9._-]{0,180}$")
GAME_OK = re.compile(r"^[a-z0-9]+$")
COLLECTIONS = {"feitos", "pedidos", "config", "quero", "metas"}
MODOS = {"plano", "fila"}
MAX_BODY = 4 * 1024
AREA_OK = re.compile(r"^m\d\d_\d\d_\d\d_\d\d$")
TEX_OK = re.compile(r"^[a-z0-9][a-z0-9_-]{0,120}\.dds$")  # textura da cena 3D (o extrator grava em minúsculas)
TIPOS_ESTATICOS = {".js": "text/javascript", ".mjs": "text/javascript", ".json": "application/json"}  # o registro do Windows erra o .js
COORD_MAX = 10000.0
AREAS_EM_MEMORIA = 12  # ~3 MB de grafo cada; as fontes de um item passam por várias áreas
MAX_QUERO = 200  # itens marcados ao mesmo tempo no Catálogo
MAX_METAS = 40  # metas de arma ligadas ao mesmo tempo (Equipamento)
ICONE_OK = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,180}$")
MAX_FILA = 50  # pedidos na_fila ao mesmo tempo
TEXTO_MAX = 160
CONTROLE = re.compile(r"[\x00-\x1f\x7f-\x9f\u2028\u2029]")
# A página só fala com o próprio servidor: fetch e imagens de fora ficam bloqueados (nada sai por um XSS).
CSP_PAGINA = ("default-src 'none'; script-src 'unsafe-inline' 'self'; style-src 'unsafe-inline' https://fonts.googleapis.com; "
              "font-src https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self'; base-uri 'none'; "
              "form-action 'none'; frame-ancestors 'none'")
CSP_INICIO = "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
DOCTYPE = b'<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head><body>'


def default_home() -> Path:
    return Path(os.environ.get("BUILDSMITH_HOME", Path.home() / ".buildsmith"))


def slug(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def state_path(home: Path, jogo: str, personagem: str) -> Path:
    return Path(home) / "estado" / jogo / f"{personagem}.json"


def read_state(home: Path, jogo: str, personagem: str) -> dict:
    path = state_path(home, jogo, personagem)
    state = {"feitos": {}, "pedidos": {}, "config": {}, "quero": {}, "metas": {}}
    if path.is_file():
        state.update(json.loads(path.read_text(encoding="utf-8")))
    return state


def _linha(value, limite: int) -> bool:
    return isinstance(value, str) and 0 < len(value) <= limite and not CONTROLE.search(value)


def clean_doc(collection: str, doc_id: str, data) -> dict | None:
    """Documento que a página pode gravar, campo a campo; qualquer outra coisa é recusada (None).

    O texto de um pedido vai para o modelo no próximo /buildsmith:build: uma linha, tamanho limitado, sem campo
    extra e sem o estado "respondido" (só a skill responde, pela CLI).
    """
    if not isinstance(data, dict):
        return None
    if collection == "pedidos":
        if (set(data) - {"texto", "origem", "estado", "criado_em"} or not _linha(data.get("texto"), TEXTO_MAX)
                or data.get("estado") != "na_fila" or not _linha(data.get("origem", "fila"), 80)
                or not _linha(data.get("criado_em", "-"), 40)):
            return None
        return data
    if collection == "feitos":
        if (set(data) - {"marcado", "em", "confirmado"} or not isinstance(data.get("marcado"), bool)
                or not _linha(data.get("em", "-"), 40) or data.get("confirmado") is not None):
            return None
        return data
    if collection == "quero":
        item_id = data.get("item_id")
        if (set(data) - {"item_id", "desde", "marcado"} or not doc_id.isdigit() or len(doc_id) > 10
                or not isinstance(item_id, int) or isinstance(item_id, bool) or str(item_id) != doc_id
                or not isinstance(data.get("marcado"), bool) or not _linha(data.get("desde", "-"), 40)):
            return None
        return data
    if collection == "metas":  # meta de uma arma no Equipamento: reforço e infusão que o jogador quer (ds2calc.INFUSOES)
        def inteiro(v, menor, maior):
            return isinstance(v, int) and not isinstance(v, bool) and menor <= v <= maior
        item_id = data.get("item_id")
        if (set(data) - {"item_id", "nivel", "infusao", "ativa", "desde"} or not doc_id.isdigit() or len(doc_id) > 10
                or not inteiro(item_id, 1, 9_999_999_999) or str(item_id) != doc_id or not inteiro(data.get("nivel"), 0, 10)
                or not inteiro(data.get("infusao"), 0, 9) or not isinstance(data.get("ativa"), bool)
                or not _linha(data.get("desde", "-"), 40)):
            return None
        return data
    if collection == "config" and doc_id == "feiticos":
        sel = data.get("selecionados")
        if (set(data) - {"selecionados", "em"} or not isinstance(sel, list) or len(sel) > 40
                or not all(isinstance(x, str) and SEGMENT.match(x) for x in sel) or not _linha(data.get("em", "-"), 40)):
            return None
        return data
    return None


_lock = threading.Lock()


def write_doc(home: Path, jogo: str, personagem: str, collection: str, doc_id: str, data: dict, merge: bool = False) -> dict:
    with _lock:
        state = read_state(home, jogo, personagem)
        current = state[collection].get(doc_id, {}) if merge else {}
        state[collection][doc_id] = {**current, **data}
        path = state_path(home, jogo, personagem)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, path)
        return state


def build_prompt(home: Path, jogo: str, personagem: str, modo: str) -> str:
    """Comando da skill para o botão da página.

    Só o slug da URL (já conferido pelo SEGMENT) entra no prompt. Nada do plano.json: ele é gravado pelo
    modelo, e um nome plantado ali viraria instrução do usuário em todo clique. A skill lê o nome como dado.
    """
    if not GAME_OK.match(jogo) or not SEGMENT.match(personagem) or modo not in MODOS:
        raise ValueError("jogo, personagem ou modo inválido")
    extra = " fila" if modo == "fila" else ""
    return f"/buildsmith:build {jogo}{extra} (pela página, personagem: {personagem})"


def pages(home: Path) -> list[tuple[str, str, float]]:
    found = []
    for plan in sorted((Path(home) / "paginas").glob("*/*/plano.json")):
        jogo, personagem = plan.parent.parent.name, plan.parent.name
        if SEGMENT.match(jogo) and SEGMENT.match(personagem):  # pasta com outro nome não vira link
            found.append((jogo, personagem, plan.stat().st_mtime))
    return found


def principal(home: Path, found: list[tuple[str, str, float]]) -> tuple[str, str, float]:
    """Página que o / abre: a mais recente com plano da IA; a sem IA (plano_base) só quando não há outra."""
    def sem_ia(pagina) -> bool:
        jogo, personagem, _ = pagina
        try:
            plano = json.loads((Path(home) / "paginas" / jogo / personagem / "plano.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False
        return isinstance(plano, dict) and plano.get("sem_ia") is True
    return max(found, key=lambda x: (not sem_ia(x), x[2]))


def personagens(home: Path, jogo: str, save=None, steam_dirs=None) -> dict:
    """Personagens do save cruzados com as páginas: o que a seleção da página mostra."""
    import ds2save  # só aqui: o servidor sobe mesmo sem pycryptodome

    try:
        lista = ds2save.personagens(Path(save) if save else ds2save.find_save())
    except (ds2save.SaveError, OSError, ImportError) as err:
        return {"personagens": [], "erro": str(err), "print": False}
    out = []
    for p in lista:
        slug_ = p["slug"]
        plano_path = Path(home) / "paginas" / jogo / slug_ / "plano.json"
        icones = []
        if SEGMENT.match(slug_) and plano_path.is_file():
            try:
                equipado = json.loads(plano_path.read_text(encoding="utf-8"))["personagem"].get("equipado", [])
            except (OSError, ValueError, KeyError, TypeError):
                equipado = []
            for node in equipado if isinstance(equipado, list) else []:
                icone = node.get("icone") if isinstance(node, dict) else None
                if isinstance(icone, str) and re.fullmatch(r"icons/[A-Za-z0-9._-]+", icone):
                    icones.append({"nome": str(node.get("nome", "")), "sub": str(node.get("sub", "")),
                                   "icone": f"/p/{jogo}/{slug_}/{icone}"})
        foto = retrato.achar(home, jogo, slug_) if SEGMENT.match(slug_) else None
        out.append({**p, "pagina": plano_path.is_file(), "url": f"/p/{jogo}/{slug_}/" if plano_path.is_file() else None,
                    "retrato": f"/api/{jogo}/{slug_}/retrato?v={int(foto.stat().st_mtime)}" if foto else None,
                    "equipado_icones": icones})
    return {"personagens": out, "print": retrato.ultimo_print(steam_dirs) is not None}


def coords(texto) -> tuple[float, float, float] | None:
    """"x,y,z" com números finitos e dentro do mapa; qualquer outra coisa = None."""
    try:
        v = tuple(float(c) for c in str(texto).split(","))
    except ValueError:
        return None
    return v if len(v) == 3 and all(math.isfinite(c) and abs(c) <= COORD_MAX for c in v) else None


class FluxoVivo:
    """Estado ao vivo do jogo (ds2vivo: memória, só leitura) para o minimapa: uma thread lê a ~10 Hz enquanto houver
    alguém ouvindo o stream e todos recebem o mesmo valor. Sem ninguém ouvindo, nada lê o jogo."""

    def __init__(self, leitor=None, intervalo: float = 0.1, area=None):
        self._leitor, self.intervalo, self._area = leitor, intervalo, area
        self._cond = threading.Condition()
        self._valor, self._seq, self._ouvintes = None, 0, 0
        self._thread = None
        self.parar = threading.Event()

    def _ler(self) -> dict:
        try:
            if self._leitor is None:
                import ds2vivo
                self._leitor = ds2vivo.LeitorVivo(area=self._area)
            return self._leitor.ler()
        except Exception as err:  # jogo, permissão ou leitor com defeito: o minimapa só mostra "fora"
            return {"ativo": False, "motivo": f"erro na leitura ({type(err).__name__})"}

    def atual(self) -> dict:
        with self._cond:
            if self._ouvintes and self._valor is not None:
                return self._valor
        return self._ler()

    def _laco(self) -> None:
        while not self.parar.is_set():
            with self._cond:
                if not self._ouvintes:
                    self._thread = None
                    return
            valor = self._ler()
            with self._cond:
                self._valor, self._seq = valor, self._seq + 1
                self._cond.notify_all()
            self.parar.wait(self.intervalo)

    def entrar(self) -> None:
        with self._cond:
            self._ouvintes += 1
            if self._thread is None:
                self._thread = threading.Thread(target=self._laco, daemon=True)
                self._thread.start()

    def sair(self) -> None:
        with self._cond:
            self._ouvintes = max(0, self._ouvintes - 1)

    def esperar(self, seq: int, timeout: float) -> tuple[int, dict | None]:
        """Próximo valor depois de `seq` (ou None se não chegou nada no tempo)."""
        with self._cond:
            self._cond.wait_for(lambda: self._seq != seq or self.parar.is_set(), timeout)
            return (self._seq, self._valor) if self._seq != seq else (seq, None)


class MapaVivo:
    """Posição do personagem (relê o save só quando o arquivo muda) e rota pelo chão (grafo do navmesh em memória)."""

    def __init__(self, home: Path, save=None, carregar_area=None, calcular_combate=None, simular_arma=None):
        self.home, self.save = Path(home), save
        self.carregar_area = carregar_area  # área -> dados com malhas; None = jogo instalado + cache de ~/.buildsmith
        self.calcular_combate = calcular_combate  # (save, slot, índice, plano, metas) -> combate; None = ds2combate com o jogo
        self.simular_arma = simular_arma  # (save, slot, item, nível, infusão) -> simulação; None = ds2simula com o jogo
        self._combate: dict = {}
        self._regras = None  # (ds2calc, ds2data) do jogo instalado, lidos uma vez
        self._save = (None, {})
        self._vivo = (None, {})
        self._mundos = (None, {})
        self._ultimo_mundo = {}  # (personagem, área) -> último estado lido: vale enquanto o jogo grava o save
        self._nomes = None
        self._areas: OrderedDict = OrderedDict()
        self._lock = threading.Lock()

    def area_por_nome(self, nome: str) -> str | None:
        """Área do personagem com esse nome na última gravação do save (o minimapa usa enquanto a memória não diz)."""
        import ds2save

        path = Path(self.save) if self.save else ds2save.find_save()
        st = path.stat()
        chave = (str(path), st.st_mtime_ns, st.st_size)
        with self._lock:
            if self._save[0] != chave:
                self._save = (chave, ds2save.posicoes(path))
            return next((p["area"] for p in self._save[1].values() if p.get("nome") == nome), None)

    def posicao(self, slug_: str) -> dict | None:
        import ds2save

        path = Path(self.save) if self.save else ds2save.find_save()
        st = path.stat()
        chave = (str(path), st.st_mtime_ns, st.st_size)
        with self._lock:
            if self._save[0] != chave:
                self._save = (chave, ds2save.posicoes(path))
            p = self._save[1].get(slug_)
        if p is None:
            return None
        return {**p, "gravado_em": datetime.fromtimestamp(st.st_mtime, timezone.utc).isoformat(timespec="seconds")}

    def ao_vivo(self, slug_: str) -> dict | None:
        """Nível, atributos, inventário, equipado e chefes derrotados (relê o save só quando o arquivo muda)."""
        import ds2save

        path = Path(self.save) if self.save else ds2save.find_save()
        st = path.stat()
        chave = (str(path), st.st_mtime_ns, st.st_size)
        with self._lock:
            if self._vivo[0] != chave:
                if self._nomes is None:
                    self._nomes = ds2save.load_item_names()
                self._vivo = (chave, ds2save.ao_vivo(path, self._nomes))
            v = self._vivo[1].get(slug_)
        if v is None:
            return None
        return {**v, "gravado_em": datetime.fromtimestamp(st.st_mtime, timezone.utc).isoformat(timespec="seconds")}

    def estado_area(self, slug_: str, area: str) -> dict | None:
        """Portas, alavancas, baús e itens da área já usados no save, só os com regra conferida (o resto fica de fora).
        Relê o save só quando o arquivo muda; se a leitura falha (o jogo gravando), vale o último estado bom."""
        import ds2save

        dados, _ = self._area(area)
        path = Path(self.save) if self.save else ds2save.find_save()
        st = path.stat()
        chave = (str(path), st.st_mtime_ns, st.st_size)
        try:
            with self._lock:
                if self._mundos[0] != chave:
                    self._mundos = (chave, ds2save.mundos(path))
                mundo = self._mundos[1].get(slug_)
        except Exception:
            ultimo = self._ultimo_mundo.get((slug_, area))
            if ultimo is None:
                raise
            return ultimo
        if mundo is None:
            return None
        objetos = {o["parte"]: o["estado_ref"] for o in dados.get("objetos", []) if o.get("estado_ref")}
        itens = {str(p["lote"]): p["estado_ref"] for p in dados.get("itens", []) if p.get("estado_ref")}
        estado = ds2save.estado_mundo(mundo, [*objetos.values(), *itens.values()])
        out = {"area": area, "objetos": {k: estado[r] for k, r in objetos.items() if estado[r] is not None},
               "lotes": {k: estado[r] for k, r in itens.items() if estado[r] is not None}}
        self._ultimo_mundo[(slug_, area)] = out
        return out

    def _area(self, area: str):
        with self._lock:
            if area in self._areas:
                self._areas.move_to_end(area)
                return self._areas[area]
        import ds2mapa

        if self.carregar_area:
            dados = self.carregar_area(area)
        else:
            import ds2arquivos

            game = ds2arquivos.game_dir_padrao()
            if game is None:
                raise OSError("DS2 SotFS não encontrado")
            dados = ds2mapa.extrair_area(game, area, self.home / "cache" / "ds2")
        par = (dados, ds2mapa._grafo(dados))
        with self._lock:
            self._areas[area] = par
            while len(self._areas) > AREAS_EM_MEMORIA:
                self._areas.popitem(last=False)
        return par

    def rota(self, area: str, de, ate) -> dict | None:
        import ds2mapa

        dados, grafo = self._area(area)
        return ds2mapa.rota(dados, de, ate, grafo, ds2mapa.caixas_da_cena(self.home / "cache" / "ds2", area))

    def _regras_do_jogo(self):
        """(ds2calc, ds2data) do jogo instalado e os nomes dos itens, lidos uma vez."""
        import ds2calc
        import ds2data
        import ds2save

        with self._lock:
            if self._nomes is None:
                self._nomes = ds2save.load_item_names()
            if self._regras is None:
                self._regras = (ds2calc.load(), ds2data.load())
            return self._regras

    def simular(self, slug_: str, item_id: int, nivel: int, infusao: int) -> dict | None:
        """Arma em qualquer reforço e infusão com os atributos do save (ds2simula). SaveError = pedido inválido."""
        import ds2save

        pos = self.posicao(slug_)
        if pos is None:
            return None
        path = Path(self.save) if self.save else ds2save.find_save()
        if self.simular_arma:
            return self.simular_arma(path, pos["slot"], item_id, nivel, infusao)
        import ds2simula

        calc, data = self._regras_do_jogo()
        snap = ds2save.snapshot(path, pos["slot"], self._nomes)
        return ds2simula.simular(calc, data, self._nomes, snap, item_id, nivel, infusao)

    def combate(self, slug_: str, indice: dict | None = None) -> dict | None:
        """Equipamento (agora × melhor), feitiços, dano e compras pelo save (ds2combate); refeito quando o save, o plano
        ou o índice de itens mudam."""
        import ds2save

        pos = self.posicao(slug_)
        if pos is None:
            return None
        path = Path(self.save) if self.save else ds2save.find_save()
        st = path.stat()
        plano_path = self.home / "paginas" / "ds2" / slug_ / "plano.json"
        estado_path = state_path(self.home, "ds2", slug_)
        chave = (str(path), st.st_mtime_ns, st.st_size, plano_path.stat().st_mtime_ns if plano_path.is_file() else None,
                 indice is not None, estado_path.stat().st_mtime_ns if estado_path.is_file() else None)
        with self._lock:
            if slug_ in self._combate and self._combate[slug_][0] == chave:
                return self._combate[slug_][1]
        try:
            plano = json.loads(plano_path.read_text(encoding="utf-8")) if plano_path.is_file() else None
        except (OSError, ValueError):
            plano = None
        plano = plano if isinstance(plano, dict) else None
        try:
            metas = read_state(self.home, "ds2", slug_).get("metas")
        except (OSError, ValueError):
            metas = None
        metas = metas if isinstance(metas, dict) else {}
        if self.calcular_combate:
            out = self.calcular_combate(path, pos["slot"], indice, plano, metas)
        else:
            import ds2combate

            regras = self._regras_do_jogo()
            snap = ds2save.snapshot(path, pos["slot"], self._nomes)
            out = ds2combate.combate(*regras, self._nomes, snap, indice, plano, metas=metas)
        with self._lock:
            self._combate[slug_] = (chave, out)
        return out

    def fontes(self, slug_: str, item: dict, indice: dict) -> dict | None:
        """Onde pegar o item para este personagem (ds2fontes): fontes no formato do plano e os passos."""
        import ds2fontes
        import ds2mapa

        vivo, pos = self.ao_vivo(slug_), self.posicao(slug_)
        if vivo is None or pos is None:
            return None
        pers = {**vivo, "fogueiras": pos["fogueiras"]}
        res = ds2fontes.fontes(item, indice, pers, carregar_area=self._area,
                               estado_area=lambda area: self.estado_area(slug_, area),
                               caixas_de=lambda area: ds2mapa.caixas_da_cena(self.home / "cache" / "ds2", area))
        return {"item": ds2fontes.pagina(res), "passos": ds2fontes.passos(res, pers), "tem": res["tem"],
                "requisito": res["requisito"]}


class Catalogo:
    """Índice de itens do jogo (ds2itens) em memória: montado em segundo plano na primeira vez (o GET não espera)."""

    def __init__(self, home: Path, montar=None):
        self.home = Path(home)
        self.montar = montar  # () -> índice; None = ds2itens.carregar com o jogo instalado e o cache de ~/.buildsmith
        self._indice = None
        self._estado: str | None = None
        self._lock = threading.Lock()

    def indice(self) -> dict | None:
        with self._lock:
            return self._indice

    def estado(self) -> str | None:
        with self._lock:
            return self._estado

    def iniciar(self) -> bool:
        with self._lock:
            if self._estado is not None or self._indice is not None:
                return False
            self._estado = "montando"
        threading.Thread(target=self._rodar, daemon=True).start()
        return True

    def _rodar(self) -> None:
        try:
            if self.montar:
                indice = self.montar()
            else:
                import ds2arquivos
                import ds2itens

                game = ds2arquivos.game_dir_padrao()
                if game is None:
                    raise OSError("DS2 SotFS não encontrado")
                indice = ds2itens.carregar(game, self.home / "cache" / "ds2")
            with self._lock:
                self._indice, self._estado = indice, None
        except Exception as err:  # jogo ausente, formato inesperado
            with self._lock:
                self._estado = f"{type(err).__name__}: {err}"[:200]


def icone_local(home: Path, url) -> str | None:
    """Ícone da wiki já baixado no cache (icons/<arquivo>, o mesmo nome do prepare_page); None se não tem."""
    if not isinstance(url, str) or not url:
        return None
    scripts = str(REPO / "skills" / "build-page" / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    import prepare_page

    if not prepare_page.wiki_icon(url):
        return None
    nome = prepare_page.icon_name(url)
    return f"icons/{nome}" if (Path(home) / "cache" / "ds2" / "icons" / nome).is_file() else None


def completar_combate(home: Path, out: dict) -> dict:
    """Ícones e letras de escala do que já está no cache da wiki (sem rede): o equipamento como o prepare_page faz, e
    os nós de feitiços, dano e compras."""
    scripts = str(REPO / "skills" / "build-page" / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    import escala_wiki
    import prepare_page

    cache = Path(home) / "cache" / "ds2"
    try:
        icones = json.loads((cache / "icones.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        icones = {}
    icones = icones if isinstance(icones, dict) else {}

    def icone_de(nome: str) -> str | None:
        return icone_local(home, (icones.get(str(nome).strip().casefold()) or {}).get("url"))

    escala = escala_wiki.EscalaWiki(cache / "escala.json", fetch=None)
    so_cache = type("EscalaSoCache", (), {"letras": staticmethod(escala.letras_guardadas)})()
    if isinstance(out.get("equipamento"), dict):
        prepare_page.completar_equipamento(out["equipamento"], so_cache, icone_de)
    nos = []
    f = out.get("feiticos") or {}
    nos += [f.get("catalisador")] + [s.get("no") for s in f.get("lista", []) if isinstance(s, dict)]
    for d in out.get("dano") or []:
        nos += [d.get("arma")] + list(d.get("por_causa") or [])
    for c in out.get("compras") or []:
        nos += [c.get("item")]
    for no in nos:
        if isinstance(no, dict) and no.get("tipo") == "item" and no.get("nome") and not str(no.get("icone", "")).startswith("icons/"):
            icone = icone_de(no["nome"])
            if icone:
                no["icone"] = icone
            else:
                no.pop("icone", None)
    return out


def resumo_catalogo(home: Path, item: dict) -> dict:
    """O que o Catálogo mostra de um item: nome, categoria, requisito, ícone local e quantas fontes de cada tipo."""
    contagem = {}
    for f in item.get("fontes", []):
        contagem[f["tipo"]] = contagem.get(f["tipo"], 0) + 1
    icone = icone_local(home, item.get("icone"))
    return {"id": item["id"], "nome": item["nome"], "cat": item["cat"], "req": item.get("req", {}), "fontes": contagem,
            **({"icone": icone} if icone else {})}


def com_icones_locais(home: Path, valor):
    """Troca a URL de ícone da wiki de cada nó pelo arquivo do cache (a página só mostra ícone local)."""
    if isinstance(valor, list):
        return [com_icones_locais(home, v) for v in valor]
    if not isinstance(valor, dict):
        return valor
    out = {k: com_icones_locais(home, v) for k, v in valor.items() if k != "icone"}
    if "icone" in valor:
        icone = icone_local(home, valor["icone"])
        if icone:
            out["icone"] = icone
    return out


class Cenas:
    """Cena 3D por área: o que já está no cache e a extração em segundo plano (uma por área; o GET nunca extrai)."""

    def __init__(self, home: Path, extrair=None):
        self.home = Path(home)
        self.extrair = extrair  # (area, cache_dir) -> cena; None = ds2cena.extrair_cena com o jogo instalado
        self._estado: dict[str, str] = {}
        self._lock = threading.Lock()

    def dir(self, area: str) -> Path:
        return self.home / "cache" / "ds2" / "cena" / area

    def pronta(self, area: str) -> bytes | None:
        import ds2cena

        try:
            corpo = (self.dir(area) / "cena.json").read_bytes()
            versao = json.loads(corpo).get("versao")
        except (OSError, ValueError, AttributeError):
            return None
        return corpo if versao == ds2cena.CENA_VERSAO and (self.dir(area) / ds2cena.GEO).is_file() else None

    def estado(self, area: str) -> str | None:
        with self._lock:
            return self._estado.get(area)

    def iniciar(self, area: str) -> bool:
        with self._lock:
            if self._estado.get(area) == "extraindo":
                return False
            self._estado[area] = "extraindo"
        threading.Thread(target=self._rodar, args=(area,), daemon=True).start()
        return True

    def _rodar(self, area: str) -> None:
        try:
            if self.extrair:
                self.extrair(area, self.home / "cache" / "ds2")
            else:
                import ds2cena

                ds2cena.extrair_cena(area=area, cache_dir=self.home / "cache" / "ds2", forcar=self.pronta(area) is None)
            with self._lock:
                self._estado.pop(area, None)
        except Exception as err:  # jogo ausente, área sem modelos, formato inesperado
            with self._lock:
                self._estado[area] = f"{type(err).__name__}: {err}"[:200]


class Handler(BaseHTTPRequestHandler):
    home: Path = default_home()
    runner: Runner | None = None
    save: Path | None = None  # None = o save ativo do jogo (ds2save.find_save)
    steam_dirs: list | None = None  # None = pastas padrão da Steam
    mapa: "MapaVivo | None" = None
    cenas: "Cenas | None" = None
    catalogo: "Catalogo | None" = None
    server_version = "buildsmith"

    def log_message(self, *args):  # sem log no console (roda com pythonw)
        pass

    def _send(self, status: int, body: bytes, ctype: str, csp: str | None = None, extra: dict | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        for nome, valor in (extra or {}).items():
            self.send_header(nome, valor)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        if csp:
            self.send_header("Content-Security-Policy", csp)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, data, status: int = 200) -> None:
        self._send(status, json.dumps(data, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def _parts(self) -> list[str] | None:
        raw = urlsplit(self.path).path
        parts = [unquote(p) for p in raw.split("/") if p]
        if any(p in (".", "..") or "/" in p or "\\" in p for p in parts):
            return None
        return parts

    def _local_host(self) -> bool:
        """Barra DNS rebinding: o navegador tem que ter chamado 127.0.0.1 ou localhost."""
        port = self.server.server_address[1]
        return self.headers.get("Host") in {f"127.0.0.1:{port}", f"localhost:{port}"}

    def _trusted(self) -> bool:
        """POST só da própria página: Host e Origin locais + cabeçalho próprio (outro site não manda sem preflight)."""
        port = self.server.server_address[1]
        origin = self.headers.get("Origin")
        if origin and origin not in {f"http://127.0.0.1:{port}", f"http://localhost:{port}"}:
            return False
        return self._local_host() and self.headers.get("X-Buildsmith") == "1"

    def do_GET(self):  # noqa: N802 (nome exigido pelo http.server)
        parts = self._parts()
        if parts is None:
            return self._send(400, b"caminho invalido", "text/plain; charset=utf-8")
        if not self._local_host():
            return self._send(400, b"host invalido", "text/plain; charset=utf-8")
        if not parts:
            found = pages(self.home)
            if found and "lista" not in parse_qs(urlsplit(self.path).query):
                jogo, personagem, _ = principal(self.home, found)
                self.send_response(302)
                self.send_header("Location", f"/p/{jogo}/{personagem}/")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return None
            return self._index()
        if parts == ["api", "ping"]:
            return self._json({"app": "buildsmith", "ok": True, "rodar": self.runner is not None, "pid": os.getpid(),
                               "versao": VERSAO})
        if len(parts) == 3 and parts[0] == "api" and parts[2] == "personagens" and parts[1] == "ds2":
            return self._json(personagens(self.home, parts[1], self.save, self.steam_dirs))
        if parts == ["api", "ds2", "rota"]:
            return self._rota()
        if parts == ["api", "ds2", "vivo"]:
            return self._json(self.vivo.atual())
        if parts == ["api", "ds2", "vivo", "stream"]:
            return self._stream_vivo()
        if parts == ["api", "ds2", "catalogo"]:
            return self._catalogo()
        if len(parts) == 4 and parts[:2] == ["api", "ds2"] and parts[3] == "fontes" and SEGMENT.match(parts[2]):
            return self._fontes(parts[2])
        if len(parts) == 4 and parts[:2] == ["api", "ds2"] and parts[3] == "combate" and SEGMENT.match(parts[2]):
            return self._combate(parts[2])
        if len(parts) == 4 and parts[:2] == ["api", "ds2"] and parts[3] == "simular" and SEGMENT.match(parts[2]):
            return self._simular(parts[2])
        if len(parts) == 4 and parts[:2] == ["api", "ds2"] and parts[3] == "posicao" and SEGMENT.match(parts[2]):
            return self._posicao(parts[2])
        if len(parts) == 4 and parts[:2] == ["api", "ds2"] and parts[3] == "save" and SEGMENT.match(parts[2]):
            return self._save_vivo(parts[2])
        if len(parts) == 4 and parts[:2] == ["api", "ds2"] and parts[3] == "mundo" and SEGMENT.match(parts[2]):
            return self._mundo(parts[2])
        if len(parts) == 5 and parts[:3] == ["api", "ds2", "cena"] and AREA_OK.match(parts[3]):
            if parts[4] == "cena.json":
                return self._cena_json(parts[3])
            if parts[4] == "geo.bin":
                return self._cena_geo(parts[3])
        if (len(parts) == 6 and parts[:3] == ["api", "ds2", "cena"] and AREA_OK.match(parts[3]) and parts[4] == "tex"
                and TEX_OK.match(parts[5])):
            return self._cena_arquivo(parts[3], ["tex", parts[5]], "application/octet-stream")
        if len(parts) == 4 and parts[0] == "api" and parts[3] == "retrato" and all(SEGMENT.match(p) for p in parts[1:3]):
            foto = retrato.achar(self.home, parts[1], parts[2])
            if foto is None:
                return self._send(404, b"sem retrato", "text/plain; charset=utf-8")
            return self._send(200, foto.read_bytes(), retrato.TIPOS[foto.suffix[1:]])
        if len(parts) == 4 and parts[0] == "api" and all(SEGMENT.match(p) for p in parts[1:3]):
            if parts[3] == "estado":
                return self._json(read_state(self.home, parts[1], parts[2]))
            if parts[3] == "execucao" and self.runner is not None:
                desde = parse_qs(urlsplit(self.path).query).get("desde", ["-1"])[0]
                return self._json(self.runner.status(int(desde) if desde.lstrip("-").isdigit() else -1))
        if len(parts) >= 3 and parts[0] == "p" and all(SEGMENT.match(p) for p in parts[1:3]):
            if not urlsplit(self.path).path.endswith("/") and len(parts) == 3:
                self.send_response(301)
                self.send_header("Location", f"/p/{parts[1]}/{parts[2]}/")
                self.end_headers()
                return None
            return self._file(parts[1], parts[2], parts[3:])
        return self._send(404, b"nao encontrado", "text/plain; charset=utf-8")

    def do_POST(self):  # noqa: N802
        parts = self._parts()
        if not self._trusted():
            return self._send(403, b"origem recusada", "text/plain; charset=utf-8")
        if (parts and len(parts) == 4 and parts[0] == "api" and parts[3] in ("rodar", "cancelar")
                and self.runner is not None and all(SEGMENT.match(p) for p in parts[1:3])):
            return self._run(parts[1], parts[2], parts[3])
        if (parts and len(parts) == 4 and parts[0] == "api" and parts[3] in ("retrato", "retrato-print", "retrato-limpar")
                and all(SEGMENT.match(p) for p in parts[1:3])):
            return self._retrato(parts[1], parts[2], parts[3])
        if parts == ["api", "desligar"]:
            self._json({"ok": True})
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return None
        if parts and len(parts) == 5 and parts[:3] == ["api", "ds2", "cena"] and AREA_OK.match(parts[3]) and parts[4] == "extrair":
            return self._cena_extrair(parts[3])
        if (parts is None or len(parts) != 5 or parts[0] != "api" or parts[3] not in COLLECTIONS
                or not all(SEGMENT.match(p) for p in (parts[1], parts[2], parts[4]))):
            return self._send(400, b"caminho invalido", "text/plain; charset=utf-8")
        data = clean_doc(parts[3], parts[4], self._body())
        if data is None:
            return self._send(400, b"documento invalido", "text/plain; charset=utf-8")
        jogo, personagem, collection, doc_id = parts[1:]
        if collection == "quero" and data["marcado"]:
            quero = read_state(self.home, jogo, personagem)["quero"]
            marcados = sum(1 for k, v in quero.items() if k != doc_id and isinstance(v, dict) and v.get("marcado"))
            if marcados >= MAX_QUERO:
                return self._send(409, b"lista cheia", "text/plain; charset=utf-8")
        if collection == "metas" and data["ativa"]:
            metas = read_state(self.home, jogo, personagem)["metas"]
            ligadas = sum(1 for k, v in metas.items() if k != doc_id and isinstance(v, dict) and v.get("ativa"))
            if ligadas >= MAX_METAS:
                return self._send(409, b"metas demais", "text/plain; charset=utf-8")
        if collection == "pedidos":
            pedidos = read_state(self.home, jogo, personagem)["pedidos"]
            abertos = sum(1 for k, v in pedidos.items() if k != doc_id and isinstance(v, dict) and v.get("estado") == "na_fila")
            if abertos >= MAX_FILA:
                return self._send(409, b"fila cheia", "text/plain; charset=utf-8")
        return self._json(write_doc(self.home, jogo, personagem, collection, doc_id, data))

    def _stream_vivo(self):
        """Server-Sent Events: um `data: <json>` a cada leitura do jogo; termina quando o cliente sai."""
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.vivo.entrar()
        try:
            self.wfile.write(b"retry: 2000\n\n")
            self.wfile.flush()
            seq = -1
            while not self.vivo.parar.is_set():
                seq, valor = self.vivo.esperar(seq, 2.0)
                corpo = b": ainda aqui\n\n" if valor is None else ("data: " + json.dumps(valor, ensure_ascii=False) + "\n\n").encode("utf-8")
                self.wfile.write(corpo)
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
            pass  # cliente fechou a aba ou o OBS trocou de cena
        finally:
            self.vivo.sair()

    def _cena_json(self, area: str):
        pronta = self.cenas.pronta(area)
        if pronta is not None:
            return self._send(200, pronta, "application/json; charset=utf-8")
        estado = self.cenas.estado(area)
        if estado == "extraindo":
            return self._json({"estado": "extraindo"}, status=202)
        comando = f"python skills/ds2-save/scripts/ds2cena.py extrair --area {area}"
        if estado:
            return self._json({"erro": f"a extração falhou ({estado})", "comando": comando}, status=500)
        return self._json({"erro": "cena não extraída", "comando": comando}, status=404)

    def _cena_arquivo(self, area: str, rel: list[str], ctype: str):
        base = self.cenas.dir(area).resolve()
        target = base.joinpath(*rel).resolve()
        if base not in target.parents or not target.is_file():
            return self._send(404, b"nao encontrado", "text/plain; charset=utf-8")
        return self._send(200, target.read_bytes(), ctype)

    def _cena_geo(self, area: str):
        """geo.bin fica em gzip no cache: vai comprimido (o navegador abre) ou aberto aqui, se o cliente não aceitar."""
        import gzip
        import ds2cena

        alvo = self.cenas.dir(area) / ds2cena.GEO
        if not alvo.is_file():
            return self._send(404, b"nao encontrado", "text/plain; charset=utf-8")
        corpo = alvo.read_bytes()
        if "gzip" in (self.headers.get("Accept-Encoding") or ""):
            return self._send(200, corpo, "application/octet-stream", extra={"Content-Encoding": "gzip"})
        return self._send(200, gzip.decompress(corpo), "application/octet-stream")

    def _cena_extrair(self, area: str):
        self.cenas.iniciar(area)
        return self._json({"estado": "extraindo"}, status=202)

    def _posicao(self, personagem: str):
        try:
            p = self.mapa.posicao(personagem)
        except Exception as err:  # sem save, save sendo gravado, pycryptodome ausente
            return self._json({"erro": f"não consegui ler o save ({type(err).__name__})"}, status=503)
        if p is None:
            return self._json({"erro": "personagem não está no save"}, status=404)
        return self._json(p)

    def _save_vivo(self, personagem: str):
        try:
            v = self.mapa.ao_vivo(personagem)
        except Exception as err:  # sem save, save sendo gravado, pycryptodome ausente
            return self._json({"erro": f"não consegui ler o save ({type(err).__name__})"}, status=503)
        if v is None:
            return self._json({"erro": "personagem não está no save"}, status=404)
        return self._json(v)

    def _mundo(self, personagem: str):
        area = parse_qs(urlsplit(self.path).query).get("area", [""])[0]
        if not AREA_OK.match(area):
            return self._send(400, b"area invalida", "text/plain; charset=utf-8")
        try:
            m = self.mapa.estado_area(personagem, area)
        except Exception as err:  # sem save, sem o jogo para a área, pycryptodome ausente
            return self._json({"erro": f"não consegui ler o estado do mundo ({type(err).__name__})"}, status=503)
        if m is None:
            return self._json({"erro": "personagem não está no save"}, status=404)
        return self._json(m)

    def _rota(self):
        q = parse_qs(urlsplit(self.path).query)
        area = q.get("area", [""])[0]
        de, ate = coords(q.get("de", [""])[0]), coords(q.get("ate", [""])[0])
        if not AREA_OK.match(area) or de is None or ate is None:
            return self._send(400, b"area, de ou ate invalido", "text/plain; charset=utf-8")
        try:
            r = self.mapa.rota(area, de, ate)
        except Exception as err:  # jogo ausente, área sem navmesh
            return self._json({"erro": f"rota indisponível ({type(err).__name__})"}, status=503)
        return self._json({"area": area, "rota": r})

    def _indice_ou_espera(self):
        """Índice pronto, ou a resposta já mandada (202 montando / 500 com o erro)."""
        indice = self.catalogo.indice()
        if indice is not None:
            return indice
        estado = self.catalogo.estado()
        if estado in (None, "montando"):
            self.catalogo.iniciar()
            self._json({"estado": "montando"}, status=202)
            return None
        self._json({"erro": f"não consegui montar o catálogo ({estado})",
                    "comando": "python skills/ds2-save/scripts/ds2itens.py montar"}, status=500)
        return None

    def _catalogo(self):
        indice = self._indice_ou_espera()
        if indice is None:
            return None
        itens = sorted(indice["itens"].values(), key=lambda i: (i["cat"], i["nome"]))
        return self._json({"itens": [resumo_catalogo(self.home, i) for i in itens]})

    def _combate(self, personagem: str):
        indice = self.catalogo.indice()
        if indice is None:
            self.catalogo.iniciar()  # o melhor por código entra quando o índice ficar pronto
        try:
            r = self.mapa.combate(personagem, indice)
        except Exception as err:  # sem save, save sendo gravado, jogo ausente
            return self._json({"erro": f"não consegui calcular o combate ({type(err).__name__})"}, status=503)
        if r is None:
            return self._json({"erro": "personagem não está no save"}, status=404)
        return self._json(completar_combate(self.home, json.loads(json.dumps(r))))

    def _simular(self, personagem: str):
        import ds2save

        q = parse_qs(urlsplit(self.path).query)
        item, nivel, infusao = (q.get(k, [""])[0] for k in ("item", "nivel", "infusao"))
        if not (item.isdigit() and len(item) <= 10 and nivel.isdigit() and int(nivel) <= 10 and infusao.isdigit()
                and int(infusao) <= 9):
            return self._send(400, b"item, nivel ou infusao invalido", "text/plain; charset=utf-8")
        try:
            r = self.mapa.simular(personagem, int(item), int(nivel), int(infusao))
        except ds2save.SaveError as err:  # arma, nível ou infusão que o jogo não aceita
            return self._json({"erro": str(err)}, status=400)
        except Exception as err:  # sem save, save sendo gravado, jogo ausente
            return self._json({"erro": f"não consegui simular ({type(err).__name__})"}, status=503)
        if r is None:
            return self._json({"erro": "personagem não está no save"}, status=404)
        return self._json(r)

    def _fontes(self, personagem: str):
        item_id = parse_qs(urlsplit(self.path).query).get("item", [""])[0]
        if not item_id.isdigit() or len(item_id) > 10:
            return self._send(400, b"item invalido", "text/plain; charset=utf-8")
        indice = self._indice_ou_espera()
        if indice is None:
            return None
        item = indice["itens"].get(item_id)
        if item is None:
            return self._json({"erro": "item não está no catálogo"}, status=404)
        try:
            r = self.mapa.fontes(personagem, item, indice)
        except Exception as err:  # sem save, save sendo gravado, jogo ausente
            return self._json({"erro": f"não consegui calcular as fontes ({type(err).__name__})"}, status=503)
        if r is None:
            return self._json({"erro": "personagem não está no save"}, status=404)
        return self._json(com_icones_locais(self.home, r))

    def _body(self) -> dict | None:
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return None
        if not 0 <= length <= MAX_BODY:
            return None
        try:
            data = json.loads(self.rfile.read(length) or b"{}")
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None
        return data if isinstance(data, dict) else None

    def _retrato(self, jogo: str, personagem: str, acao: str):
        if acao == "retrato-limpar":
            retrato.limpar(self.home, jogo, personagem)
            return self._json({"ok": True})
        if acao == "retrato-print":
            shot = retrato.ultimo_print(self.steam_dirs)
            if shot is None:
                return self._send(404, b"nenhum print do DS2 na Steam", "text/plain; charset=utf-8")
            data = shot.read_bytes()
        else:
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                return self._send(400, b"tamanho invalido", "text/plain; charset=utf-8")
            if length > retrato.MAX_RETRATO:
                # Lê e descarta (até 16 MB) antes de responder: fechar com o corpo pela metade derruba a conexão no Windows.
                restante = min(length, 16 * 1024 * 1024)
                while restante > 0:
                    bloco = self.rfile.read(min(restante, 64 * 1024))
                    if not bloco:
                        break
                    restante -= len(bloco)
                self.close_connection = True
                return self._send(413, b"imagem maior que 2 MB", "text/plain; charset=utf-8")
            data = self.rfile.read(length) if length > 0 else b""
        try:
            retrato.gravar(self.home, jogo, personagem, data)
        except ValueError as err:
            status = 413 if "2 MB" in str(err) else 400
            return self._send(status, str(err).encode("utf-8"), "text/plain; charset=utf-8")
        return self._json({"ok": True})

    def _run(self, jogo: str, personagem: str, acao: str):
        if acao == "cancelar":
            self.runner.cancel()
            return self._json(self.runner.status())
        data = self._body()
        modo = (data or {}).get("modo")
        if modo not in MODOS:
            return self._send(400, b"modo invalido", "text/plain; charset=utf-8")
        try:
            self.runner.start(modo, build_prompt(self.home, jogo, personagem, modo), {"jogo": jogo, "personagem": personagem})
        except Busy:
            return self._json(self.runner.status(), status=409)
        return self._json(self.runner.status())

    def _file(self, jogo: str, personagem: str, rest: list[str]):
        root = (Path(self.home) / "paginas" / jogo / personagem).resolve()
        target = (root / Path(*rest)).resolve() if rest else root / "index.html"
        if len(rest) == 2 and rest[0] == "icons" and ICONE_OK.match(rest[1]) and not target.is_file():
            # ícone de item do Catálogo que a página ainda não copiou: o mesmo arquivo do cache de ícones da wiki
            target = Path(self.home) / "cache" / jogo / "icons" / rest[1]
            if not target.is_file():
                return self._send(404, b"nao encontrado", "text/plain; charset=utf-8")
            return self._send(200, target.read_bytes(), mimetypes.guess_type(target.name)[0] or "application/octet-stream")
        if root not in target.parents and target != root / "index.html" or not target.is_file():
            return self._send(404, b"nao encontrado", "text/plain; charset=utf-8")
        body = target.read_bytes()
        if target.name in ("index.html", "overlay.html"):  # a página e o minimapa: mesmo CSP (script só inline/próprio)
            return self._send(200, DOCTYPE + body + b"</body></html>", "text/html; charset=utf-8", CSP_PAGINA)
        ctype = TIPOS_ESTATICOS.get(target.suffix.lower()) or mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype == "application/json":
            ctype += "; charset=utf-8"
        return self._send(200, body, ctype)

    def _index(self):
        esc = html.escape
        items = "".join(f'<li><a href="/p/{esc(j)}/{esc(p)}/">{esc(p.replace("-", " ").title())}</a> <small>({esc(j)})</small></li>'
                        for j, p, _ in pages(self.home)) or "<li>Nenhuma página ainda. Rode /buildsmith:build ds2.</li>"
        body = ("<title>Forja de Build</title><style>body{background:#101013;color:#b4b2b0;font:15px Helvetica,Arial,sans-serif;"
                "padding:32px 16px}a{color:#ab966f}h1{color:#fff;font-family:Georgia,serif;font-weight:400}</style>"
                f"<h1>Forja de Build</h1><ul>{items}</ul>")
        return self._send(200, DOCTYPE + body.encode("utf-8") + b"</body></html>", "text/html; charset=utf-8", CSP_INICIO)


def make_server(home: Path, port: int = PORT, runner: Runner | None = None, save=None, steam_dirs=None,
                mapa: MapaVivo | None = None, extrair_cena=None, catalogo: Catalogo | None = None,
                vivo: FluxoVivo | None = None) -> ThreadingHTTPServer:
    runner = runner or Runner(cwd=Path(home), log_path=Path(home) / "execucoes" / "ultima.jsonl")
    mapa = mapa or MapaVivo(home, save)
    handler = type("BuildsmithHandler", (Handler,), {"home": Path(home), "runner": runner, "save": save,
                                                     "steam_dirs": steam_dirs, "mapa": mapa,
                                                     "cenas": Cenas(home, extrair_cena),
                                                     "catalogo": catalogo or Catalogo(home),
                                                     "vivo": vivo or FluxoVivo(area=mapa.area_por_nome)})
    httpd = ThreadingHTTPServer(("127.0.0.1", port), handler)
    desligar = httpd.shutdown

    def shutdown():  # streams abertos param junto com o servidor
        handler.vivo.parar.set()
        desligar()
    httpd.shutdown = shutdown
    return httpd


def running(port: int = PORT) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/ping", timeout=1) as resp:
            return json.loads(resp.read()).get("app") == "buildsmith"
    except OSError:
        return False


def slug_do_jogador(home: Path, vivo, save=None) -> str:
    """Página do personagem carregado no jogo (nome lido da memória, cruzado com o save); sem leitura, a mais recente."""
    nome = (vivo.atual() or {}).get("nome")
    if nome:
        try:
            import ds2save
            for p in ds2save.personagens(Path(save) if save else ds2save.find_save()):
                if p["nome"] == nome and (Path(home) / "paginas" / "ds2" / p["slug"]).is_dir():
                    return p["slug"]
        except Exception:  # save sendo gravado: fica a página mais recente
            pass
    found = pages(home)
    return principal(home, found)[1] if found else ""


def latest_page_url(home: Path, port: int) -> str:
    found = pages(home)
    if not found:
        return f"http://127.0.0.1:{port}/"
    jogo, personagem, _ = principal(home, found)
    return f"http://127.0.0.1:{port}/p/{jogo}/{personagem}/"


def main(argv=None) -> int:
    sys.stdout.reconfigure(encoding="utf-8") if hasattr(sys.stdout, "reconfigure") else None
    parser = argparse.ArgumentParser(prog="serve")
    parser.add_argument("--home", default=str(default_home()))
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--sem-overlay", action="store_true", help="não abre o minimapa por cima do jogo")
    parser.add_argument("--open", action="store_true",
                        help="atualiza (git pull, servidor e páginas: app/abrir.py) e abre a página mais recente")
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("parar", help="desliga o servidor que está rodando (funciona no Windows)")
    sub.add_parser("reiniciar", help="desliga e sobe de novo em segundo plano, com o código do disco")
    for name in ("estado", "responder", "confirmar"):
        p = sub.add_parser(name)
        p.add_argument("--home", default=str(default_home()))
        p.add_argument("--jogo", default="ds2")
        p.add_argument("--personagem", required=True)
    sub.choices["responder"].add_argument("--pedido", required=True)
    sub.choices["responder"].add_argument("--item", help="id do item em 'Onde pegar' (vazio = sem fonte)")
    sub.choices["confirmar"].add_argument("--passo", required=True)
    sub.choices["confirmar"].add_argument("--resultado", choices=("sim", "nao"), required=True)
    args = parser.parse_args(argv)
    home = Path(args.home)

    if args.cmd in ("parar", "reiniciar"):
        if not abrir.parar(args.port):
            print(json.dumps({"error": f"não consegui desligar o servidor da porta {args.port}"}, ensure_ascii=False))
            return 1
        if args.cmd == "parar":
            print(json.dumps({"ok": True, "parado": True}, ensure_ascii=False))
            return 0
        ok = abrir.subir(home, args.port)
        print(json.dumps({"ok": ok, "url": latest_page_url(home, args.port)}, ensure_ascii=False))
        return 0 if ok else 1
    if args.open and not args.cmd:  # atalho antigo (serve.py --open): passa pelo abridor e já abre atualizado
        return abrir.main(["--home", str(home), "--port", str(args.port)])

    if args.cmd:
        who = slug(args.personagem)
        if not SEGMENT.match(args.jogo) or not SEGMENT.match(who):
            parser.error("--jogo e --personagem precisam virar um nome simples (letras, números e -)")
        ids = [v for v in (getattr(args, "pedido", None), getattr(args, "item", None), getattr(args, "passo", None)) if v]
        if not all(SEGMENT.match(v) for v in ids):
            parser.error("--pedido, --item e --passo são ids da página (letras minúsculas, números e -)")
        state = read_state(home, args.jogo, who)
        # Só responde o que a página pediu e só confirma o que ela marcou: a CLI não cria entrada nova.
        if args.cmd == "responder":
            if args.pedido not in state["pedidos"]:
                print(json.dumps({"error": f"não há pedido {args.pedido} na fila"}, ensure_ascii=False))
                return 1
            write_doc(home, args.jogo, who, "pedidos", args.pedido,
                      {"estado": "respondido", "item_id": args.item or None, "respondido_em": now()}, merge=True)
        elif args.cmd == "confirmar":
            if args.passo not in state["feitos"]:
                print(json.dumps({"error": f"o passo {args.passo} não está marcado na página"}, ensure_ascii=False))
                return 1
            write_doc(home, args.jogo, who, "feitos", args.passo, {"confirmado": args.resultado == "sim"}, merge=True)
        print(json.dumps(read_state(home, args.jogo, who), ensure_ascii=False, indent=2))
        return 0

    if running(args.port):
        if args.open:
            webbrowser.open(latest_page_url(home, args.port))
        return 0
    httpd = make_server(home, args.port)
    if not args.sem_overlay and os.name == "nt":  # minimapa e overlay grande por cima do jogo (app/overlay.py)
        import overlay

        def avisa(texto: str) -> None:
            with (home / "execucoes" / "overlay.log").open("a", encoding="utf-8") as fh:
                fh.write(f"{datetime.now():%Y-%m-%d %H:%M:%S}  {texto}\n")
        (home / "execucoes").mkdir(parents=True, exist_ok=True)
        vivo = httpd.RequestHandlerClass.vivo
        overlay.iniciar(home, args.port, lambda: slug_do_jogador(home, vivo), avisa)
    if args.open:
        threading.Timer(0.6, lambda: webbrowser.open(latest_page_url(home, args.port))).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
