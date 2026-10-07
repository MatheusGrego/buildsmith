#!/usr/bin/env python3
"""Cria o atalho "Forja de Build" na área de trabalho (Windows).

Baixa uma imagem de fogueira da wiki do DS2, monta ~/.buildsmith/app/buildsmith.ico e cria o atalho
apontando para `pythonw.exe app/serve.py --open` (sem janela de console). A imagem do jogo fica só na
sua máquina; nada disso vai para o repositório.

Precisa de Pillow (pip install pillow) só para montar o ícone.
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


def criar_atalho(icone: Path, nome: str = "Forja de Build") -> Path:
    pythonw = shutil.which("pythonw") or str(Path(sys.executable).with_name("pythonw.exe"))
    desktop = Path(subprocess.run(["powershell", "-NoProfile", "-Command", "[Environment]::GetFolderPath('Desktop')"],
                                  capture_output=True, text=True, check=True).stdout.strip())
    lnk = desktop / f"{nome}.lnk"
    script = (
        "$s = (New-Object -ComObject WScript.Shell).CreateShortcut($env:BS_LNK);"
        "$s.TargetPath = $env:BS_PYW; $s.Arguments = $env:BS_ARGS; $s.WorkingDirectory = $env:BS_REPO;"
        "$s.IconLocation = $env:BS_ICO + ',0'; $s.Description = 'Abre a Forja de Build (buildsmith) no navegador'; $s.Save()"
    )
    env = {**os.environ, "BS_LNK": str(lnk), "BS_PYW": pythonw, "BS_ARGS": f'"{REPO / "app" / "serve.py"}" --open',
           "BS_REPO": str(REPO), "BS_ICO": str(icone)}
    subprocess.run(["powershell", "-NoProfile", "-Command", script], env=env, check=True)
    return lnk


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="instalar_atalho")
    parser.add_argument("--home", default=str(Path.home() / ".buildsmith"))
    parser.add_argument("--so-icone", action="store_true", help="só monta o ícone (sem criar atalho)")
    args = parser.parse_args(argv)
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
