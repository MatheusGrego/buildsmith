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

## Testes

`tests/test_serve.py`: servidor em porta livre com `BUILDSMITH_HOME` temporário — página com charset, `plano.json`, gravação e leitura de estado, bloqueio de `..`, ping; CLI `estado`/`responder`.
