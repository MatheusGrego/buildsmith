---
name: build-page
description: Publica ou atualiza a página fixa do plano de build do buildsmith (estilo wiki do DS2, fluxos com ícones e tabelas de dados). Use no fim do /buildsmith:build, depois que o plano.json v2 estiver pronto.
---

# build-page

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

1. Grave o `plano.json` em `<scratchpad>/buildsmith-plano.json`.
2. Rode `python "<pasta>/scripts/prepare_page.py" <scratchpad>/buildsmith-plano.json ~/.buildsmith/paginas/<jogo>/<slug-do-personagem> --jogo <jogo>`.
   - Ele valida o plano, baixa os ícones (cache em `~/.buildsmith/cache/<jogo>/icons/`), copia o modelo e imprime `{"index", "files", "avisos"}`.
   - `{"error": ...}` → corrija o plano e rode de novo. `avisos` → ícones que não baixaram; o nó mostra a inicial do nome.
3. Servidor local (`<pasta>/../../app/serve.py`, porta 8642): se `http://127.0.0.1:8642/api/ping` não responder, suba em segundo plano com `pythonw "<app>/serve.py"` (Windows: `Start-Process pythonw -ArgumentList '"<app>\serve.py"'`). O jogador também pode abrir pelo atalho **Forja de Build** da área de trabalho (`app/instalar_atalho.py` cria).
4. Responda a fila com `serve.py responder` / `serve.py confirmar` (veja a skill `build`).
5. Responda com o link `http://127.0.0.1:8642/p/<jogo>/<slug-do-personagem>/` e as 2–3 linhas de `mudancas` mais importantes.

### Modo `publicar` (Artifact, para ver no celular)

- Prepare a página em `<scratchpad>/buildsmith-page/<jogo>/` (o Artifact só publica arquivos do diretório de trabalho ou do scratchpad).
- `~/.buildsmith/config.json`, chave `paginas.<jogo>.<personagem>`: **com URL** → `Artifact` `action: "read"` e depois publique com `url`, `file_path` = `index` e `files` da saída; **sem URL** → publique com `icon: "sword"`, `description` de uma frase e `capabilities: {"db": {}}`, e grave a URL.
- Nesse modo a fila fica no banco da página: leia e responda com `ArtifactData` (`pedidos`, `feitos`, `config/feiticos`).
