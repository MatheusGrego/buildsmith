import json
import os
import signal
import subprocess
import sys
from pathlib import Path

import pytest

from test_ds2mem import MARCA, jogo_falso

pytestmark = pytest.mark.skipif(not sys.platform.startswith("linux"), reason="ajudante só no Linux")
REPO = Path(__file__).resolve().parents[1]
AJUDANTE = REPO / "app" / "vivo_linux.py"

# Quem lê no papel do servidor: irmão do ajudante, não ancestral do jogo (o Yama nega o /proc/<pid>/mem direto).
LEITOR = r"""
import json, os, sys
sys.path.insert(0, sys.argv[2])
import ds2mem
pid = int(sys.argv[1])
try:
    os.close(os.open(f"/proc/{pid}/mem", os.O_RDONLY))
    direto = True
except PermissionError:
    direto = False
ds2mem.pid_de = lambda exe, proc_dir="/proc": pid
proc = ds2mem.ProcessoLinux.abrir("DarkSoulsII.exe")
print(json.dumps({"direto": direto, "marca": proc.ler(proc.base_modulo + 0x200, 16).decode(),
                  "tamanho": proc.tamanho_modulo}))
"""


def ppid(pid: int) -> int:
    status = Path(f"/proc/{pid}/status").read_text(encoding="utf-8")
    return int(next(linha.split()[1] for linha in status.splitlines() if linha.startswith("PPid:")))


def ptrace_scope() -> str:
    try:
        return Path("/proc/sys/kernel/yama/ptrace_scope").read_text().strip()
    except OSError:
        return ""


def test_helper_hands_the_game_memory_to_a_process_that_is_not_its_ancestor(tmp_path):
    env = {**os.environ, "XDG_RUNTIME_DIR": str(tmp_path / "run"), "HOME": str(tmp_path)}
    ajudante, jogo, _ = jogo_falso(tmp_path, exe_nome="DarkSoulsII.exe", duplo=True,
                                   antes=(sys.executable, str(AJUDANTE)), env=env)
    try:
        assert ppid(jogo) == ajudante.pid  # o Wine solta o processo do jogo; o subreaper o segura no ajudante
        leitor = tmp_path / "leitor.py"
        leitor.write_text(LEITOR, encoding="utf-8")
        out = subprocess.run([sys.executable, str(leitor), str(jogo), str(REPO / "skills" / "ds2-save" / "scripts")],
                             capture_output=True, text=True, timeout=20, env=env)
        assert out.returncode == 0, out.stderr
        lido = json.loads(out.stdout)
        assert lido["marca"] == MARCA.decode() and lido["tamanho"] == 0x3000
        if ptrace_scope() == "1":
            assert lido["direto"] is False  # sem o ajudante o servidor não leria
    finally:
        ajudante.send_signal(signal.SIGTERM)  # a Steam parando o jogo: o ajudante repassa ao comando e sai
        ajudante.wait(timeout=10)
        os.kill(jogo, signal.SIGKILL)
    assert not (tmp_path / "run" / "buildsmith" / "ds2-mem.sock").exists()


def test_helper_runs_the_game_even_without_socket_and_returns_its_exit_code(tmp_path):
    env = {**os.environ, "XDG_RUNTIME_DIR": "/proc/sem-permissao", "HOME": str(tmp_path)}
    out = subprocess.run([sys.executable, str(AJUDANTE), sys.executable, "-c", "import sys; sys.exit(3)"],
                         capture_output=True, text=True, timeout=20, env=env)
    assert out.returncode == 3
    assert "ajudante sem socket" in (tmp_path / ".buildsmith" / "execucoes" / "vivo_linux.log").read_text(encoding="utf-8")


def test_helper_without_command_shows_how_to_use():
    out = subprocess.run([sys.executable, str(AJUDANTE)], capture_output=True, text=True, timeout=20)
    assert out.returncode == 2 and "%command%" in out.stderr
