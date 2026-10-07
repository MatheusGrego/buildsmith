import json
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
import runner  # noqa: E402

FAKE = r'''
import json, sys, time
def out(e): print(json.dumps(e), flush=True)
out({"type": "system", "subtype": "init"})
out({"type": "assistant", "message": {"content": [{"type": "text", "text": "[etapa:fila] Lendo a fila da página"}]}})
out({"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Bash", "input": {"command": "python ds2save.py snapshot", "description": "Lê o save"}}]}})
out({"type": "user", "message": {"content": [{"type": "tool_result", "content": "ok"}]}})
out({"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "WebFetch", "input": {"url": "https://darksouls2.wiki.fextralife.com/Bonfire+Ascetic"}}]}})
out({"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Bash", "input": {"command": "python prepare_page.py plano.json saida"}}]}})
time.sleep(float(sys.argv[1]) if len(sys.argv) > 1 else 0)
out({"type": "result", "subtype": "success", "is_error": False, "result": "Plano atualizado", "total_cost_usd": 0.42, "duration_ms": 1000})
'''


def fake_cmd(tmp_path, delay=0.0, login_error=False):
    script = tmp_path / "fake_claude.py"
    body = FAKE
    if login_error:
        body = ('import json\nprint(json.dumps({"type": "assistant", "message": {"content": [{"type": "text", '
                '"text": "Failed to authenticate: OAuth session expired"}]}}))\n'
                'print(json.dumps({"type": "result", "is_error": True, "result": "Failed to authenticate", "total_cost_usd": 0}))\n')
    script.write_text(body, encoding="utf-8")
    return lambda prompt: [sys.executable, str(script), str(delay)]


def wait(r, timeout=10):
    end = time.time() + timeout
    while r.status()["estado"] == "rodando" and time.time() < end:
        time.sleep(0.05)
    return r.status()


def test_stages_microtext_and_result(tmp_path):
    r = runner.Runner(command=fake_cmd(tmp_path), cwd=tmp_path)
    r.start("plano", "/buildsmith:build ds2")
    st = wait(r)
    assert st["estado"] == "ok" and st["custo_usd"] == 0.42
    assert st["etapa"] == "fim"
    textos = [e["texto"] for e in st["eventos"]]
    assert "Lendo a fila da página" in textos  # marcador sai do texto
    assert "Lê o save" in textos                # descrição do Bash
    assert any("Bonfire Ascetic" in t for t in textos)
    feitas = [e["texto"] for e in st["eventos"] if e["tipo"] == "etapa"]
    assert feitas[:3] == ["Fila", "Save", "Pesquisa"]


def test_only_one_run_at_a_time(tmp_path):
    r = runner.Runner(command=fake_cmd(tmp_path, delay=1.5), cwd=tmp_path)
    r.start("plano", "x")
    with pytest.raises(runner.Busy):
        r.start("fila", "y")
    r.cancel()
    assert wait(r)["estado"] == "cancelado"


def test_events_since_index(tmp_path):
    r = runner.Runner(command=fake_cmd(tmp_path), cwd=tmp_path)
    r.start("plano", "x")
    st = wait(r)
    later = r.status(desde=st["eventos"][-1]["i"])
    assert later["eventos"] == []


def test_login_error_has_hint(tmp_path):
    r = runner.Runner(command=fake_cmd(tmp_path, login_error=True), cwd=tmp_path)
    r.start("plano", "x")
    st = wait(r)
    assert st["estado"] == "erro" and "/login" in st["mensagem"]


def test_default_command_is_headless_claude():
    cmd = runner.claude_command("/buildsmith:build ds2", claude="claude")
    assert cmd[:3] == ["claude", "-p", "/buildsmith:build ds2"]
    assert "--output-format" in cmd and "stream-json" in cmd and "--verbose" in cmd
    assert "--allowedTools" in cmd and "[etapa:" in cmd[cmd.index("--append-system-prompt") + 1]
