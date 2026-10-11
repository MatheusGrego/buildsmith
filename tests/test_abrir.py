import json
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
import abrir  # noqa: E402
import serve  # noqa: E402


def test_code_version_changes_with_the_code_but_not_with_line_endings(tmp_path):
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "serve.py").write_bytes(b"print('a')\n")
    v1 = abrir.versao_codigo(tmp_path)
    (tmp_path / "app" / "serve.py").write_bytes(b"print('a')\r\n")
    assert abrir.versao_codigo(tmp_path) == v1
    (tmp_path / "app" / "serve.py").write_bytes(b"print('b')\n")
    assert abrir.versao_codigo(tmp_path) != v1


def test_pull_is_skipped_outside_git(tmp_path):
    assert abrir.puxar(tmp_path).startswith("sem git")


def test_pid_from_windows_netstat():
    saida = """
  Proto  Endereço local         Endereço externo       Estado          PID
  TCP    0.0.0.0:135            0.0.0.0:0              LISTENING       1188
  TCP    127.0.0.1:8642         0.0.0.0:0              LISTENING       23456
  TCP    127.0.0.1:8642         127.0.0.1:50311        TIME_WAIT       0
  TCP    127.0.0.1:18642        0.0.0.0:0              LISTENING       999
"""
    assert abrir.pid_do_netstat(saida, 8642) == 23456
    assert abrir.pid_do_netstat(saida, 9000) is None


def test_stop_shuts_down_a_running_server(tmp_path):
    httpd = serve.make_server(tmp_path, port=0, runner=serve.Runner(command=lambda p: [sys.executable, "-c", "0"], cwd=tmp_path))
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    info = abrir.ping(port)
    assert info["versao"] == serve.VERSAO and isinstance(info["pid"], int)
    assert abrir.parar(port) is True
    thread.join(5)
    assert not thread.is_alive() and abrir.ping(port) is None
    httpd.server_close()


def test_pages_are_rebuilt_only_when_the_code_changes(tmp_path):
    for slug in ("pssk", "outro"):
        pasta = tmp_path / "paginas" / "ds2" / slug
        pasta.mkdir(parents=True)
        (pasta / "plano.json").write_text("{}", encoding="utf-8")
    chamadas = []

    def preparar(plano, jogo):
        chamadas.append((plano.parent.name, jogo))
        return {"error": "plano inválido"} if plano.parent.name == "outro" else {"index": "x", "avisos": []}

    avisos = []
    assert abrir.refazer_paginas(tmp_path, "v1", avisos.append, preparar=preparar) == ["ds2/pssk"]
    assert sorted(chamadas) == [("outro", "ds2"), ("pssk", "ds2")]
    assert any("fica a página de antes" in a for a in avisos)
    chamadas.clear()
    assert abrir.refazer_paginas(tmp_path, "v1", avisos.append, preparar=preparar) == []  # pssk já está na v1
    assert chamadas == [("outro", "ds2")]  # a que deu erro tenta de novo
    assert abrir.refazer_paginas(tmp_path, "v2", avisos.append, preparar=preparar) == ["ds2/pssk"]
    assert json.loads((tmp_path / "app" / "paginas.json").read_text(encoding="utf-8")) == {"ds2/pssk": "v2"}


def test_rebuild_forwards_script_progress_and_keeps_saying_it_is_working(tmp_path):
    """A janela do atalho não fica muda enquanto a página é refeita (senão parece travada e a pessoa fecha)."""
    script = tmp_path / "lento.py"
    script.write_text(
        "import sys, time, json\n"
        "print('mapa extraído do jogo: Majula', file=sys.stderr, flush=True)\n"
        "time.sleep(0.6)\n"
        "print(json.dumps({'index': 'x', 'files': {str(i): 'y' * 100 for i in range(2000)}}))\n",  # stdout grande
        encoding="utf-8")
    avisos = []
    saida, erro = abrir.rodar_avisando([sys.executable, str(script)], avisos.append, a_cada=0.2)
    assert json.loads(saida)["index"] == "x"
    assert "  mapa extraído do jogo: Majula" in avisos
    assert any(a.startswith("  ainda refazendo") for a in avisos)
    assert "Majula" in erro


def test_characters_without_a_page_get_one_without_ai(tmp_path, monkeypatch):
    sys.path.insert(0, str(abrir.REPO / "skills" / "build-page" / "scripts"))
    import plano_base

    chamadas = []

    def criar(home, preparar=None, avisa=None, **kw):
        chamadas.append(home)
        assert preparar is not None and avisa is not None
        return ["ds2/personagem-um"]

    monkeypatch.setattr(plano_base, "criar_paginas", criar)
    assert abrir.criar_paginas_sem_ia(tmp_path, avisa=lambda t: None) == ["ds2/personagem-um"] and chamadas == [tmp_path]
