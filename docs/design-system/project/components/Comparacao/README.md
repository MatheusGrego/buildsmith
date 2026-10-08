# Comparacao

Bloco da aba Builds que compara o personagem com uma build da wiki (Você × Build) e sugere o ajuste como fluxo.

## Quando usar

- Use na aba Builds, na seção "Outras builds", um bloco por build comparada.
- Use para builds do mesmo arquétipo, tiradas da wiki, respeitando o que o jogador travou e o "sem migrar" do perfil (`skills/build/SKILL.md`, item `comparacao`).

## Quando não usar

- Não use para comparar o personagem com ele mesmo no tempo. Isso é Desde a última vez (ver Ficha).
- Não use para passo. O ajuste aqui é sugestão; o que entra no plano vira Passo.

## O que entra

`comparacao[]`: `{"build", "link", "dados": [Linha], "ajuste": [Nó]}`. `build` é obrigatório (`validate_plano.py` L101–L105). Em `dados`, `agora` é você, `depois` é a build e `efeito` é a diferença. Exemplo real (`example/plano.json` L1397 em diante, `icone` e `link` dos nós omitidos aqui):

```json
{"build": "Moonlight Battlemage", "link": "https://darksouls2.wiki.fextralife.com/PvE+Builds",
 "dados": [{"dado": "Arma principal", "agora": "Uchigatana", "depois": "Moonlight Greatsword", "efeito": "troca", "sinal": ""},
           {"dado": "STR", "agora": "10", "depois": "18", "efeito": "faltam 8", "sinal": "-"},
           {"dado": "DEX", "agora": "18", "depois": "18", "efeito": "ok", "sinal": "+"},
           {"dado": "INT", "agora": "26", "depois": "18+", "efeito": "ok", "sinal": "+"}],
 "ajuste": [{"tipo": "item", "nome": "Uchigatana", "sub": "agora", "tem": true},
            {"tipo": "item", "nome": "Old Paledrake Soul", "sub": "+ 10.000 almas"},
            {"tipo": "item", "nome": "Moonlight Greatsword", "sub": "depois"}]}
```

## Anatomia

`builds()` (`skills/build-page/template/index.html` L382–L389):

```html
<section><h2>Outras builds</h2><div class="blocks"><div class="block">
  <div class="block-head"><span class="step-title"><a class="" href="https://darksouls2.wiki.fextralife.com/PvE+Builds" target="_blank" rel="noopener noreferrer">Moonlight Battlemage</a></span></div>
  <div class="tw"><table><thead><tr><th>Dado</th><th>Você</th><th>Build</th><th>Diferença</th></tr></thead><tbody><tr><td>Arma principal</td><td>Uchigatana</td><td>Moonlight Greatsword</td><td class="">troca</td></tr><tr><td>STR</td><td>10</td><td>18</td><td class="neg">faltam 8</td></tr>…</tbody></table></div>
  <span class="label">Ajuste sugerido</span><div class="flow">…</div>
</div></div></section>
```

| Parte | Regra |
|---|---|
| `.blocks` | Grade com `gap: 0` (L96). |
| `.block` | Grade com `gap` `block-gap`, `padding-block` `block-pad-y`, borda de cima `border-hair` em `line` (L97). |
| `.block:first-child` | Sem borda, `padding-top` `list-first-pad-top` (L98). |
| `.block-head` | `display: flex`, `flex-wrap: wrap`, `align-items: center`, `gap: 8px 14px` (L99; sem token). |
| `.step-title` | Nome da build em `titulo-passo`, `head`. Com link, o `a` fica em `link` e com o sublinhado padrão do navegador. |
| tabela | `rows()` com Dado · Você · Build · Diferença (ver TabelaWiki). |
| `.label` | "Ajuste sugerido" em `selo` (Marcellus 13px), cor `text` (L100). |
| `.flow` | O ajuste (ver Fluxo). |

## Estados e variantes

- Com `link`: nome da build vira link da wiki, abre em outra aba.
- Sem `link`, ou link que não é http(s): nome em `head`, sem link.
- Sem `ajuste`, ou lista vazia: não aparecem o rótulo nem o fluxo.
- Várias builds: um `.block` por build, separados pela borda `line`.
- Sem comparação: `<section><h2>Outras builds</h2><p class="empty">Nenhuma comparação ainda.</p></section>` (L388).
- A aba mostra o contador com `comparacao.length` (L490).

## Regras de conteúdo

- Escreva a Diferença com palavra: "faltam 8" (`-`), "ok" (`+`), "troca" (`""`).
- Monte o ajuste como fluxo do que sai até o que entra, como na spec `2026-10-06-buildsmith-pagina-v2-design.md` ("Uchigatana ➜ Moonlight Greatsword"). No exemplo o custo vai no `sub` do nó do meio ("+ 10.000 almas").
- Escreva "—" quando o valor da build não tem fonte.
- Todo nó `item` do ajuste precisa de entrada em `itens` ou de `"tem": true` (`validate_plano.py` L246–L266).

## Acessibilidade

- O nome da build em `link` dá 6.19:1 sobre `panel`; o foco é o anel `focus-width` em `link`.
- `.label` em `text` dá 8.40:1 sobre `panel`.
- A Diferença traz a palavra além da cor: `neg` 5.40:1 e `pos` 7.80:1 sobre a célula.

## Tokens usados

Cor: `head`, `text`, `link`, `line`, `pos`, `neg`. Espaço: `block-gap`, `block-pad-y`, `list-first-pad-top`. Borda: `border-hair`. Tipo: `titulo-passo`, `selo`, `titulo-secao`, `vazio`. Mais os tokens de TabelaWiki e Fluxo.

## Problemas conhecidos

- O link da build herda o sublinhado do navegador (`aba-builds-desktop.png`); o título-link do painel Agora tira o sublinhado (`.agora-acao .step-title`, L149). Os dois usam `.step-title`.
- Sem `<caption>` e sem `scope` nos `<th>`.
