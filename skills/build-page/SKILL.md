---
name: build-page
description: Publica ou atualiza a página fixa do plano de build do buildsmith (estilo wiki do DS2, fluxos com ícones e tabelas de dados). Use no fim do /buildsmith:build, depois que o plano.json v2 estiver pronto.
---

# build-page

## Regra de credibilidade (obrigatória, vale para tudo)

Nenhum fato de jogo vem da memória. Todo fato que aparece no plano, na página ou na resposta do chat precisa de **fonte verificada**:

- **O que conta como fato:** onde fica um item, NPC, chefe, baú ou fogueira; como chegar lá; requisito (atributo, chave, chefe, evento); quem vende, troca ou recebe o item; preço; efeito; drop, chance e quantidade; rota e ordem das áreas.
- **Fontes aceitas, nesta ordem:**
  1. **Tabelas do jogo e o save**, pelos scripts (`ds2save`, `ds2data`, `ds2calc`): números, lojas, trocas, requisitos, custos, progresso.
  2. **Wiki**, pela skill `wiki-cache` (URL + data, cache de até 30 dias): locais, rotas, baús, drops e efeitos que as tabelas não descrevem.
- **Sem fonte, não entra:** escreva `"—"` ou "não confirmado" e diga no chat o que faltou. Nunca complete com o que "deve ser".
- **Antes de publicar**, confira cada local, requisito e efeito do plano contra a fonte. Fonte e plano têm que dizer a mesma coisa.
- **Se o jogador contestar um fato**, verifique na fonte antes de responder. Se estava errado, diga isso claramente, corrija o cache e o plano.

Formato do plano: `example/plano.json` desta pasta (versão 2). Spec: `docs/superpowers/specs/2026-10-06-buildsmith-pagina-v2-design.md`.

## Regras do conteúdo

- **Nada de frase explicativa.** Todo passo é `fluxo` (nós com ícone e link) + `dados` (linhas Dado | Agora | Depois | Efeito).
- `sinal`: `"+"` = ganho (âmbar), `"-"` = perda ou falta (azul), `""` = neutro. Valor sem fonte = `"—"`.
- `titulo` até 40 caracteres; `sub` de nó até 30.
- Nó: `tipo` (`item, chefe, inimigo, npc, local, bau, almas, atributo`), `nome`, `link` da wiki, `icone` = URL do ícone da wiki (vem do cabeçalho `icone:` do `wiki-cache`), `sub` curto (`"×1"`, `"+ 1.500 almas"`, `"R1 · +5"`).
- Almas e níveis sempre do `ds2save.py levels`; dano sempre do `ds2calc.py ar`.
- `progresso` (aba Progresso) e `dano` (aba Dano) são opcionais; estado é texto (`derrotado`/`vivo`, `feito`/`pendente`), a página desenha o selo no estilo da wiki.
- `feiticos` (aba Feitiços), `agora` (painel no topo), `id` em passos e itens, e requisito `{"texto", "item"}` estão em `example/plano.json` e no spec `2026-10-07-buildsmith-feiticos-fila-ux-design.md`.

## Passos

Padrão: **página local** (sem Artifact, mais barata). Só publique no Artifact quando o pedido tiver `publicar`.

1. Grave o `plano.json` em `<scratchpad>/buildsmith-plano.json` (sem scratchpad, rodando pela página: `~/.buildsmith/tmp/buildsmith-plano.json`).
2. Rode `python "<pasta>/scripts/prepare_page.py" <scratchpad>/buildsmith-plano.json ~/.buildsmith/paginas/<jogo>/<slug-do-personagem> --jogo <jogo>`.
   - Ele valida o plano, baixa os ícones (cache em `~/.buildsmith/cache/<jogo>/icons/`), copia o modelo e imprime `{"index", "files", "avisos"}`.
   - `{"error": ...}` → corrija o plano e rode de novo. `avisos` → ícones que não baixaram; o nó mostra a inicial do nome.
3. Servidor local (`<pasta>/../../app/serve.py`, porta 8642; rodando pela página ele já está de pé): se `http://127.0.0.1:8642/api/ping` não responder, suba em segundo plano com `pythonw "<app>/serve.py"` (Windows: `Start-Process pythonw -ArgumentList '"<app>\serve.py"'`). O jogador também pode abrir pelo atalho **Forja de Build** da área de trabalho (`app/instalar_atalho.py` cria).
4. Responda a fila com `serve.py responder` / `serve.py confirmar` (veja a skill `build`).
   - Aberta pelo servidor, a página tem os botões **Atualizar plano** e **Responder fila**: rodam esta skill sem janela (`app/runner.py`, `claude -p`) e mostram etapas + microtexto. Visual: `docs/design-system.md`.
5. Responda com o link `http://127.0.0.1:8642/p/<jogo>/<slug-do-personagem>/` e as 2–3 linhas de `mudancas` mais importantes.

### Modo `publicar` (Artifact, para ver no celular)

- Prepare a página em `<scratchpad>/buildsmith-page/<jogo>/` (o Artifact só publica arquivos do diretório de trabalho ou do scratchpad).
- `~/.buildsmith/config.json`, chave `paginas.<jogo>.<personagem>`: **com URL** → `Artifact` `action: "read"` e depois publique com `url`, `file_path` = `index` e `files` da saída; **sem URL** → publique com `icon: "sword"`, `description` de uma frase e `capabilities: {"db": {}}`, e grave a URL.
- Nesse modo a fila fica no banco da página: leia e responda com `ArtifactData` (`pedidos`, `feitos`, `config/feiticos`).
