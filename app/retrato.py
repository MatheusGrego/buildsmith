"""Retrato do personagem na página: foto enviada pelo jogador ou o último print do DS2 na Steam.

Fica em ~/.buildsmith/retratos/<jogo>/<slug>.<png|jpg>. Só PNG ou JPEG, reconhecidos pelos bytes iniciais
(a extensão e o Content-Type vêm do navegador e não valem), até 2 MB.
"""
import os
import re
from pathlib import Path

MAX_RETRATO = 2 * 1024 * 1024
SEGMENT = re.compile(r"^[a-z0-9][a-z0-9._-]{0,180}$")
DS2_APP = 335300
STEAM_DIRS = [Path("C:/Program Files (x86)/Steam"), Path("C:/Program Files/Steam")]
TIPOS = {"png": "image/png", "jpg": "image/jpeg"}


def tipo_imagem(data: bytes) -> str | None:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg"
    return None


def _pasta(home, jogo: str, slug: str) -> Path:
    if not SEGMENT.match(jogo) or not SEGMENT.match(slug):
        raise ValueError("jogo ou personagem inválido")
    return Path(home) / "retratos" / jogo


def achar(home, jogo: str, slug: str) -> Path | None:
    pasta = _pasta(home, jogo, slug)
    for ext in TIPOS:
        path = pasta / f"{slug}.{ext}"
        if path.is_file():
            return path
    return None


def gravar(home, jogo: str, slug: str, data: bytes) -> Path:
    pasta = _pasta(home, jogo, slug)
    if len(data) > MAX_RETRATO:
        raise ValueError("imagem maior que 2 MB")
    ext = tipo_imagem(data)
    if ext is None:
        raise ValueError("só PNG ou JPEG")
    pasta.mkdir(parents=True, exist_ok=True)
    destino = pasta / f"{slug}.{ext}"
    tmp = destino.with_suffix(".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, destino)
    for outro in TIPOS:
        if outro != ext:
            (pasta / f"{slug}.{outro}").unlink(missing_ok=True)
    return destino


def limpar(home, jogo: str, slug: str) -> None:
    pasta = _pasta(home, jogo, slug)
    for ext in TIPOS:
        (pasta / f"{slug}.{ext}").unlink(missing_ok=True)


def ultimo_print(steam_dirs=None, app: int = DS2_APP) -> Path | None:
    """Print mais recente do jogo na Steam (F12): <steam>/userdata/<conta>/760/remote/<app>/screenshots/*.jpg."""
    found = []
    for raiz in steam_dirs if steam_dirs is not None else STEAM_DIRS:
        found += [p for p in Path(raiz).glob(f"userdata/*/760/remote/{app}/screenshots/*.jpg") if p.is_file()]
    return max(found, key=lambda p: p.stat().st_mtime) if found else None
