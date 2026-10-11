#!/usr/bin/env python3
"""Monta o executável do Windows e o zip da release.

    python release/construir.py

1. ambiente isolado em build/venv com PyInstaller e pycryptodome (versões fixas abaixo);
2. ícone próprio (brasa e espada, desenhado aqui: nenhuma imagem do jogo vai na release) em build/buildsmith.ico;
3. PyInstaller com release/buildsmith.spec: Buildsmith.exe, python.exe, pythonw.exe e runtime/ em build/dist/Buildsmith;
4. os arquivos do programa ao lado (app, skills, games, .claude-plugin, README) e o LEIA-ME.txt;
5. teste de fumaça (cada exe roda um script do buildsmith) e build/buildsmith-<versão>-windows-x64.zip.
"""
import json
import math
import shutil
import struct
import subprocess
import sys
import zipfile
import zlib
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
BUILD = RAIZ / "build"
VENV = BUILD / "venv"
PACOTES = ["pyinstaller==6.11.1", "pycryptodome==3.21.0"]
PROGRAMA = ("app", "skills", "games", ".claude-plugin", "README.md")
SEM_JANELA = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def versao() -> str:
    return json.loads((RAIZ / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))["version"]


def python_do_venv() -> Path:
    py = VENV / "Scripts" / "python.exe"
    if not py.is_file():
        subprocess.run([sys.executable, "-m", "venv", str(VENV)], check=True)
    subprocess.run([str(py), "-m", "pip", "install", "--disable-pip-version-check", "-q", *PACOTES], check=True)
    return py


# ---- ícone -----------------------------------------------------------------------------------------------------
def _liso(d: float, borda: float) -> float:
    """Cobertura 0..1 de uma forma pela distância com sinal (negativa dentro), com borda suave de `borda`."""
    return min(1.0, max(0.0, 0.5 - d / borda))


def _pixel(u: float, v: float, px: float) -> tuple[float, float, float, float]:
    cor, alfa = [0.0, 0.0, 0.0], 0.0

    def pinta(rgb, cobertura):
        nonlocal alfa
        for k in range(3):
            cor[k] = cor[k] * (1 - cobertura) + rgb[k] * cobertura
        alfa = alfa + cobertura * (1 - alfa)

    qx, qy = abs(u - 0.5) - 0.5 + 0.17, abs(v - 0.5) - 0.5 + 0.17  # quadrado de cantos redondos
    d = math.hypot(max(qx, 0), max(qy, 0)) + min(max(qx, qy), 0) - 0.17
    pinta((16, 16, 19), _liso(d, px))
    r = math.hypot(u - 0.5, v - 0.5)
    pinta((171, 150, 111), _liso(abs(r - 0.40) - 0.022, px))  # anel dourado
    # brasa: gota (círculo embaixo, ponta para cima)
    base = math.hypot(u - 0.5, v - 0.63) - 0.15
    ponta = abs(u - 0.5) - 0.15 * max(0.0, (v - 0.24) / 0.39) if v >= 0.24 else math.hypot(u - 0.5, v - 0.24)
    gota = min(base, ponta if v < 0.63 else base)
    calor = max(0.0, min(1.0, 1 - abs(u - 0.5) / 0.15)) * max(0.0, min(1.0, (v - 0.3) / 0.45))
    pinta((235 + 20 * calor, 110 + 110 * calor, 40 + 90 * calor), _liso(gota, px))
    # espada cravada: lâmina, guarda e cabo
    lamina = max(abs(u - 0.5) - 0.018, abs(v - 0.50) - 0.25)
    guarda = max(abs(u - 0.5) - 0.085, abs(v - 0.33) - 0.016)
    pinta((222, 218, 208), _liso(min(lamina, guarda), px) * 0.92)
    return cor[0], cor[1], cor[2], alfa


def _png(lado: int) -> bytes:
    linhas = bytearray()
    for y in range(lado):
        linhas.append(0)
        for x in range(lado):
            r, g, b, a = _pixel((x + 0.5) / lado, (y + 0.5) / lado, 1.5 / lado)
            linhas += bytes((round(r), round(g), round(b), round(a * 255)))

    def bloco(tipo: bytes, dados: bytes) -> bytes:
        return struct.pack(">I", len(dados)) + tipo + dados + struct.pack(">I", zlib.crc32(tipo + dados) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n" + bloco(b"IHDR", struct.pack(">IIBBBBB", lado, lado, 8, 6, 0, 0, 0))
            + bloco(b"IDAT", zlib.compress(bytes(linhas), 9)) + bloco(b"IEND", b""))


def icone(destino: Path, lados=(16, 24, 32, 48, 64, 128, 256)) -> Path:
    """ICO com PNG em cada tamanho (Windows Vista em diante)."""
    imagens = [_png(lado) for lado in lados]
    cab = struct.pack("<3H", 0, 1, len(lados))
    off = 6 + 16 * len(lados)
    entradas = b""
    for lado, img in zip(lados, imagens):
        entradas += struct.pack("<4B2H2I", lado % 256, lado % 256, 0, 0, 1, 32, len(img), off)
        off += len(img)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(cab + entradas + b"".join(imagens))
    return destino


# ---- pasta e zip ---------------------------------------------------------------------------------------------------
LEIA_ME = """Forja de Build (buildsmith) {versao} — early alpha, Windows 64 bits

Companion do Dark Souls II: Scholar of the First Sin. Lê o seu save e os arquivos do jogo instalado e mostra a sua
página: nível, atributos, equipamento, o plano de build e o mapa 2D/3D de cada área (itens, inimigos, portas e chaves,
fogueiras, rota pelo chão), tudo atualizado enquanto você joga.

COMO ABRIR
  1. Descompacte esta pasta onde quiser (ex.: Documentos\\Buildsmith).
  2. Dê dois cliques em Buildsmith.exe. Uma janelinha mostra os passos e o navegador abre a página
     (http://127.0.0.1:8642/). O servidor fica rodando em segundo plano.
  3. Opcional: "Buildsmith.exe atalho" (num terminal nesta pasta) cria o atalho "Forja de Build" na área de trabalho.

PRECISA
  - Dark Souls II: Scholar of the First Sin instalado pela Steam (os mapas e modelos são lidos dos arquivos do jogo,
    na sua máquina; nada do jogo vem nesta pasta).
  - Gerar ou atualizar o PLANO de build usa o Claude Code (comando `claude` instalado e logado). Ler o save, a página,
    o mapa e o progresso ao vivo não usam IA.

ONDE FICAM SEUS DADOS
  %USERPROFILE%\\.buildsmith (perfil, páginas, cache dos mapas). O save do jogo só é lido, nunca gravado.

PARAR O SERVIDOR
  python.exe app\\serve.py parar   (nesta pasta)

Os arquivos python.exe/pythonw.exe e a pasta runtime\\ são o Python embutido do programa (não é preciso ter Python).
Código e licenças: README.md e games\\LICENSE-*.
"""


def copiar_programa(pasta: Path) -> None:
    lixo = shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache")
    for nome in PROGRAMA:
        origem, destino = RAIZ / nome, pasta / nome
        if destino.exists():
            shutil.rmtree(destino) if destino.is_dir() else destino.unlink()
        if origem.is_dir():
            shutil.copytree(origem, destino, ignore=lixo)
        else:
            shutil.copy2(origem, destino)
    (pasta / "LEIA-ME.txt").write_text(LEIA_ME.format(versao=versao()), encoding="utf-8")


def fumaca(pasta: Path) -> None:
    """Cada executável roda um script do buildsmith que importa a biblioteca padrão e o pycryptodome."""
    testes = [
        (["python.exe", "app/serve.py", "--help"], "usage"),
        (["python.exe", "skills/ds2-save/scripts/ds2esd.py", "--help"], "usage"),
        (["python.exe", "-X", "utf8", "skills/ds2-save/scripts/ds2save.py", "--help"], "usage"),
        (["Buildsmith.exe", "--help"], "usage"),
    ]
    codigo = "from Crypto.Cipher import AES; from Crypto.PublicKey import RSA; import http.server, gzip; print('ok')"
    (pasta / "fumaca.py").write_text(codigo, encoding="utf-8")
    testes.append((["pythonw.exe", "fumaca.py"], None))
    try:
        for cmd, esperado in testes:
            r = subprocess.run([str(pasta / cmd[0]), *cmd[1:]], cwd=str(pasta), capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=120, creationflags=SEM_JANELA)
            if r.returncode != 0 or (esperado and esperado not in (r.stdout + r.stderr).lower()):
                raise SystemExit(f"fumaça falhou: {' '.join(cmd)} -> {r.returncode}\n{r.stdout}\n{r.stderr}")
            print("  ok:", " ".join(cmd))
    finally:
        (pasta / "fumaca.py").unlink(missing_ok=True)


def zipar(pasta: Path, destino: Path) -> Path:
    destino.unlink(missing_ok=True)
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for p in sorted(pasta.rglob("*")):
            if p.is_file():
                z.write(p, Path("Buildsmith") / p.relative_to(pasta))
    return destino


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    v = versao()
    print(f"buildsmith {v}: ambiente de build...")
    py = python_do_venv()
    print("ícone:", icone(BUILD / "buildsmith.ico"))
    subprocess.run([str(py), "-m", "PyInstaller", str(RAIZ / "release" / "buildsmith.spec"), "--noconfirm", "--clean",
                    "--distpath", str(BUILD / "dist"), "--workpath", str(BUILD / "work"), "--log-level", "WARN"],
                   check=True, cwd=str(RAIZ))
    pasta = BUILD / "dist" / "Buildsmith"
    copiar_programa(pasta)
    print("testando os executáveis...")
    fumaca(pasta)
    z = zipar(pasta, BUILD / f"buildsmith-{v}-windows-x64.zip")
    print(f"pronto: {z} ({z.stat().st_size / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
