#!/usr/bin/env python3
"""Servidor local do buildsmith.

Mostra as páginas de ~/.buildsmith/paginas/<jogo>/<personagem>/ e guarda o que a página grava
(fila de pesquisa, fogueiras de feito, seleção de feitiços) em ~/.buildsmith/estado/<jogo>/<personagem>.json.
Só biblioteca padrão. Escuta apenas em 127.0.0.1.

  pythonw serve.py --open          sobe o servidor (ou reaproveita o que já está de pé) e abre o navegador
  python serve.py estado ...       imprime o estado de um personagem (usado pela skill)
  python serve.py responder ...    marca um pedido da fila como respondido
  python serve.py confirmar ...    grava a confirmação de um passo marcado como feito

Os botões "Atualizar plano" e "Responder fila" da página rodam a skill sem janela (claude -p) pelo runner.py.
O mapa da página pergunta a posição do personagem (relida do save) e a rota pelo chão até um ponto.
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

import retrato
from runner import Busy, Runner

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "skills" / "ds2-save" / "scripts"))

PORT = 8642
SEGMENT = re.compile(r"^[a-z0-9][a-z0-9._-]{0,180}$")
GAME_OK = re.compile(r"^[a-z0-9]+$")
COLLECTIONS = {"feitos", "pedidos", "config"}
MODOS = {"plano", "fila"}
MAX_BODY = 4 * 1024
AREA_OK = re.compile(r"^m\d\d_\d\d_\d\d_\d\d$")
COORD_MAX = 10000.0
AREAS_EM_MEMORIA = 4
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
    state = {"feitos": {}, "pedidos": {}, "config": {}}
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


class MapaVivo:
    """Posição do personagem (relê o save só quando o arquivo muda) e rota pelo chão (grafo do navmesh em memória)."""

    def __init__(self, home: Path, save=None, carregar_area=None):
        self.home, self.save = Path(home), save
        self.carregar_area = carregar_area  # área -> dados com malhas; None = jogo instalado + cache de ~/.buildsmith
        self._save = (None, {})
        self._areas: OrderedDict = OrderedDict()
        self._lock = threading.Lock()

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
        return ds2mapa.rota(dados, de, ate, grafo)


class Handler(BaseHTTPRequestHandler):
    home: Path = default_home()
    runner: Runner | None = None
    save: Path | None = None  # None = o save ativo do jogo (ds2save.find_save)
    steam_dirs: list | None = None  # None = pastas padrão da Steam
    mapa: "MapaVivo | None" = None
    server_version = "buildsmith"

    def log_message(self, *args):  # sem log no console (roda com pythonw)
        pass

    def _send(self, status: int, body: bytes, ctype: str, csp: str | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
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
                jogo, personagem, _ = max(found, key=lambda x: x[2])
                self.send_response(302)
                self.send_header("Location", f"/p/{jogo}/{personagem}/")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return None
            return self._index()
        if parts == ["api", "ping"]:
            return self._json({"app": "buildsmith", "ok": True, "rodar": self.runner is not None})
        if len(parts) == 3 and parts[0] == "api" and parts[2] == "personagens" and parts[1] == "ds2":
            return self._json(personagens(self.home, parts[1], self.save, self.steam_dirs))
        if parts == ["api", "ds2", "rota"]:
            return self._rota()
        if len(parts) == 4 and parts[:2] == ["api", "ds2"] and parts[3] == "posicao" and SEGMENT.match(parts[2]):
            return self._posicao(parts[2])
        if len(parts) == 5 and parts[:3] == ["api", "ds2", "cena"] and AREA_OK.match(parts[3]):
            if parts[4] == "cena.json":
                return self._cena_json(parts[3])
            if parts[4] == "geo.bin":
                return self._cena_geo(parts[3])
        if len(parts) == 6 and parts[:3] == ["api", "ds2", "cena"] and AREA_OK.match(parts[3]) and parts[4] == "tex" and SEGMENT.match(parts[5]):
            return self._cena_tex(parts[3], parts[5])
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
        if collection == "pedidos":
            pedidos = read_state(self.home, jogo, personagem)["pedidos"]
            abertos = sum(1 for k, v in pedidos.items() if k != doc_id and isinstance(v, dict) and v.get("estado") == "na_fila")
            if abertos >= MAX_FILA:
                return self._send(409, b"fila cheia", "text/plain; charset=utf-8")
        return self._json(write_doc(self.home, jogo, personagem, collection, doc_id, data))

    def _cena_dir(self, area: str) -> Path:
        return (Path(self.home) / "cache" / "ds2" / "cena" / area).resolve()

    def _cena_json(self, area: str):
        import ds2cena
        area_dir = self._cena_dir(area)
        cena_path = area_dir / "cena.json"
        if not cena_path.is_file():
            try:
                ds2cena.extrair_cena(area=area, cache_dir=self.home / "cache" / "ds2")
            except Exception as err:
                return self._json({"erro": f"cena nao encontrada ({type(err).__name__})"}, status=404)
        if not cena_path.is_file():
            return self._send(404, b"cena nao encontrada", "text/plain; charset=utf-8")
        return self._send(200, cena_path.read_bytes(), "application/json; charset=utf-8")

    def _cena_geo(self, area: str):
        geo_path = self._cena_dir(area) / "geo.bin"
        if not geo_path.is_file():
            return self._send(404, b"geometria nao encontrada", "text/plain; charset=utf-8")
        return self._send(200, geo_path.read_bytes(), "application/octet-stream")

    def _cena_tex(self, area: str, arquivo: str):
        tex_dir = (self._cena_dir(area) / "tex").resolve()
        target = (tex_dir / arquivo).resolve()
        if tex_dir not in target.parents or not target.is_file():
            return self._send(404, b"textura nao encontrada", "text/plain; charset=utf-8")
        return self._send(200, target.read_bytes(), "application/octet-stream")

    def _cena_extrair(self, area: str):
        import ds2cena
        try:
            cena = ds2cena.extrair_cena(area=area, cache_dir=self.home / "cache" / "ds2", forcar=True)
            return self._json({"ok": True, "area": area, "instancias": len(cena.get("instancias", []))})
        except Exception as err:
            return self._json({"erro": f"falha na extracao ({type(err).__name__}: {err})"}, status=500)

    def _posicao(self, personagem: str):
        try:
            p = self.mapa.posicao(personagem)
        except Exception as err:  # sem save, save sendo gravado, pycryptodome ausente
            return self._json({"erro": f"não consegui ler o save ({type(err).__name__})"}, status=503)
        if p is None:
            return self._json({"erro": "personagem não está no save"}, status=404)
        return self._json(p)

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
        if root not in target.parents and target != root / "index.html" or not target.is_file():
            return self._send(404, b"nao encontrado", "text/plain; charset=utf-8")
        body = target.read_bytes()
        if target.name == "index.html":
            return self._send(200, DOCTYPE + body + b"</body></html>", "text/html; charset=utf-8", CSP_PAGINA)
        ctype = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
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
                mapa: MapaVivo | None = None) -> ThreadingHTTPServer:
    runner = runner or Runner(cwd=Path(home), log_path=Path(home) / "execucoes" / "ultima.jsonl")
    handler = type("BuildsmithHandler", (Handler,), {"home": Path(home), "runner": runner, "save": save,
                                                     "steam_dirs": steam_dirs, "mapa": mapa or MapaVivo(home, save)})
    return ThreadingHTTPServer(("127.0.0.1", port), handler)


def running(port: int = PORT) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/ping", timeout=1) as resp:
            return json.loads(resp.read()).get("app") == "buildsmith"
    except OSError:
        return False


def latest_page_url(home: Path, port: int) -> str:
    found = pages(home)
    if not found:
        return f"http://127.0.0.1:{port}/"
    jogo, personagem, _ = max(found, key=lambda x: x[2])
    return f"http://127.0.0.1:{port}/p/{jogo}/{personagem}/"


def main(argv=None) -> int:
    sys.stdout.reconfigure(encoding="utf-8") if hasattr(sys.stdout, "reconfigure") else None
    parser = argparse.ArgumentParser(prog="serve")
    parser.add_argument("--home", default=str(default_home()))
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--open", action="store_true", help="abre a página mais recente no navegador padrão")
    sub = parser.add_subparsers(dest="cmd")
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
    if args.open:
        threading.Timer(0.6, lambda: webbrowser.open(latest_page_url(home, args.port))).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
