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

## Passos

1. Grave o `plano.json` em `<scratchpad>/buildsmith-plano.json`.
2. Rode `python "<pasta>/scripts/prepare_page.py" <scratchpad>/buildsmith-plano.json <scratchpad>/buildsmith-page/<jogo> --jogo <jogo>`.
   - Ele valida o plano, baixa os ícones (cache em `~/.buildsmith/cache/<jogo>/icons/`), copia o modelo e imprime `{"index", "files", "avisos"}`.
   - `{"error": ...}` → corrija o plano e rode de novo. `avisos` → ícones que não baixaram; o nó mostra a inicial do nome.
3. Leia `~/.buildsmith/config.json`, chave `paginas.<jogo>.<personagem>`.
   - **Tem URL:** `Artifact` com `action: "read"` nessa URL, depois publique com `url`, `file_path` = `index` e `files` = o objeto `files` da saída, sem mudar nada.
   - **Sem URL:** publique sem `url`, com `icon: "sword"` e `description` de uma frase; grave a URL em `config.json`.
4. Responda com o link e as 2–3 linhas de `mudancas` mais importantes.
