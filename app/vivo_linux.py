#!/usr/bin/env python3
"""Ajudante do estado ao vivo no Linux: abre o DS2 pela Steam e entrega a leitura da memória ao servidor.

O Linux (kernel.yama.ptrace_scope = 1, o padrão) só deixa ler a memória de um processo quem é ancestral dele, e o
servidor do buildsmith não é. Este ajudante é: nas opções de inicialização da Steam ele vem antes do resto, roda o
comando do jogo como filho e vira "subreaper" (o processo do jogo, que o Wine solta do pai, fica pendurado nele). Quando
o DarkSoulsII.exe aparece, ele abre o /proc/<pid>/mem e entrega o descritor a quem pedir no socket do ds2mem (só o
mesmo usuário). Nada é escrito no jogo; o servidor só lê.

Com o Proton atual o ajudante sobra: o jogo roda no contêiner do Steam Linux Runtime (bwrap, um user namespace criado
pelo usuário), e o Yama deixa ler quem tem CAP_SYS_PTRACE nesse namespace, o que o dono dele tem (conferido em
2026-10-30: os processos de dentro do contêiner abrem direto, os de fora não). Ele fica para jogo fora do contêiner.

Opções de inicialização da Steam (DS2 SotFS → Propriedades → Geral), na frente do que já estiver lá:

    python3 /caminho/do/buildsmith/app/vivo_linux.py %command%
    python3 /caminho/do/buildsmith/app/vivo_linux.py bash -c 'exec "${@/DarkSoulsII.exe/ds2sc_launcher.exe}"' -- %command%

O jogo abre igual com ou sem o ajudante: se algo aqui falhar, ele só registra em ~/.buildsmith/execucoes/vivo_linux.log.
"""
import ctypes
import json
import os
import signal
import socket
import struct
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "ds2-save" / "scripts"))
import ds2mem  # noqa: E402

JOGO = "DarkSoulsII.exe"
PR_SET_CHILD_SUBREAPER = 36
LOG = Path.home() / ".buildsmith" / "execucoes" / "vivo_linux.log"


def avisa(texto: str) -> None:
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as fh:
            fh.write(f"{datetime.now():%Y-%m-%d %H:%M:%S}  {texto}\n")
    except OSError:
        pass


def descendente(pid: int, ancestral: int, proc_dir="/proc") -> bool:
    while pid > 1:
        if pid == ancestral:
            return True
        try:
            status = (Path(proc_dir) / str(pid) / "status").read_text(encoding="utf-8", errors="replace")
            pid = int(next(linha.split()[1] for linha in status.splitlines() if linha.startswith("PPid:")))
        except (OSError, StopIteration, ValueError, IndexError):
            return False
    return False


class Ajudante:
    """Socket que entrega o descritor do /proc/<pid>/mem do jogo, aberto aqui (ancestral do jogo)."""

    def __init__(self, caminho: Path, exe: str = JOGO, proc_dir="/proc"):
        self.caminho, self.exe, self.proc_dir = Path(caminho), exe, proc_dir
        self.pid = self.fd = None
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        os.chmod(self.caminho.parent, 0o700)
        self.caminho.unlink(missing_ok=True)  # sobra de um ajudante que não saiu direito
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.bind(str(self.caminho))
        os.chmod(self.caminho, 0o600)
        self.sock.listen(4)

    def _jogo(self) -> tuple[int | None, int | None]:
        if self.fd is not None and not (Path(self.proc_dir) / str(self.pid)).exists():
            os.close(self.fd)
            self.pid = self.fd = None
        if self.fd is None:  # só o jogo aberto por este ajudante (outro DS2 aberto à parte não é descendente)
            pid = next((p for p in ds2mem.pids_de(self.exe, self.proc_dir) if descendente(p, os.getpid(), self.proc_dir)), None)
            if pid is not None:
                self.fd = os.open(f"{self.proc_dir}/{pid}/mem", os.O_RDONLY | os.O_CLOEXEC)
                self.pid = pid
                avisa(f"jogo achado: pid {pid}")
        return self.pid, self.fd

    def atender(self, conn) -> None:
        _, uid, _ = struct.unpack("3i", conn.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i")))
        if uid != os.getuid():
            return
        pid, fd = self._jogo()
        socket.send_fds(conn, [json.dumps({"pid": pid}).encode()], [fd] if fd is not None else [])

    def servir(self) -> None:
        while True:
            try:
                conn, _ = self.sock.accept()
            except OSError:  # socket fechado: o jogo saiu
                return
            with conn:
                try:
                    self.atender(conn)
                except OSError as err:
                    avisa(f"pedido falhou: {err}")

    def fechar(self) -> None:
        self.sock.close()
        self.caminho.unlink(missing_ok=True)
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None


def esperar(filho: subprocess.Popen) -> int:
    """Espera o comando do jogo; como subreaper, recolhe também os processos que o Wine soltou aqui."""
    while True:
        try:
            pid, status = os.waitpid(-1, 0)
        except ChildProcessError:
            return filho.returncode or 0
        if pid == filho.pid:
            filho.returncode = os.waitstatus_to_exitcode(status)
            return filho.returncode


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        print(f"uso, nas opções de inicialização da Steam: python3 {Path(__file__).resolve()} %command%", file=sys.stderr)
        return 2
    try:
        ctypes.CDLL(None, use_errno=True).prctl(PR_SET_CHILD_SUBREAPER, 1, 0, 0, 0)
    except (OSError, AttributeError) as err:
        avisa(f"sem subreaper: {err}")
    filho = subprocess.Popen(argv)
    for sinal in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(sinal, lambda s, _f: filho.poll() is None and filho.send_signal(s))
    ajudante = None
    try:
        ajudante = Ajudante(ds2mem.socket_ajudante())
        threading.Thread(target=ajudante.servir, daemon=True, name="ajudante").start()
        avisa(f"ajudante pronto em {ajudante.caminho}; jogo: {' '.join(argv)[:200]}")
    except OSError as err:  # o jogo abre do mesmo jeito, só sem a leitura ao vivo
        avisa(f"ajudante sem socket: {err}")
    try:
        return esperar(filho)
    finally:
        if ajudante is not None:
            ajudante.fechar()


if __name__ == "__main__":
    sys.exit(main())
