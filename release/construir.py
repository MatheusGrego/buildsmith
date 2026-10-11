#!/usr/bin/env python3
"""Monta o executável do Windows e o zip da release.

    python release/construir.py

1. ambiente isolado em build/venv com PyInstaller e pycryptodome (versões fixas abaixo);
2. ícone próprio (brasa e espada, desenhado aqui: nenhuma imagem do jogo vai na release) em build/buildsmith.ico;
3. PyInstaller com release/buildsmith.spec: Buildsmith.exe, python.exe, pythonw.exe e runtime/ em build/dist/Buildsmith;
4. os arquivos do programa ao lado (app, skills, games, .claude-plugin, README, LICENSE, THIRD_PARTY_NOTICES), o
   LEIA-ME.txt e, em licencas/, as licenças do que vai dentro do executável (Python, pycryptodome, PyInstaller);
5. teste de fumaça (cada exe roda um script do buildsmith) e build/buildsmith-<versão>-windows-x64.zip;
6. exe único (com o Go instalado): o lançador de release/lancador com o zip embutido e o ícone (.syso) em
   build/Buildsmith.exe; na primeira vez ele descompacta o programa em %LOCALAPPDATA%\\Buildsmith\\<versão>. Testado
   com uma pasta temporária no lugar do %LOCALAPPDATA%.
"""
import json
import math
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import zipfile
import zlib
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
BUILD = RAIZ / "build"
VENV = BUILD / "venv"
PACOTES = ["pyinstaller==6.11.1", "pycryptodome==3.21.0"]
PROGRAMA = ("app", "skills", "games", ".claude-plugin", "README.md", "LICENSE", "THIRD_PARTY_NOTICES.md")
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


def syso_do_icone(ico: bytes) -> bytes:
    """O ícone como recurso do Windows num objeto COFF (.syso) que o `go build` junta ao exe do lançador.

    Formato PE/COFF da Microsoft: seção .rsrc com a árvore tipo → ID → idioma (RT_ICON = 3, uma imagem por ID;
    RT_GROUP_ICON = 14, o diretório do ícone com o ID de cada imagem); cada IMAGE_RESOURCE_DATA_ENTRY guarda o RVA do
    dado, que o linker acerta pela relocação IMAGE_REL_AMD64_ADDR32NB contra o símbolo da seção."""
    n = struct.unpack_from("<3H", ico, 0)[2]
    entradas = [struct.unpack_from("<4B2H2I", ico, 6 + 16 * k) for k in range(n)]
    imagens = [ico[e[7]:e[7] + e[6]] for e in entradas]
    grupo = struct.pack("<3H", 0, 1, n) + b"".join(struct.pack("<4B2HIH", *e[:6], e[6], k + 1) for k, e in enumerate(entradas))
    dados = imagens + [grupo]
    dir_ = lambda ids: struct.pack("<IIHHHH", 0, 0, 0, 0, 0, len(ids)) + b"".join(struct.pack("<II", *i) for i in ids)  # noqa: E731
    sub, t14 = 0x80000000, 32 + 16 + 8 * n  # raiz (2 tipos) e diretório do tipo 3 vêm antes
    idiomas = t14 + 24
    entradas_dado = idiomas + 24 * len(dados)
    inicio = (entradas_dado + 16 * len(dados) + 7) // 8 * 8
    offs, pos = [], inicio
    for d in dados:
        offs.append(pos)
        pos = (pos + len(d) + 7) // 8 * 8
    rsrc = bytearray(dir_([(3, sub | 32), (14, sub | t14)]))
    rsrc += dir_([(k + 1, sub | (idiomas + 24 * k)) for k in range(n)])
    rsrc += dir_([(1, sub | (idiomas + 24 * n))])
    for k in range(len(dados)):
        rsrc += dir_([(0x0409, entradas_dado + 16 * k)])
    for d, off in zip(dados, offs):
        rsrc += struct.pack("<4I", off, len(d), 0, 0)
    for d, off in zip(dados, offs):
        rsrc += b"\0" * (off - len(rsrc)) + d
    rsrc += b"\0" * (-len(rsrc) % 8)
    relocs = b"".join(struct.pack("<IIH", entradas_dado + 16 * k, 0, 3) for k in range(len(dados)))
    simbolos = 60 + len(rsrc) + len(relocs)
    cab = struct.pack("<HHIIIHH", 0x8664, 1, 0, simbolos, 1, 0, 0)
    secao = struct.pack("<8sIIIIIIHHI", b".rsrc", 0, 0, len(rsrc), 60, 60 + len(rsrc), 0, len(dados), 0, 0x40000040)
    simbolo = struct.pack("<8sIhHBB", b".rsrc", 0, 1, 0, 3, 0)
    return cab + secao + bytes(rsrc) + relocs + simbolo + struct.pack("<I", 4)


# ---- pasta e zip ---------------------------------------------------------------------------------------------------
LEIA_ME = """Forja de Build (buildsmith) {versao} — early alpha, Windows 64 bits

Companion do Dark Souls II: Scholar of the First Sin. Lê o seu save e os arquivos do jogo instalado e mostra a sua
página: nível, atributos, equipamento, o Catálogo com todos os itens do jogo (marque com a estrela e veja onde pegar
e os passos), o plano de build e o mapa 2D/3D de cada área (itens, inimigos, portas e chaves, fogueiras, rota pelo
chão), tudo atualizado enquanto você joga.

COMO ABRIR
  1. Descompacte esta pasta onde quiser (ex.: Documentos\\Buildsmith).
  2. Dê dois cliques em Buildsmith.exe. Uma janelinha mostra os passos e o navegador abre a página
     (http://127.0.0.1:8642/). O servidor fica rodando em segundo plano.
  3. Opcional: "Buildsmith.exe atalho" (num terminal nesta pasta) cria o atalho "Forja de Build" na área de trabalho.

PRECISA
  - Dark Souls II: Scholar of the First Sin instalado pela Steam (os mapas e modelos são lidos dos arquivos do jogo,
    na sua máquina; nada do jogo vem nesta pasta).
  - Só o PLANO de build (opcional: objetivo, quais itens e por quê, comparação com builds) usa o Claude Code (comando
    `claude` instalado e logado). O save, a página de cada personagem, o Catálogo, Onde pegar e Passos dos itens
    marcados, o mapa e o progresso ao vivo não usam IA.

ONDE FICAM SEUS DADOS
  %USERPROFILE%\\.buildsmith (perfil, páginas, itens marcados, cache dos mapas e dos itens). O save do jogo só é
  lido, nunca gravado.

PARAR O SERVIDOR
  python.exe app\\serve.py parar   (nesta pasta)

Os arquivos python.exe/pythonw.exe e a pasta runtime\\ são o Python embutido do programa (não é preciso ter Python).

LICENÇA
  PolyForm Strict 1.0.0 (arquivo LICENSE): pode usar para fins não comerciais (uso pessoal, estudo, hobby); não pode
  modificar, criar obras derivadas nem redistribuir sem permissão por escrito dos autores. Componentes de terceiros e
  as licenças deles: THIRD_PARTY_NOTICES.md e a pasta licencas\\. Projeto de fãs, sem ligação com a FromSoftware ou
  a Bandai Namco.
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
    licencas = pasta / "licencas"
    licencas.mkdir(exist_ok=True)
    site = VENV / "Lib" / "site-packages"
    base = Path(subprocess.run([str(VENV / "Scripts" / "python.exe"), "-c", "import sys; print(sys.base_prefix)"],
                               capture_output=True, text=True, check=True).stdout.strip())
    for origem, nome in ((base / "LICENSE.txt", "PYTHON-LICENSE.txt"),
                         (next(site.glob("pycryptodome-*.dist-info")) / "LICENSE.rst", "PYCRYPTODOME-LICENSE.rst"),
                         (next(site.glob("pyinstaller-*.dist-info")) / "COPYING.txt", "PYINSTALLER-COPYING.txt")):
        shutil.copy2(origem, licencas / nome)
    go = shutil.which("go")
    if go:  # o exe único (lançador em Go) leva o runtime do Go: a licença vai junto, dentro do programa
        goroot = Path(subprocess.run([go, "env", "GOROOT"], capture_output=True, text=True, check=True).stdout.strip())
        shutil.copy2(goroot / "LICENSE", licencas / "GO-LICENSE.txt")


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


def lancador(zip_programa: Path, ico: Path, v: str) -> Path | None:
    """build/Buildsmith.exe: o lançador em Go com o programa e o ícone embutidos; None sem o Go instalado."""
    go = shutil.which("go")
    if go is None:
        print("sem o Go: fica só o zip (o exe único precisa do Go 1.21 ou mais novo)")
        return None
    pasta = BUILD / "lancador"
    shutil.rmtree(pasta, ignore_errors=True)
    shutil.copytree(RAIZ / "release" / "lancador", pasta, ignore=shutil.ignore_patterns("*_test.go"))
    shutil.copy2(zip_programa, pasta / "programa.zip")
    (pasta / "rsrc_windows_amd64.syso").write_bytes(syso_do_icone(ico.read_bytes()))
    destino = BUILD / "Buildsmith.exe"
    env = {**os.environ, "CGO_ENABLED": "0", "GOOS": "windows", "GOARCH": "amd64"}
    subprocess.run([go, "build", "-tags", "embutido", "-trimpath", "-ldflags", f"-s -w -X main.versao={v}",
                    "-o", str(destino), "."], cwd=str(pasta), env=env, check=True)
    return destino


def fumaca_lancador(exe: Path, v: str) -> None:
    """O exe único descompacta na primeira vez, roda o Buildsmith.exe de dentro e não descompacta de novo depois."""
    with tempfile.TemporaryDirectory() as tmp:
        env = {**os.environ, "LOCALAPPDATA": tmp}
        marca = Path(tmp) / "Buildsmith" / v / ".completo"
        for vez in (1, 2):
            r = subprocess.run([str(exe), "--help"], capture_output=True, text=True, encoding="utf-8", errors="replace",
                               timeout=300, env=env, creationflags=SEM_JANELA)
            if r.returncode != 0 or "usage" not in (r.stdout + r.stderr).lower() or not marca.is_file():
                raise SystemExit(f"fumaça do exe único falhou ({vez}ª vez): {r.returncode}\n{r.stdout}\n{r.stderr}")
            if vez == 1:
                antes = marca.stat().st_mtime_ns
            elif marca.stat().st_mtime_ns != antes:
                raise SystemExit("o exe único descompactou de novo na segunda vez")
            print(f"  ok: Buildsmith.exe (exe único) --help, {vez}ª vez")


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
    exe = lancador(z, BUILD / "buildsmith.ico", v)
    if exe:
        fumaca_lancador(exe, v)
        print(f"pronto: {exe} ({exe.stat().st_size / 1e6:.1f} MB, exe único)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
