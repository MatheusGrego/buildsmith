# buildsmith — servidor local e app na área de trabalho

Data: 2026-10-07
Status: aprovado em conversa ("pode fazer o A, e depois um app pra ligar o servidor na área de trabalho")

## Por quê

Publicar no Artifact a cada `/build` custa tokens extras (lista de ~55 arquivos, leitura da página inteira antes de republicar em outro chat, chamadas ao banco). Uma página servida localmente lê os arquivos direto de `~/.buildsmith/`: o `/build` só reescreve o `plano.json`.

## Como funciona

```
~/.buildsmith/
  paginas/<jogo>/<personagem-slug>/   index.html + plano.json + icons/   (escrito pelo prepare_page)
  estado/<jogo>/<personagem-slug>.json  {"feitos": {}, "pedidos": {}, "config": {}}  (escrito pela página e pela skill)
  app/buildsmith.ico                  ícone do atalho (gerado na instalação)
```

`app/serve.py` (só biblioteca padrão), `127.0.0.1:8642`:

| Rota | O que faz |
|---|---|
| `GET /` | lista os personagens com página |
| `GET /p/<jogo>/<slug>/` | a página (com `<!doctype html>` e `charset=utf-8`) |
| `GET /p/<jogo>/<slug>/<arquivo>` | `plano.json`, `icons/*.png` |
| `GET /api/<jogo>/<slug>/estado` | estado (fila, fogueiras, feitiços) |
| `POST /api/<jogo>/<slug>/<feitos\|pedidos\|config>/<id>` | grava um documento (corpo JSON) |
| `GET /api/ping` | `{"app": "buildsmith"}` |
| `POST /api/desligar` | encerra o servidor |

- Caminhos validados (segmentos `[a-z0-9._-]`, sem `..`); só arquivos dentro da pasta da página.
- Gravação atômica do estado (arquivo temporário + `os.replace`).
- `serve.py --open`: se já houver um buildsmith na porta, só abre o navegador; senão sobe o servidor e abre a página mais recente no navegador padrão.
- CLI para a skill: `serve.py estado`, `serve.py responder`, `serve.py confirmar` (sem servidor rodando, direto no arquivo).

## Página

O modelo escolhe o armazenamento: `claude.use("db")` (Artifact) → senão a API local (`/api/...`, com consulta a cada 2 s e logo após cada gravação) → senão modo leitura (Pesquisar copia o comando).

## App na área de trabalho

`app/instalar_atalho.py`: baixa uma imagem de fogueira da wiki do DS2, monta `~/.buildsmith/app/buildsmith.ico` (16–256 px) e cria `Forja de Build.lnk` na área de trabalho apontando para `pythonw.exe app/serve.py --open` (sem janela de console).

## Publicar no Artifact

Continua disponível: `/buildsmith:build ds2 publicar` (para ver no celular).

## Segurança da execução sem janela (0.7.1)

Os botões rodam `claude -p` lendo a wiki, que qualquer um edita, sem ninguém olhando. Um texto plantado numa página (prompt injection) não pode virar código rodando na máquina nem dado vazando.

| Camada | O que faz |
|---|---|
| `app/guard.py` (hook `PreToolUse`, via `--settings`) | decide cada ferramenta por código: Bash só com os scripts do buildsmith (sem `&&`, `|`, `;`, `$()`, crase, variável, coringa), `mkdir`/`ls`/`date`; Write/Edit só em `~/.buildsmith/{config.json,profiles,history,cache,flags,tmp}` e no scratchpad; WebFetch só `https` na Fextralife; Read/Glob/Grep só no repositório, em `~/.buildsmith`, no scratchpad e na pasta da sessão; o resto (MCP, Agent, PowerShell) negado |
| `--permission-mode dontAsk`, sem `--allowedTools` | nada roda sem o "sim" do guarda; se o hook não carregar, tudo é negado |
| `--setting-sources project`, `--strict-mcp-config`, `--plugin-dir <repo>` | regras de permissão, MCP e plugins do usuário não valem nessa execução; o plugin vem do repositório que o guarda confere |
| `runner.check_guard` | antes de cada execução, testa o guarda (nega `python -c`, nega `example.com`, libera `ds2save levels`); falhou → não roda |
| `prepare_page` e página | ícone só baixa da Fextralife; a página só mostra ícone local (`icons/...`) e link `http(s)` (`javascript:`/`data:` viram texto) |

Bloqueios aparecem na barra de progresso ("Bloqueado: ..."). Validado de ponta a ponta com `claude -p` real: `python -c`, `&&`, WebFetch fora da wiki, gravação em `.claude/settings.json` e leitura de `/etc` negados; script do buildsmith, wiki e `~/.buildsmith/tmp` liberados.

### Auditoria de prompt injection (0.7.2)

Quatro lentes (fila, persistência, guarda, runner/servidor), cada achado reproduzido em código e conferido por um verificador cético: 13 de 15 confirmados. O guarda em si não teve brecha; os furos estavam no que o modelo podia gravar e no que voltava depois.

| Caminho | Antes | Agora |
|---|---|---|
| `CLAUDE.md` / `.claude/` numa pasta gravável (ex.: `cache/CLAUDE.md`) | o Claude Code anexa como regra do projeto quando a próxima execução lê algo ali (testado no CLI 2.1.293) | runner passa `CLAUDE_CODE_DISABLE_CLAUDE_MDS=1`; guarda nega `.claude`, nome com ponto no começo ou no fim, `CLAUDE.md`, `CLAUDE.local.md`, `AGENTS.md`, `SKILL.md` em qualquer pasta |
| Nome do personagem no `plano.json` | entrava cru no prompt do usuário do `claude -p` a cada clique | `build_prompt` usa só o slug da URL; `validate_plano` recusa nome com mais de 32 caracteres |
| Requisito da wiki → botão Pesquisar | texto com várias linhas ia para a fila ou para a área de transferência (colado no Claude Code interativo, sem guarda) | `limpaPedido` na página (uma linha, caracteres de nome de item, 120 no máximo) e o aviso mostra o que foi copiado; `validate_plano` recusa requisito acima de 80 caracteres e qualquer texto com quebra de linha |
| Perfil, `config.json`, flags | graváveis pela execução sem janela e lidos como escolha do jogador | só leitura sem janela (mudam na sessão interativa) |
| Formato do que se grava | qualquer arquivo em `history/`, `cache/`, `tmp/` | `history/**.json`, `cache/**.md|json`, `tmp/**.json|md|txt`; `mkdir` sem ponto no nome |
| `POST` da fila | qualquer campo, 64 KB, estado `respondido` | esquema por coleção, 4 KB, 50 pedidos na fila, só `na_fila` |
| CLI `responder`/`confirmar` | criava entrada nova com id livre | ids da página e só o que existe |
| Página inicial | nome de pasta sem escape | `html.escape`, só pastas no formato da página, CSP |
| Página do plano | sem CSP | `connect-src 'self'`, `img-src 'self' data:`: nada sai da página mesmo com um XSS |
| Ícone | `.../Pagina#/CLAUDE.md` virava `CLAUDE.md` no disco | nome só do caminho, sempre com extensão de imagem |
| Skill | qualquer uma | só `buildsmith:*` |

Testes: `tests/test_injection.py` (um teste por ataque) e `tests/test_injection_live.py` (`claude -p` real, opt-in com `BUILDSMITH_LIVE=1`: pede cada ataque e confere no disco que nada aconteceu).

## Testes

`tests/test_serve.py`: servidor em porta livre com `BUILDSMITH_HOME` temporário — página com charset, `plano.json`, gravação e leitura de estado, bloqueio de `..`, ping; CLI `estado`/`responder`.
