#!/usr/bin/env python3
"""Guarda das execuções sem janela (claude -p) que os botões da página disparam.

O runner.py instala este arquivo como hook PreToolUse (via --settings). O claude -p lê a wiki, que qualquer
um edita: um texto escondido numa página pode tentar fazer o modelo rodar código, gravar fora do lugar,
deixar instrução para a próxima execução ou mandar dados para fora. Aqui cada chamada de ferramenta é
decidida por código, não pelo modelo:

  Bash             só os scripts do buildsmith (python "<script>" <subcomando> ...), mkdir, ls e date;
                   sem &&, |, ;, $(), crase, variável nem coringa; "> arquivo" só onde o Write grava.
  Write/Edit       só history/*.json, cache/*.md|json e tmp/*.json|md|txt em ~/.buildsmith, e o scratchpad.
                   Perfil, config.json e flags ficam só leitura aqui (mudam numa sessão interativa).
                   Nunca .claude/, CLAUDE.md, AGENTS.md nem SKILL.md: o Claude Code carrega esses arquivos
                   sozinho como instrução, e um texto plantado viraria regra das próximas execuções.
  WebFetch         só https na wiki (Fextralife).
  Read/Glob/Grep   só no repositório, em ~/.buildsmith, no scratchpad e na pasta da sessão.
  Skill            só as do buildsmith. WebSearch, ToolSearch e lista de tarefas: liberadas.
  Qualquer outra (MCP, Agent, PowerShell...): negada.

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
    "skills/ds2-save/scripts/ds2save.py": {"slots", "snapshot", "levels", "flags-diff", "posicao"},
    "skills/ds2-save/scripts/ds2calc.py": {"ar", "catalisador", "feitico", "sintonia"},
    "skills/ds2-save/scripts/ds2perto.py": {"catalisadores", "armas", "armaduras", "feiticos"},
    "skills/ds2-save/scripts/ds2equip.py": None,
    "skills/ds2-save/scripts/ds2data.py": {"onde-comprar", "trocas", "custo-upgrade", "acesso"},
    "skills/ds2-save/scripts/ds2mapa.py": {"areas", "extrair", "onde", "rota"},
    "skills/build-page/scripts/prepare_page.py": None,
    "skills/build-page/scripts/validate_plano.py": None,
    "app/serve.py": {"estado", "responder", "confirmar"},
}
SERVE_OPTS = {"--personagem", "--jogo", "--pedido", "--item", "--passo", "--resultado"}
# ds2mapa sem --game/--cache: sem janela, só a instalação padrão e o cache de ~/.buildsmith.
MAPA_OPTS = {"--area", "--item", "--de", "--ate"}
AREA = re.compile(r"^m\d\d_\d\d_\d\d_\d\d$")
PONTO = re.compile(r"^(fogueira|item|inimigo):\d{1,10}$")
PYTHONS = {"python", "python3", "py", "python.exe", "python3.exe", "py.exe"}
PYTHON_FLAGS = {"-u", "-B", "-3", "-Xutf8"}
ENV_OK = {"PYTHONIOENCODING=utf-8", "PYTHONUTF8=1"}
DATE_OPTS = {"-u", "--utc", "-I", "-Idate", "-Ihours", "-Iminutes", "-Iseconds",
             "--iso-8601", "--iso-8601=date", "--iso-8601=minutes", "--iso-8601=seconds"}
# O que a execução sem janela grava em ~/.buildsmith, por pasta.
WRITE_EXT = {"history": (".json",), "cache": (".md", ".json"), "tmp": (".json", ".md", ".txt")}
SCRATCH_EXT = (".json", ".md", ".txt")
# Arquivos que o Claude Code carrega sozinho como instrução (memória de projeto, skill, agente).
RESERVED = {"claude.md", "claude.local.md", "agents.md", "skill.md"}
WIKI_HOSTS = ("fextralife.com", "fextralifeimages.com")
FREE_TOOLS = {"WebSearch", "ToolSearch", "TodoWrite", "TaskCreate", "TaskUpdate", "TaskList", "TaskGet"}
READ_TOOLS = {"Read", "Glob", "Grep"}
EDIT_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}
# Fora de aspas o bash expandiria ou encadearia; dentro de aspas nenhum nome de item usa.
BAD_CHARS = set("$`\n\r*?[]{}#\0")
PUNCT = set("();<>|&")
GAME = re.compile(r"^[a-z0-9]+$")
SEGMENT = re.compile(r"^[a-z0-9][a-z0-9._-]{0,180}$")  # o mesmo do serve.py (pastas e ids da página)
# Nome de arquivo ou pasta gravável: sem ponto no começo (.claude), sem : / \ < > " | ~ e sem ponto ou
# espaço no fim (o Windows corta, e "CLAUDE.md." viraria CLAUDE.md).
PART = re.compile(r"^\w[\w .,'()+&-]*(?<![ .])$")
DIR_PART = re.compile(r"^\w[\w -]*(?<! )$")  # pasta criada com mkdir: sem ponto nenhum


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


def _names_ok(parts, pattern, what: str) -> None:
    for part in parts:
        if not pattern.match(part) or part.lower() in RESERVED:
            raise Deny(f"{what}: nome não permitido: {part}")


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

    def read_roots(self):
        return [REPO, self.home, self.scratch, self.session]

    def need(self, raw, roots, what: str) -> Path:
        path = self.path(raw)
        if not under(path, roots):
            raise Deny(f"{what} fora das pastas permitidas: {path}")
        return path

    def _relative(self, path: Path, what: str) -> tuple[tuple[str, ...], str]:
        """Partes do caminho dentro do scratchpad ou de ~/.buildsmith, e a pasta de cima."""
        if self.scratch and path != self.scratch and under(path, [self.scratch]):
            return path.relative_to(self.scratch).parts, "scratchpad"
        if path != self.home and under(path, [self.home]):
            parts = path.relative_to(self.home).parts
            return parts, parts[0]
        raise Deny(f"{what} fora de ~/.buildsmith e do scratchpad: {path}")

    def writable(self, raw, what: str = "gravação") -> Path:
        """Arquivo que a execução sem janela pode gravar: formato fixo por pasta."""
        path = self.path(raw)
        parts, top = self._relative(path, what)
        exts = SCRATCH_EXT if top == "scratchpad" else WRITE_EXT.get(top) if len(parts) > 1 else None
        if exts is None:
            raise Deny(f"{what} só em ~/.buildsmith/{{{','.join(WRITE_EXT)}}} e no scratchpad "
                       f"(perfil, config.json e flags: só leitura aqui): {path}")
        _names_ok(parts, PART, what)
        if not path.name.lower().endswith(exts):
            raise Deny(f"{what}: em {top}/ só {', '.join(exts)}")
        return path

    def creatable_dir(self, raw) -> Path:
        path = self.path(raw)
        parts, top = self._relative(path, "mkdir")
        if top != "scratchpad" and top not in WRITE_EXT:
            raise Deny(f"mkdir só em ~/.buildsmith/{{{','.join(WRITE_EXT)}}} e no scratchpad: {path}")
        _names_ok(parts, DIR_PART, "mkdir")
        return path

    def page_dir(self, raw) -> Path:
        """Pasta de saída do prepare_page: paginas/<jogo>/<personagem>, ou em tmp/ e no scratchpad."""
        path = self.path(raw)
        paginas = self.home / "paginas"
        if under(path, [paginas]):
            parts = path.relative_to(paginas).parts
            if len(parts) != 2 or not all(SEGMENT.match(p) for p in parts):
                raise Deny("pasta da página: use paginas/<jogo>/<personagem> (letras minúsculas, números e -)")
            return path
        parts, top = self._relative(path, "pasta da página")
        if top not in ("tmp", "scratchpad"):
            raise Deny(f"pasta da página só em paginas/, tmp/ ou no scratchpad: {path}")
        _names_ok(parts, PART, "pasta da página")
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
    if rel.endswith("ds2mapa.py"):
        for name, value in _options(args[1:], MAPA_OPTS):
            if name == "--area" and not AREA.match(value):
                raise Deny("--area é um mapa como m10_16_00_00")
            if name in ("--de", "--ate") and not PONTO.match(value):
                raise Deny(f"{name} é fogueira:<id>, item:<lote> ou inimigo:<id>")
            if name == "--item" and len(value) > 80:
                raise Deny("--item longo demais")
        return
    if rel == "app/serve.py":
        for name, value in _options(args[1:], SERVE_OPTS):
            if name == "--jogo" and not GAME.match(value):
                raise Deny("--jogo inválido")
            if name in ("--pedido", "--item", "--passo") and not SEGMENT.match(value):
                raise Deny(f"{name} precisa ser um id da página (letras minúsculas, números e -)")
            if name == "--resultado" and value not in ("sim", "nao"):
                raise Deny("--resultado é sim ou nao")
            if name == "--personagem" and len(value) > 80:
                raise Deny("--personagem longo demais")
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
            if name == "--jogo" and not GAME.match(value):
                raise Deny("--jogo inválido")
            if name == "--cache" and ctx.path(value) != ctx.home / "cache":
                raise Deny("--cache só ~/.buildsmith/cache")
        if len(positional) != 2:
            raise Deny("prepare_page: use <plano.json> <pasta da página>")
        ctx.need(positional[0], ctx.read_roots(), "plano")
        ctx.page_dir(positional[1])


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
        ctx.writable(redirect, "redirecionamento")

    head = tokens[0]
    if head in ("mkdir", "ls", "date"):
        if redirect is not None:
            raise Deny(f"{head} sem redirecionamento")
        args = tokens[1:]
        if head == "date":
            if any(a not in DATE_OPTS and not a.startswith("+") for a in args):
                raise Deny("date só com +FORMATO, -u ou -I")
            return "date"
        for arg in args:
            if arg.startswith("-"):
                if head == "mkdir" and arg not in ("-p", "--parents"):
                    raise Deny("mkdir só com -p")
                continue
            if head == "mkdir":
                ctx.creatable_dir(arg)
            else:
                ctx.need(arg, ctx.read_roots(), "ls")
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


def check_skill(tool_input: dict) -> str:
    name = str(tool_input.get("skill") or "").lstrip("/")
    if not name.startswith("buildsmith:"):
        raise Deny(f"só as skills do buildsmith (buildsmith:...); pedida: {name or '?'}")
    return name


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
        if tool == "Skill":
            return "allow", f"skill {check_skill(tool_input)}"
        if tool in READ_TOOLS:
            check_read(tool, tool_input, ctx)
            return "allow", "leitura dentro das pastas do buildsmith"
        if tool in EDIT_TOOLS:
            ctx.writable(tool_input.get("file_path") or tool_input.get("notebook_path"))
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
