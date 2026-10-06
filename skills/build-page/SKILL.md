---
name: build-page
description: Publica ou atualiza a página fixa do plano de build (modelo HTML + plano.json) do buildsmith. Use no fim do /buildsmith:build, depois que o plano.json estiver pronto.
---

# build-page

## Passos

1. Monte o `plano.json` no formato descrito em `example/plano.json` desta pasta. Números de almas vêm do `ds2save.py levels`.
2. Valide: `python "<pasta>/scripts/validate_plano.py" <caminho>/plano.json`. Corrija até sair `ok`.
3. Copie `<pasta>/template/index.html` e o `plano.json` para `<scratchpad>/buildsmith-page/<jogo>/` (o Artifact só publica arquivos do diretório de trabalho ou do scratchpad).
4. Leia `~/.buildsmith/config.json`. Chave da página: `paginas.<jogo>.<personagem>`.
   - **Tem URL:** rode `Artifact` com `action: "read"` nessa URL, depois publique com `url`, `file_path` = `index.html` copiado e `files: {"plano.json": <caminho do plano.json copiado>}`.
   - **Sem URL:** publique sem `url`, com `icon: "sword"` e `description` de uma frase; grave a URL devolvida em `config.json`.
5. Responda com o link e as 2–3 mudanças mais importantes do plano.

O modelo HTML não muda entre execuções; só o `plano.json` muda.
