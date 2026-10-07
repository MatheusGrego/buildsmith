#!/usr/bin/env python3
"""Guarda das execuções sem janela (claude -p) que os botões da página disparam.

O runner.py instala este arquivo como hook PreToolUse (via --settings). O claude -p lê a wiki, que qualquer
um edita: um texto escondido numa página pode tentar fazer o modelo rodar código, gravar fora do lugar ou
mandar dados para fora. Aqui cada chamada de ferramenta é decidida por código, não pelo modelo:

  Bash             só os scripts do buildsmith (python "<script>" <subcomando> ...), mkdir, ls e date;
                   sem &&, |, ;, $(), crase, variável nem coringa; "> arquivo" só para as pastas graváveis.
  Write/Edit       só em ~/.buildsmith/{config.json, profiles, history, cache, flags, tmp} e no scratchpad.
  WebFetch         só https na wiki (Fextralife).
  Read/Glob/Grep   só no repositório, em ~/.buildsmith, no scratchpad e na pasta da sessão.
  Skill, WebSearch, ToolSearch e lista de tarefas: liberadas. Qualquer outra (MCP, Agent, PowerShell...): negada.

Na dúvida, nega. Erro do próprio guarda também nega. Só biblioteca padrão.
"""
import json
import os
import re
import shlex
import sys
from pathlib import Path
from urllib.parse import urlsplit

REPO = Path(__file__).resolve().parents[1]

# script (relativo ao repositório) → subcomandos aceitos (None = sem subcomando)
SCRIPTS = {
    "skills/ds2-save/scripts/ds2save.py": {"slots", "snapshot", "levels", "flags-diff"},
    "skills/ds2-save/scripts/ds2calc.py": {"ar", "catalisador", "feitico"},
    "skills/ds2-save/scripts/ds2data.py": {"onde-comprar", "trocas", "custo-upgrade", "acesso"},
    "skills/build-page/scripts/prepare_page.py": None,
    "skills/build-page/scripts/validate_plano.py": None,
    "app/serve.py": {"estado", "responder", "confirmar"},
}
SERVE_OPTS = {"--personagem", "--jogo", "--pedido", "--item", "--passo", "--resultado"}
PYTHONS = {"python", "python3", "py", "python.exe", "python3.exe", "py.exe"}
PYTHON_FLAGS = {"-u", "-B", "-3", "-Xutf8"}
ENV_OK = {"PYTHONIOENCODING=utf-8", "PYTHONUTF8=1"}
DATE_OPTS = {"-u", "--utc", "-I", "-Idate", "-Ihours", "-Iminutes", "-Iseconds",
             "--iso-8601", "--iso-8601=date", "--iso-8601=minutes", "--iso-8601=seconds"}
WRITE_DIRS = ("profiles", "history", "cache", "flags", "tmp")
WIKI_HOSTS = ("fextralife.com", "fextralifeimages.com")
FREE_TOOLS = {"Skill", "WebSearch", "ToolSearch", "TodoWrite", "TaskCreate", "TaskUpdate", "TaskList", "TaskGet"}
READ_TOOLS = {"Read", "Glob", "Grep"}
EDIT_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}
# Fora de aspas o bash expandiria ou encadearia; dentro de aspas nenhum nome de item usa.
BAD_CHARS = set("$`\n\r*?[]{}#\0")
PUNCT = set("();<>|&")
SEGMENT = re.compile(r"^[a-z0-9]+$")


class Deny(Exception):
    pass


def default_home() -> Path:
    return Path(os.environ.get("BUILDSMITH_HOME") or Path.home() / ".buildsmith")


def windows_path(raw: str, nt: bool = os.name == "nt") -> str:
    """No Windows o Bash é o Git Bash: /c/Users/... vira C:/Users/..."""
    match = re.match(r"^/([A-Za-z])(/|$)", raw) if nt else None
    return f"{match.group(1).upper()}:/{raw[3:]}" if match else raw


def under(path: Path, roots) -> bool:
    return any(root is not None and (path == root or path.is_relative_to(root)) for root in roots)


class Context:
    def __init__(self, data: dict, home: Path | None = None):
        self.home = Path(home or default_home()).expanduser().resolve()
        self.cwd = Path(data.get("cwd") or self.home)
        scratch, transcript = data.get("scratchpad_dir"), data.get("transcript_path")
        self.scratch = Path(scratch).resolve() if scratch else None
        self.session = Path(transcript).with_suffix("").resolve() if transcript else None  # tool-results/ da sessão

    def path(self, raw) -> Path:
        if not isinstance(raw, str) or not raw.strip():
            raise Deny("caminho vazio")
        path = Path(os.path.expanduser(windows_path(raw.strip())))
        if not path.is_absolute():
            path = self.cwd / path
        return path.resolve()

    def write_roots(self):
        return [self.home / d for d in WRITE_DIRS] + [self.scratch]

    def page_roots(self):
        return [self.home / "paginas", self.home / "tmp", self.scratch]

    def read_roots(self):
        return [REPO, self.home, self.scratch, self.session]

    def need(self, raw, roots, what: str) -> Path:
        path = self.path(raw)
        if not under(path, roots):
            raise Deny(f"{what} fora das pastas permitidas: {path}")
        return path


def split(command: str) -> list[str]:
    lex = shlex.shlex(command, posix=True, punctuation_chars=True)
    lex.whitespace_split = True
    lex.commenters = ""
    try:
        return list(lex)
    except ValueError as err:
        raise Deny(f"comando mal formado ({err})") from err


def _options(args: list[str], allowed: set[str]) -> list[tuple[str, str]]:
    """Pares --opção valor (ou --opção=valor). Opção fora da lista (abreviação inclusive) é negada."""
    pairs, i = [], 0
    while i < len(args):
        name, eq, value = args[i].partition("=")
        if name not in allowed:
            raise Deny(f"opção não permitida: {args[i]}")
        if not eq:
            if i + 1 >= len(args):
                raise Deny(f"{name} sem valor")
            value, i = args[i + 1], i + 1
        pairs.append((name, value))
        i += 1
    return pairs


def _script(rel: str, args: list[str], ctx: Context) -> None:
    subcommands = SCRIPTS[rel]
    if subcommands is not None and (not args or args[0] not in subcommands):
        raise Deny(f"{Path(rel).name}: subcomando precisa ser um de {sorted(subcommands)}")
    if rel == "app/serve.py":
        for name, value in _options(args[1:], SERVE_OPTS):
            if name == "--jogo" and not SEGMENT.match(value):
                raise Deny("--jogo inválido")
    elif rel.endswith("prepare_page.py"):
        positional, rest = [], list(args)
        while rest:  # só <plano> <saida> e --jogo/--cache; "--" e outras opções são negadas
            token = rest.pop(0)
            if not token.startswith("-"):
                positional.append(token)
                continue
            name, eq, value = token.partition("=")
            if name not in ("--jogo", "--cache"):
                raise Deny(f"opção não permitida: {token}")
            if not eq:
                if not rest:
                    raise Deny(f"{name} sem valor")
                value = rest.pop(0)
            if name == "--jogo" and not SEGMENT.match(value):
                raise Deny("--jogo inválido")
            if name == "--cache":
                ctx.need(value, [ctx.home / "cache"], "cache")
        if len(positional) != 2:
            raise Deny("prepare_page: use <plano.json> <pasta da página>")
        ctx.need(positional[0], ctx.read_roots(), "plano")
        ctx.need(positional[1], ctx.page_roots(), "pasta da página")


def check_bash(tool_input: dict, ctx: Context) -> str:
    if tool_input.get("run_in_background"):
        raise Deny("rode em primeiro plano")
    command = tool_input.get("command")
    if not isinstance(command, str) or not command.strip():
        raise Deny("comando vazio")
    bad = sorted(set(command) & BAD_CHARS)
    if bad:
        raise Deny(f"caractere não permitido: {' '.join(repr(c) for c in bad)}")
    tokens = split(command)
    redirect = None
    if len(tokens) >= 2 and tokens[-2] in (">", ">>"):
        redirect, tokens = tokens[-1], tokens[:-2]
    if any(t and set(t) <= PUNCT for t in tokens):
        raise Deny("sem &&, |, ;, < ou parênteses: um comando por vez")
    if not tokens:
        raise Deny("comando vazio")
    if redirect is not None and redirect != "/dev/null":
        ctx.need(redirect, ctx.write_roots(), "redirecionamento")

    head = tokens[0]
    if head in ("mkdir", "ls", "date"):
        if redirect is not None:
            raise Deny(f"{head} sem redirecionamento")
        args = tokens[1:]
        if head == "date":
            if any(a not in DATE_OPTS and not a.startswith("+") for a in args):
                raise Deny("date só com +FORMATO, -u ou -I")
            return "date"
        roots = [ctx.home, ctx.scratch] if head == "mkdir" else ctx.read_roots()
        for arg in args:
            if arg.startswith("-"):
                if head == "mkdir" and arg not in ("-p", "--parents"):
                    raise Deny("mkdir só com -p")
                continue
            ctx.need(arg, roots, head)
        return head

    i = 0
    while i < len(tokens) and tokens[i] in ENV_OK:
        i += 1
    if i >= len(tokens) or tokens[i] not in PYTHONS:
        raise Deny("só scripts do buildsmith (python \"<script>\" ...), mkdir, ls e date")
    i += 1
    while i < len(tokens) and (tokens[i] in PYTHON_FLAGS or tokens[i] == "-X" and tokens[i + 1:i + 2] == ["utf8"]):
        i += 2 if tokens[i] == "-X" else 1
    if i >= len(tokens):
        raise Deny("falta o script")
    if tokens[i].startswith("-"):
        raise Deny(f"opção do python não permitida: {tokens[i]}")
    script = ctx.path(tokens[i])
    rel = next((r for r in SCRIPTS if script == (REPO / r).resolve()), None)
    if rel is None or not script.is_file():
        raise Deny(f"script fora do buildsmith: {script}")
    _script(rel, tokens[i + 1:], ctx)
    return rel


def check_url(url) -> str:
    parts = urlsplit(url if isinstance(url, str) else "")
    host = (parts.hostname or "").lower()
    if parts.scheme != "https" or parts.username or parts.password or parts.port not in (None, 443):
        raise Deny("WebFetch só com https simples")
    if not any(host == h or host.endswith("." + h) for h in WIKI_HOSTS):
        raise Deny(f"WebFetch só na wiki ({', '.join(WIKI_HOSTS)}); host: {host or '?'}")
    return host


def check_read(tool: str, tool_input: dict, ctx: Context) -> None:
    roots = ctx.read_roots()
    if tool == "Read":
        ctx.need(tool_input.get("file_path"), roots, "leitura")
        return
    if tool_input.get("path"):
        ctx.need(tool_input["path"], roots, "busca")
    pattern = str(tool_input.get("pattern") or "") if tool == "Glob" else ""
    if ".." in re.split(r"[\\/]", pattern):
        raise Deny("padrão com ..")
    static = re.split(r"[*?\[{]", pattern, maxsplit=1)[0]
    if static and (static[0] in "/\\~" or Path(static).is_absolute()):
        ctx.need(static, roots, "busca")


def check_edit(tool_input: dict, ctx: Context) -> None:
    raw = tool_input.get("file_path") or tool_input.get("notebook_path")
    path = ctx.path(raw)
    if path != ctx.home / "config.json" and not under(path, ctx.write_roots()):
        raise Deny(f"gravação só em ~/.buildsmith/{{config.json,{','.join(WRITE_DIRS)}}} e no scratchpad: {path}")


def decide(data: dict, home: Path | None = None) -> tuple[str, str]:
    """('allow' | 'deny', motivo) para uma chamada de ferramenta."""
    try:
        tool = data.get("tool_name")
        tool_input = data.get("tool_input") or {}
        if not isinstance(tool_input, dict):
            raise Deny("entrada inválida")
        ctx = Context(data, home)
        if tool in FREE_TOOLS:
            return "allow", f"{tool} liberada"
        if tool in READ_TOOLS:
            check_read(tool, tool_input, ctx)
            return "allow", "leitura dentro das pastas do buildsmith"
        if tool in EDIT_TOOLS:
            check_edit(tool_input, ctx)
            return "allow", "gravação dentro de ~/.buildsmith"
        if tool == "WebFetch":
            return "allow", f"wiki: {check_url(tool_input.get('url'))}"
        if tool == "Bash":
            return "allow", f"buildsmith: {check_bash(tool_input, ctx)}"
        raise Deny(f"ferramenta {tool} não é usada pelo buildsmith")
    except Deny as err:
        return "deny", f"guarda do buildsmith: {err}"
    except Exception as err:  # noqa: BLE001 (erro do guarda = negar)
        return "deny", f"guarda do buildsmith: erro interno ({type(err).__name__})"


def main() -> int:
    try:
        data = json.loads(sys.stdin.buffer.read().decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError
    except (ValueError, UnicodeDecodeError):
        data = {}
    decision, reason = decide(data) if data else ("deny", "guarda do buildsmith: entrada ilegível")
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                             "permissionDecision": decision, "permissionDecisionReason": reason}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
