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

## Testes

`tests/test_serve.py`: servidor em porta livre com `BUILDSMITH_HOME` temporário — página com charset, `plano.json`, gravação e leitura de estado, bloqueio de `..`, ping; CLI `estado`/`responder`.
