#!/usr/bin/env python3
"""Cria o atalho "Forja de Build" na área de trabalho (Windows).

Baixa uma imagem de fogueira da wiki do DS2, monta ~/.buildsmith/app/buildsmith.ico e cria o atalho
apontando para `python.exe app/abrir.py`: uma janelinha mostra o git pull, o servidor reiniciando e as páginas
sendo refeitas (sem Claude), e fecha sozinha quando o navegador abre. A imagem do jogo fica só na sua máquina;
nada disso vai para o repositório.

Precisa de Pillow (pip install pillow) só para montar o ícone. No executável (`Buildsmith.exe atalho`), o atalho
aponta para o Buildsmith.exe e usa o ícone dele: não baixa nada. Aberto pelo exe único (o lançador, que descompacta
o programa em %LOCALAPPDATA%\\Buildsmith\\<versão>), o atalho aponta para o lançador, que sobrevive à próxima versão.
"""
import argparse
import io
import os
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

FONTE = "https://static0.fextralifeimages.com/file/darksouls2/f/f3/Bonfires-dark-souls-2-wiki-guide-300px.png"
RECORTE = (64, 22, 224, 182)  # quadrado 160×160 em volta da espada e da chama
REPO = Path(__file__).resolve().parents[1]
FUNDO, OURO = (16, 16, 19, 255), (171, 150, 111, 255)


def montar_icone(destino: Path, imagem: bytes) -> Path:
    from PIL import Image, ImageDraw, ImageFilter

    base = Image.open(io.BytesIO(imagem)).convert("RGBA").crop(RECORTE).resize((256, 256), Image.LANCZOS)
    base = base.filter(ImageFilter.UnsharpMask(radius=2, percent=80, threshold=2))
    canvas = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    ImageDraw.Draw(canvas).rounded_rectangle((0, 0, 255, 255), radius=44, fill=FUNDO)
    mascara = Image.new("L", (256, 256), 0)
    ImageDraw.Draw(mascara).ellipse((18, 18, 238, 238), fill=255)
    canvas.paste(base, (0, 0), mascara)
    ImageDraw.Draw(canvas).ellipse((16, 16, 240, 240), outline=OURO, width=6)
    destino.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(destino, format="ICO", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    canvas.save(destino.with_suffix(".png"))
    return destino


def alvo_do_atalho() -> tuple[str, str]:
    """(programa, argumentos) do atalho: o lançador (exe único) ou o Buildsmith.exe no executável, senão
    python.exe app/abrir.py."""
    if getattr(sys, "frozen", False):
        lancador = os.environ.get("BUILDSMITH_LANCADOR")
        if lancador and Path(lancador).is_file():
            return str(Path(lancador).resolve()), ""
        return str(Path(sys.executable).resolve().with_name("Buildsmith.exe")), ""
    python = str(Path(sys.executable).with_name("python.exe"))
    if not Path(python).exists():
        python = shutil.which("python") or sys.executable
    return python, f'"{REPO / "app" / "abrir.py"}"'


def criar_atalho(icone: Path, nome: str = "Forja de Build") -> Path:
    programa, argumentos = alvo_do_atalho()
    desktop = Path(subprocess.run(["powershell", "-NoProfile", "-Command", "[Environment]::GetFolderPath('Desktop')"],
                                  capture_output=True, text=True, check=True).stdout.strip())
    lnk = desktop / f"{nome}.lnk"
    script = (
        "$s = (New-Object -ComObject WScript.Shell).CreateShortcut($env:BS_LNK);"
        "$s.TargetPath = $env:BS_PYW; $s.Arguments = $env:BS_ARGS; $s.WorkingDirectory = $env:BS_REPO;"
        "$s.IconLocation = $env:BS_ICO + ',0'; $s.Description = 'Atualiza e abre a Forja de Build (buildsmith) no navegador';"
        "$s.Save()"
    )
    pasta = Path(programa).parent if getattr(sys, "frozen", False) else REPO  # a do lançador não some na versão nova
    env = {**os.environ, "BS_LNK": str(lnk), "BS_PYW": programa, "BS_ARGS": argumentos,
           "BS_REPO": str(pasta), "BS_ICO": str(icone)}
    subprocess.run(["powershell", "-NoProfile", "-Command", script], env=env, check=True)
    return lnk


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="instalar_atalho")
    parser.add_argument("--home", default=str(Path.home() / ".buildsmith"))
    parser.add_argument("--so-icone", action="store_true", help="só monta o ícone (sem criar atalho)")
    args = parser.parse_args(argv)
    if getattr(sys, "frozen", False):  # o Buildsmith.exe já traz o ícone
        print("atalho:", criar_atalho(Path(alvo_do_atalho()[0])))
        return 0
    req = urllib.request.Request(FONTE, headers={"User-Agent": "Mozilla/5.0 (buildsmith)"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        imagem = resp.read()
    icone = montar_icone(Path(args.home) / "app" / "buildsmith.ico", imagem)
    print("ícone:", icone)
    if not args.so_icone:
        print("atalho:", criar_atalho(icone))
    return 0


if __name__ == "__main__":
    sys.exit(main())
