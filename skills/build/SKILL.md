---
name: build
description: Planeja a evolução da build a partir do save real do jogo e publica a página do plano. Use quando o usuário digitar /buildsmith:build <jogo>, pedir plano de build, perguntar quanto falta de alma, o que upar, onde pegar item ou como melhorar a build. Jogo suportado: ds2 (Dark Souls II SotFS).
---

# build

Argumentos: `<jogo> [pedido livre]`. Hoje só `ds2`; outro jogo → diga que ainda não há leitor de save para ele.

Dados do usuário em `~/.buildsmith/` (crie as pastas se faltarem): `config.json`, `profiles/<jogo>/`, `history/<jogo>/<personagem>/`, `cache/<jogo>/`.

## Passos

1. **Ficha:** rode o `snapshot` da skill `ds2-save` (`<pasta>/../ds2-save/scripts/ds2save.py`). Se `config.json` tiver `slots.ds2`, passe `--slot`. Erro de "mais de um personagem": rode `slots`, pergunte, grave a escolha em `config.json`.
2. **Histórico:** grave a saída em `history/ds2/<personagem>/<AAAA-MM-DDTHH-MM>.json`. Compare com o arquivo anterior: níveis, atributos, itens novos, upgrades. Isso vira `mudancas` (vazio na primeira vez: "primeira leitura").
3. **Perfil:** leia `profiles/ds2/<personagem>.yaml`. Se não existir, pergunte (uma pergunta por vez, múltipla escolha): arquétipo, itens que não quer trocar, foco secundário. Grave no formato:
   ~~~yaml
   personagem: Melatonina Vorcaro
   slot: 1
   arquetipo: mago INT + espada DEX
   secundario: piromancia (INT+FTH, soft cap 60)
   travados: [Uchigatana]
   nao_migrar: true
   notas: []
   ~~~
   Se o `pedido` mudar o foco ("agora quero piro"), atualize o perfil e diga o que mudou.
4. **Plano** (formato v2: `../build-page/example/plano.json`):
   - **Sem frases.** Cada passo é `fluxo` (de onde → para onde, com nós) + `dados` (Dado | Agora | Depois | Efeito, com `sinal` + ou −). Ex.: `Ruin Sentinels ➜ Ruin Sentinel Soul ➜ Straid (+ 1.500 almas) ➜ Heavy Homing Soul Arrow`.
   - Defina `alvo_stats` a partir do perfil e dos atributos atuais. Divida em `fases` de 1 atributo cada (com `atributo`), sobrevivência primeiro quando VGR < 20.
   - Custo de cada fase: `ds2save.py levels --from <nível inicial> --to <nível final>`. Nada de conta manual.
   - Efeitos numéricos (PV por nível de VGR, efeito de anel, escala de arma, preço) vêm da skill `wiki-cache`, junto com `link` e `icone` de cada nó. Sem fonte → `"—"`.
   - `mudancas`: compare com o snapshot anterior e gere linhas (Dado | Antes | Agora | Efeito).
   - `itens`: nó do item + `onde` como fluxo (ex.: `The Tower Apart ➜ Baú de ferro`) + `dados`.
   - `comparacao`: builds do mesmo arquétipo via `wiki-cache`; `dados` com Você × Build e `ajuste` como fluxo. Respeite `travados` e `nao_migrar`; nunca proponha recomeçar a build.
   - `passos`: no máximo 7, em ordem de execução, começando pelo que dá para fazer na área atual do jogador.
5. **Página:** siga a skill `build-page`.
6. **Resposta no chat:** primeira linha = próximo passo concreto; depois o link da página; no máximo 5 linhas.
