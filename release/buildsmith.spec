# -*- mode: python ; coding: utf-8 -*-
# Spec do PyInstaller para o executável do Windows. Não rode direto: `python release/construir.py` monta o ícone,
# roda este spec, copia os arquivos do programa para o lado dos executáveis, testa e gera o zip.
#
# Os três executáveis são o mesmo programa (app/exe.py) com o mesmo runtime (pasta runtime/): Buildsmith.exe (abre o
# companion), python.exe e pythonw.exe (o Python dos scripts). Os scripts do buildsmith NÃO vão para dentro do
# executável: só a biblioteca padrão e o pycryptodome que eles importam (lista tirada do próprio código).
import ast
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

RAIZ = Path(SPECPATH).resolve().parent  # noqa: F821 (SPECPATH vem do PyInstaller)
PASTAS = ("app", "skills")
FORA = {"PIL", "pytest", "tkinter"}  # Pillow só monta o ícone do atalho fora do executável


def imports_do_codigo() -> list[str]:
    locais = {p.stem for d in PASTAS for p in (RAIZ / d).rglob("*.py")}
    mods = set()
    for d in PASTAS:
        for p in (RAIZ / d).rglob("*.py"):
            for no in ast.walk(ast.parse(p.read_text(encoding="utf-8"))):
                if isinstance(no, ast.Import):
                    mods |= {a.name for a in no.names}
                elif isinstance(no, ast.ImportFrom) and no.module and not no.level:
                    mods.add(no.module)
    return sorted(m for m in mods if m.split(".")[0] not in locais | FORA)


a = Analysis(
    [str(RAIZ / "app" / "exe.py")],
    pathex=[],
    hiddenimports=imports_do_codigo() + collect_submodules("Crypto", filter=lambda m: ".SelfTest" not in m)
    + collect_submodules("encodings"),
    excludes=sorted(FORA | {"unittest", "pydoc_data", "test", "Crypto.SelfTest"}),
    noarchive=False,
)
pyz = PYZ(a.pure)  # noqa: F821
ICONE = str(RAIZ / "build" / "buildsmith.ico")


def exe(nome: str, console: bool):
    return EXE(  # noqa: F821
        pyz, a.scripts, [("X utf8", None, "OPTION")], exclude_binaries=True, name=nome, console=console,
        icon=ICONE, upx=False, contents_directory="runtime",
    )


COLLECT(  # noqa: F821
    exe("Buildsmith", True), exe("python", True), exe("pythonw", False),
    a.binaries, a.datas, name="Buildsmith", upx=False,
)
