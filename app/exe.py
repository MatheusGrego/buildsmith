#!/usr/bin/env python3
"""Ponto de entrada do executável do Windows (PyInstaller; monta com `python release/construir.py`).

O mesmo programa vai com três nomes na pasta do buildsmith, ao lado dos scripts (que ficam como arquivos comuns: o
Claude lê a pasta como plugin e o guarda confere os caminhos):
- Buildsmith.exe: abre o companion (app/abrir.py): sobe o servidor, refaz as páginas e abre o navegador;
  `Buildsmith.exe atalho` cria o atalho na área de trabalho;
- python.exe e pythonw.exe: fazem o papel do Python para os scripts, sem Python instalado. O abridor sobe o servidor
  com o pythonw, refaz a página com o python, e o Claude roda `python "<script>" ...` (a pasta vai na frente do PATH).
"""
import runpy
import sys
from pathlib import Path

OPCOES_PYTHON = {"-u", "-B", "-I", "-E", "-s", "-S", "-3", "-Xutf8"}  # aceitas e ignoradas (o exe já roda em UTF-8)


def raiz() -> Path:
    """Pasta do buildsmith: a do executável, ou a do repositório quando roda pelo Python."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def alvo(args: list[str], pasta: Path) -> tuple[Path, list[str]]:
    """(script, sys.argv do script) para os argumentos que o executável recebeu."""
    args = list(args)
    while args and (args[0] in OPCOES_PYTHON or args[0] == "-X"):
        args = args[2:] if args[0] == "-X" else args[1:]
    if args and args[0].lower().endswith((".py", ".pyw")):
        return Path(args[0]), args
    if args[:1] == ["atalho"]:
        script = pasta / "app" / "instalar_atalho.py"
        return script, [str(script), *args[1:]]
    script = pasta / "app" / "abrir.py"
    return script, [str(script), *args]


def main() -> None:
    script, sys.argv = alvo(sys.argv[1:], raiz())
    sys.path.insert(0, str(script.resolve().parent))  # como o python faz: a pasta do script primeiro
    runpy.run_path(str(script), run_name="__main__")


if __name__ == "__main__":
    main()
