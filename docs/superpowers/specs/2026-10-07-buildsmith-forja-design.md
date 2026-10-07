# Forja: rodar a skill pela página

## Objetivo

Os botões **Atualizar plano** e **Responder fila** da página local rodam `/buildsmith:build` sem abrir o Claude Code e mostram o progresso: barra de etapas + microtexto rolando com o que o Claude está fazendo.

## Peças

- `app/runner.py`: `Runner.start(modo, prompt, alvo)` sobe `claude -p <prompt> --output-format stream-json --verbose --allowedTools ... --append-system-prompt <marcadores>` em segundo plano (sem janela no Windows), cwd `~/.buildsmith`. Uma execução por vez (`Busy`).
- Etapas: `fila, save, perfil, pesquisa, calculos, pagina, resposta, fim`. Vêm do marcador `[etapa:<id>]` que o prompt de sistema pede no texto, com heurística pelas ferramentas como reserva (`ds2save` → save, `WebFetch` → pesquisa, `prepare_page` → página...). Só avançam.
- Microtexto: texto do assistente, pensamento e cada ferramenta resumida (descrição do Bash, página da wiki, arquivo lido/gravado). Até 400 eventos com índice `i`; a página pede `?desde=i`.
- Fim: `result` do stream (custo, resposta) → `ok`; `is_error` → `erro` (falha de login vira "rode claude e use /login"); processo sem `result` → `erro` com as últimas linhas; Cancelar mata a árvore (`taskkill /T`).
- Stream cru da última execução em `~/.buildsmith/execucoes/ultima.jsonl`.

## API (`app/serve.py`)

| Rota | Faz |
|---|---|
| `GET /api/ping` | `{"rodar": true}` liga os botões |
| `POST /api/<jogo>/<personagem>/rodar` `{"modo": "plano"\|"fila"}` | inicia; 409 se já tem execução |
| `GET /api/<jogo>/<personagem>/execucao?desde=N` | status, etapas, eventos novos, segundos, custo |
| `POST /api/<jogo>/<personagem>/cancelar` | cancela |

Prompt: `/buildsmith:build <jogo> [fila] (pela página, personagem: <nome do plano>)`. O texto dos pedidos não entra no prompt; a skill lê a fila do arquivo de estado.

## Segurança

Servidor só em 127.0.0.1. Todo POST exige `X-Buildsmith: 1`, `Host` local e `Origin` local ou ausente: outro site aberto no navegador não consegue enfileirar nem rodar (o cabeçalho próprio força preflight, que o servidor não aceita). GET exige `Host` local (DNS rebinding).

## Página

Botões no cabeçalho (só quando o servidor tem runner). Durante a execução: título, etapa atual "Pesquisa · 4 de 8", relógio, Cancelar; barra segmentada; microtexto de 6 linhas que segue o fim (para de seguir se o jogador rolar para cima). No fim: tempo + custo em US$, resposta da skill, faixa "PLANO FORJADO" e o plano recarrega sozinho. Estilo em `docs/design-system.md`.
