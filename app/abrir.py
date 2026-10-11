#!/usr/bin/env python3
"""Abre a Forja de Build sempre atualizada. É o que o atalho da área de trabalho roda (e o `serve.py --open`).

1. `git pull --ff-only` no repositório (com alteração local, sem git ou sem rede: segue com o código que tem);
2. servidor: se o que está rodando é de outro código (ou de antes desta versão), desliga e sobe o novo;
3. páginas: quando o código mudou, refaz cada ~/.buildsmith/paginas/<jogo>/<personagem>/ a partir do plano.json
   que já está lá (prepare_page: nenhum Claude, nenhum token);
4. abre a página mais recente no navegador.

As fogueiras acesas e as áreas liberadas/bloqueadas a página lê ao vivo do save, pelo servidor.
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.request
import webbrowser
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PORT = 8642
CODIGO = ("app/*.py", "skills/*/scripts/*.py", "skills/build-page/template/*", "skills/build-page/template/vendor/*",
          "games/ds2/*.json")
SEM_JANELA = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def versao_codigo(repo: Path = REPO) -> str:
    """Impressão digital do código que monta e serve a página: muda a cada pull que mexe em algo que importa."""
    h = hashlib.sha1()
    for padrao in CODIGO:
        for p in sorted(repo.glob(padrao)):
            if p.is_file():
                h.update(p.relative_to(repo).as_posix().encode())
                h.update(p.read_bytes().replace(b"\r\n", b"\n"))  # CRLF do Windows não conta como mudança
    return h.hexdigest()[:12]


def puxar(repo: Path = REPO) -> str:
    """git pull que só avança. Nunca mexe em alteração local."""
    if not (repo / ".git").exists():
        return "sem git: segue com o código que tem"

    def git(*args):
        return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, timeout=90,
                              creationflags=SEM_JANELA)
    try:
        if git("status", "--porcelain", "--untracked-files=no").stdout.strip():
            return "tem alteração local: pull pulado"
        r = git("pull", "--ff-only")
    except (OSError, subprocess.TimeoutExpired) as err:
        return f"git indisponível ({type(err).__name__}): segue com o código que tem"
    linhas = (r.stdout or r.stderr).strip().splitlines()
    if r.returncode != 0:
        return "pull falhou: " + (linhas[-1] if linhas else f"código {r.returncode}")
    return linhas[-1] if linhas else "ok"


def ping(port: int = PORT) -> dict | None:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/ping", timeout=1.5) as resp:
            dados = json.loads(resp.read())
        return dados if dados.get("app") == "buildsmith" else None
    except (OSError, ValueError):
        return None


def pid_do_netstat(texto: str, port: int) -> int | None:
    """PID que escuta 127.0.0.1:<port> na saída do `netstat -ano` do Windows."""
    for linha in texto.splitlines():
        partes = linha.split()
        if len(partes) >= 5 and partes[0].upper() == "TCP" and partes[1].endswith(f":{port}") and partes[3].upper() in ("LISTENING", "ESCUTANDO"):
            if partes[-1].isdigit():
                return int(partes[-1])
    return None


def pid_na_porta(port: int) -> int | None:
    try:
        if os.name == "nt":
            out = subprocess.run(["netstat", "-ano", "-p", "TCP"], capture_output=True, text=True, timeout=10,
                                 creationflags=SEM_JANELA).stdout
            return pid_do_netstat(out, port)
        out = subprocess.run(["lsof", "-ti", f"tcp:{port}", "-sTCP:LISTEN"], capture_output=True, text=True, timeout=10).stdout
        return int(out.split()[0]) if out.split() else None
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None


def matar(pid: int) -> None:
    if os.name == "nt":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True, creationflags=SEM_JANELA)
    else:
        import signal
        os.kill(pid, signal.SIGTERM)


def _esperar(condicao, segundos: float) -> bool:
    fim = time.time() + segundos
    while time.time() < fim:
        if condicao():
            return True
        time.sleep(0.15)
    return condicao()


def parar(port: int = PORT) -> bool:
    """Desliga o servidor: pelo próprio servidor (/api/desligar); se ele responde mas não sai, pelo processo dele.

    Só mata processo que se identificou como buildsmith (nunca outro programa na porta, nunca este processo)."""
    info = ping(port)
    if info is None:
        return pid_na_porta(port) is None  # porta livre; ocupada por outro programa = não mexe
    req = urllib.request.Request(f"http://127.0.0.1:{port}/api/desligar", data=b"{}", method="POST",
                                 headers={"Content-Type": "application/json", "X-Buildsmith": "1"})
    try:
        urllib.request.urlopen(req, timeout=3).read()
    except OSError:
        pass
    if _esperar(lambda: ping(port) is None, 6):
        return True
    pid = info.get("pid") or pid_na_porta(port)
    if pid and int(pid) != os.getpid():
        matar(int(pid))
    return _esperar(lambda: ping(port) is None, 5)


def _python(janela: bool) -> str:
    """python.exe (com console) ou pythonw.exe (sem janela) ao lado do que está rodando."""
    exe = Path(sys.executable)
    if os.name == "nt":
        alvo = exe.with_name("python.exe" if janela else "pythonw.exe")
        if alvo.exists():
            return str(alvo)
    return str(exe)


def subir(home: Path, port: int = PORT) -> bool:
    """Sobe o servidor em segundo plano, solto deste processo (fecha a janela e ele continua)."""
    flags = 0
    if os.name == "nt":
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    subprocess.Popen([_python(False), str(REPO / "app" / "serve.py"), "--home", str(home), "--port", str(port)],
                     cwd=str(REPO), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     creationflags=flags, close_fds=True, start_new_session=os.name != "nt")
    return _esperar(lambda: ping(port) is not None, 20)


def _preparar_padrao(plano: Path, jogo: str) -> dict:
    script = REPO / "skills" / "build-page" / "scripts" / "prepare_page.py"
    r = subprocess.run([_python(True), str(script), str(plano), str(plano.parent), "--jogo", jogo],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=1800,
                       creationflags=SEM_JANELA, env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    try:
        return json.loads(r.stdout)
    except ValueError:
        return {"error": (r.stderr or r.stdout).strip().splitlines()[-1] if (r.stderr or r.stdout).strip() else f"código {r.returncode}"}


def refazer_paginas(home: Path, versao: str, avisa=print, forcar: bool = False, preparar=_preparar_padrao) -> list[str]:
    """Refaz as páginas geradas com outro código, a partir do plano.json de cada uma. Devolve as que refez."""
    marca = home / "app" / "paginas.json"
    try:
        feitas = json.loads(marca.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        feitas = {}
    refeitas = []
    for plano in sorted((home / "paginas").glob("*/*/plano.json")):
        chave = plano.parent.relative_to(home / "paginas").as_posix()
        if not forcar and feitas.get(chave) == versao:
            continue
        jogo = plano.parent.parent.name
        avisa(f"refazendo a página {chave} com o código novo (sem Claude, sem token)...")
        out = preparar(plano, jogo)
        if out.get("error"):
            avisa(f"  não deu ({out['error']}): fica a página de antes")
            continue
        for aviso in out.get("avisos", [])[:5]:
            avisa(f"  aviso: {aviso}")
        feitas[chave] = versao
        refeitas.append(chave)
    marca.parent.mkdir(parents=True, exist_ok=True)
    marca.write_text(json.dumps(feitas, ensure_ascii=False, indent=2), encoding="utf-8")
    return refeitas


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(prog="abrir", description=__doc__.splitlines()[0])
    parser.add_argument("--home", default=os.environ.get("BUILDSMITH_HOME", str(Path.home() / ".buildsmith")))
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--sem-pull", action="store_true", help="não roda git pull")
    parser.add_argument("--sem-navegador", action="store_true", help="não abre o navegador")
    parser.add_argument("--refazer", action="store_true", help="refaz todas as páginas mesmo sem código novo")
    args = parser.parse_args(argv)
    home = Path(args.home)
    log = home / "execucoes" / "abrir.log"
    log.parent.mkdir(parents=True, exist_ok=True)

    def avisa(texto: str) -> None:
        linha = f"{datetime.now():%Y-%m-%d %H:%M:%S}  {texto}"
        try:
            print(texto, flush=True)
        except (OSError, ValueError):  # pythonw: sem console
            pass
        with log.open("a", encoding="utf-8") as fh:
            fh.write(linha + "\n")

    avisa("Forja de Build: conferindo atualização...")
    if not args.sem_pull:
        avisa("git pull: " + puxar())
    versao = versao_codigo()
    info = ping(args.port)
    if info is not None and info.get("versao") != versao:
        avisa("servidor rodando com o código antigo: desligando...")
        if not parar(args.port):
            avisa(f"não consegui desligar o servidor da porta {args.port}; feche o pythonw no Gerenciador de Tarefas")
            return 1
        _esperar(lambda: pid_na_porta(args.port) is None, 8)  # o processo antigo solta a porta ao sair
    refazer_paginas(home, versao, avisa, forcar=args.refazer)
    if ping(args.port) is None:
        avisa("subindo o servidor...")
        if not subir(home, args.port):
            avisa(f"o servidor não respondeu na porta {args.port}; veja {log}")
            return 1
    sys.path.insert(0, str(REPO / "app"))
    import serve  # depois do pull: o código novo

    url = serve.latest_page_url(home, args.port)
    if not args.sem_navegador:
        webbrowser.open(url)
    avisa(f"pronto: {url}")
    return 0


if __name__ == "__main__":
    codigo = main()
    if sys.stdout and sys.stdout.isatty() and not sys.argv[1:]:  # janela do atalho: dá tempo de ler
        time.sleep(4 if codigo else 2)
    sys.exit(codigo)
