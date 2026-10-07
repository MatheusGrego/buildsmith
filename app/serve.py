#!/usr/bin/env python3
"""Servidor local do buildsmith.

Mostra as páginas de ~/.buildsmith/paginas/<jogo>/<personagem>/ e guarda o que a página grava
(fila de pesquisa, fogueiras de feito, seleção de feitiços) em ~/.buildsmith/estado/<jogo>/<personagem>.json.
Só biblioteca padrão. Escuta apenas em 127.0.0.1.

  pythonw serve.py --open          sobe o servidor (ou reaproveita o que já está de pé) e abre o navegador
  python serve.py estado ...       imprime o estado de um personagem (usado pela skill)
  python serve.py responder ...    marca um pedido da fila como respondido
  python serve.py confirmar ...    grava a confirmação de um passo marcado como feito
"""
import argparse
import json
import mimetypes
import os
import re
import sys
import threading
import unicodedata
import urllib.request
import webbrowser
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

PORT = 8642
SEGMENT = re.compile(r"^[a-z0-9][a-z0-9._-]{0,180}$")
COLLECTIONS = {"feitos", "pedidos", "config"}
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
    if path.exists():
        state.update(json.loads(path.read_text(encoding="utf-8")))
    return state


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


def pages(home: Path) -> list[tuple[str, str, float]]:
    found = []
    for plan in sorted((Path(home) / "paginas").glob("*/*/plano.json")):
        found.append((plan.parent.parent.name, plan.parent.name, plan.stat().st_mtime))
    return found


class Handler(BaseHTTPRequestHandler):
    home: Path = default_home()
    server_version = "buildsmith"

    def log_message(self, *args):  # sem log no console (roda com pythonw)
        pass

    def _send(self, status: int, body: bytes, ctype: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
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

    def do_GET(self):  # noqa: N802 (nome exigido pelo http.server)
        parts = self._parts()
        if parts is None:
            return self._send(400, b"caminho invalido", "text/plain; charset=utf-8")
        if not parts:
            return self._index()
        if parts == ["api", "ping"]:
            return self._json({"app": "buildsmith", "ok": True})
        if len(parts) == 4 and parts[0] == "api" and parts[3] == "estado" and all(SEGMENT.match(p) for p in parts[1:3]):
            return self._json(read_state(self.home, parts[1], parts[2]))
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
        if parts == ["api", "desligar"]:
            self._json({"ok": True})
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return None
        if (parts is None or len(parts) != 5 or parts[0] != "api" or parts[3] not in COLLECTIONS
                or not all(SEGMENT.match(p) for p in (parts[1], parts[2], parts[4]))):
            return self._send(400, b"caminho invalido", "text/plain; charset=utf-8")
        length = int(self.headers.get("Content-Length") or 0)
        if length > 64 * 1024:
            return self._send(413, b"grande demais", "text/plain; charset=utf-8")
        try:
            data = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            return self._send(400, b"json invalido", "text/plain; charset=utf-8")
        if not isinstance(data, dict):
            return self._send(400, b"esperava objeto", "text/plain; charset=utf-8")
        return self._json(write_doc(self.home, parts[1], parts[2], parts[3], parts[4], data))

    def _file(self, jogo: str, personagem: str, rest: list[str]):
        root = (Path(self.home) / "paginas" / jogo / personagem).resolve()
        target = (root / Path(*rest)).resolve() if rest else root / "index.html"
        if root not in target.parents and target != root / "index.html" or not target.is_file():
            return self._send(404, b"nao encontrado", "text/plain; charset=utf-8")
        body = target.read_bytes()
        if target.name == "index.html":
            return self._send(200, DOCTYPE + body + b"</body></html>", "text/html; charset=utf-8")
        ctype = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype == "application/json":
            ctype += "; charset=utf-8"
        return self._send(200, body, ctype)

    def _index(self):
        items = "".join(f'<li><a href="/p/{j}/{p}/">{p.replace("-", " ").title()}</a> <small>({j})</small></li>'
                        for j, p, _ in pages(self.home)) or "<li>Nenhuma página ainda. Rode /buildsmith:build ds2.</li>"
        html = ("<title>Forja de Build</title><style>body{background:#101013;color:#b4b2b0;font:15px Helvetica,Arial,sans-serif;"
                "padding:32px 16px}a{color:#ab966f}h1{color:#fff;font-family:Georgia,serif;font-weight:400}</style>"
                f"<h1>Forja de Build</h1><ul>{items}</ul>")
        return self._send(200, DOCTYPE + html.encode("utf-8") + b"</body></html>", "text/html; charset=utf-8")


def make_server(home: Path, port: int = PORT) -> ThreadingHTTPServer:
    handler = type("BuildsmithHandler", (Handler,), {"home": Path(home)})
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
        if args.cmd == "responder":
            write_doc(home, args.jogo, who, "pedidos", args.pedido,
                      {"estado": "respondido", "item_id": args.item or None, "respondido_em": now()}, merge=True)
        elif args.cmd == "confirmar":
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
