"""O executável do Windows (app/exe.py, release/): o mesmo programa faz o papel do python dos scripts."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
import exe  # noqa: E402
import instalar_atalho  # noqa: E402
import runner  # noqa: E402

PASTA = Path("C:/Jogos/Buildsmith")


def test_sem_argumento_abre_o_companion():
    script, argv = exe.alvo([], PASTA)
    assert script == PASTA / "app" / "abrir.py" and argv == [str(script)]
    script, argv = exe.alvo(["--sem-pull", "--port", "8650"], PASTA)
    assert script.name == "abrir.py" and argv[1:] == ["--sem-pull", "--port", "8650"]


def test_script_roda_como_no_python_e_ignora_opcoes_do_interpretador():
    """O abridor chama `pythonw.exe app/serve.py ...` e o Claude `python -X utf8 "<script>" ...` (o guarda deixa)."""
    s = "C:/Jogos/Buildsmith/skills/ds2-save/scripts/ds2save.py"
    assert exe.alvo(["-X", "utf8", "-u", s, "levels", "--from", "1"], PASTA) == (Path(s), [s, "levels", "--from", "1"])
    assert exe.alvo(["app/serve.py", "--home", "h"], PASTA) == (Path("app/serve.py"), ["app/serve.py", "--home", "h"])


def test_atalho():
    script, argv = exe.alvo(["atalho"], PASTA)
    assert script == PASTA / "app" / "instalar_atalho.py" and argv == [str(script)]


def test_no_executavel_o_claude_acha_o_python_da_pasta(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "pythonw.exe"))
    env = runner.child_env(tmp_path)
    assert env["PATH"].split(";" if sys.platform == "win32" else ":")[0] == str(tmp_path.resolve())
    assert instalar_atalho.alvo_do_atalho() == (str(tmp_path.resolve() / "Buildsmith.exe"), "")


def test_fora_do_executavel_nada_muda(monkeypatch, tmp_path):
    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.setenv("PATH", "X")
    assert runner.child_env(tmp_path)["PATH"] == "X"
    programa, argumentos = instalar_atalho.alvo_do_atalho()
    assert argumentos.endswith('abrir.py"')
