# No

Caixa que representa um elemento do jogo (item, chefe, inimigo, NPC, local, baú, almas ou atributo) com ícone, nome e uma legenda curta, e que vira link para a página da wiki.

## Quando usar

- Use sempre que a página cita algo do jogo: nós de um fluxo, equipamento da Ficha, item de Onde pegar, chefe e loja do Progresso, arma do Dano, feitiço e catalisador.
- Use a legenda (`sub`) para dizer o papel do nó naquele lugar: quantidade, preço, mão, área, "sai" ou "entra".

## Quando não usar

- Não use para um número ou valor de tabela. Valor vai em `td`.
- Não use para requisito de fonte. Requisito é texto com o botão Pesquisar, ou `.req-link` para outro item do plano.
- Não use para título de passo nem nome de build. Esses vão em `.step-title`.

## O que entra

Nó (`validate_plano.py` L28–L37, `skills/build-page/SKILL.md` L27):

| Campo | Regra | Vira |
|---|---|---|
| `tipo` | um de `item`, `chefe`, `inimigo`, `npc`, `local`, `bau`, `almas`, `atributo` | nada visível |
| `nome` | obrigatório, sem limite de tamanho | `.nm` |
| `sub` | opcional, até 30 caracteres | `.sub`; sem `sub` o nó é `.solo` |
| `link` | opcional, só `http(s)://` | `<a class="node">`; sem link, `<span class="node">` |
| `icone` | opcional, `https://` da wiki no plano | `img.ic` só depois que o `prepare_page.py` baixa para `icons/` |
| `tem` | opcional, `true` se o jogador já tem | nada visível; libera a regra de fechamento |

Exemplo real (`example/plano.json`, `personagem.equipado`):

```json
{"tipo": "item", "nome": "Uchigatana", "link": "https://darksouls2.wiki.fextralife.com/Uchigatana", "icone": "https://static0.fextralifeimages.com/file/darksouls2/thumb/d/df/Uchigatana_ds2.png/178px-Uchigatana_ds2.png", "sub": "R1 · +5"}
```

## Anatomia

`node()` (`skills/build-page/template/index.html` L273–L277):

```js
const inner = `${icon(n.icone, n.nome)}<span class="nm">${esc(n.nome)}</span>${n.sub ? `<span class="sub">${esc(n.sub)}</span>` : ""}`;
const solo = n.sub ? "" : " solo";
return n.link ? ext(n.link, inner, `node${solo}`) : `<span class="node${solo}">${inner}</span>`;
```

HTML real de cada variante:

```html
<!-- com link e sub -->
<a class="node" href="https://darksouls2.wiki.fextralife.com/Uchigatana" target="_blank" rel="noopener noreferrer"><span class="ini" aria-hidden="true">U</span><span class="nm">Uchigatana</span><span class="sub">R1 · +5</span></a>
<!-- com link, sem sub -->
<a class="node solo" href="https://darksouls2.wiki.fextralife.com/Dull+Ember" target="_blank" rel="noopener noreferrer"><span class="ini" aria-hidden="true">D</span><span class="nm">Dull Ember</span></a>
<!-- sem link, com sub -->
<span class="node"><span class="ini" aria-hidden="true">N</span><span class="nm">Ninho</span><span class="sub">após o Pursuer</span></span>
<!-- sem link, sem sub -->
<span class="node solo"><span class="ini" aria-hidden="true">B</span><span class="nm">Baú de ferro</span></span>
<!-- com ícone local -->
<img class="ic" src="icons/178px-Uchigatana_ds2.png" alt="" data-ini="U">
```

| Parte | Regra (L66–L73) |
|---|---|
| `.node` | Grade de duas colunas: `icon-node` e `minmax(0, auto)`, duas linhas, `column-gap` `node-icon-gap`, `align-items: center`. Padding `node-pad` em cima, embaixo e à esquerda, `node-pad-right` à direita. Fundo `td`, borda `border-hair` em `line`, cor `link`, sem sublinhado, `min-width: 0`, `max-width: 100%`. |
| `span.node` | Nome em `head`: sem link, o nó não parece clicável. |
| `.ic` | Imagem de `icon-node`, `object-fit: contain`, ocupa as duas linhas. |
| `.ini` | Quadrado de `icon-node` em `th`, letra em `head` com o estilo `inicial-no`, centrada. Ocupa as duas linhas. |
| `.nm` | Estilo `nome-no` (peso 500), `overflow-wrap: anywhere`. |
| `.sub` | Estilo `legenda-no` em `text`, na 2ª coluna. |
| `.solo` | Uma linha só. |
| `a.node:hover .nm` | Sublinha só o nome. |

Dentro de `td` o nó fica compacto (L117–L118): padding `node-pad-table` e `node-pad-right-table`, coluna do ícone `icon-node-table`, `column-gap` `node-icon-gap-table`, sem fundo e sem borda; a inicial usa `inicial-no-tabela`.

## Estados e variantes

| Situação | Resultado |
|---|---|
| `link` http(s) | `a.node`, nome em `link`, abre em outra aba |
| sem `link`, ou link que não é http(s) | `span.node`, nome em `head` (`safeUrl`, L257) |
| sem `sub` | `.solo`, uma linha |
| `icone` casa com `^icons\/[A-Za-z0-9._-]+$` | `img.ic` (L264–L265) |
| sem `icone`, ou ainda em `https://` | `.ini` com a inicial |
| imagem que falha | troca por `.ini` na hora (`fallbackIcons`, L266–L271) |
| hover em `a.node` | sublinha o `.nm` |
| dentro de `td` | compacto, sem caixa |

A inicial sai de `letter()` (L261): tira espaços e o "The " do começo, pega a 1ª letra em maiúscula; nome vazio vira "?". "The Tower Apart" vira "T"; "99.790 almas" vira "9".

O `tipo` não muda o visual. Chefe, NPC, local e item são iguais; a diferença vem do ícone.

## Regras de conteúdo

- Escreva o nome como no jogo e na wiki, em inglês: "Steady Hand McDuff", "Large Titanite Shard", "The Tower Apart". Lugar sem nome no jogo ganha descrição curta em português, como no exemplo: "Baú de ferro", "Corpo à esquerda", "Ninho".
- Escreva o `sub` com até 30 caracteres, nos padrões do exemplo: quantidade "×1", "×3"; preço "2.500 almas", "+ 10.000 almas"; mão e upgrade "R1 · +5", "L1 · +2", "R2"; slot "anel"; papel "sai", "entra", "agora", "depois"; área "Lost Bastille"; transição "tem 2 → 3", "nível 65 → 76".
- Ponha `link` só para a wiki, em `http(s)`.
- Ponha no plano o ícone `https://` da Fextralife. O `prepare_page.py` baixa e reescreve para `icons/<arquivo>`; a página nunca carrega ícone de fora.
- Marque `"tem": true` no item que o jogador já tem. Todo nó `item` citado em passo, dano, ajuste, `agora.faltam` ou feitiço sugerido precisa de entrada em `itens` ou de `tem` (`validate_plano.py` L246–L266).

## Acessibilidade

- O nome está sempre escrito. A imagem é decorativa (`alt=""`) e a inicial tem `aria-hidden="true"`.
- O foco do `a.node` é o anel `focus-width` em `link` com `focus-offset` (regra de `a:focus-visible`).
- Contraste sobre `td` em cima de `panel` (#2a2a2a): nome em `link` 5.01:1, nome em `head` 14.35:1, `sub` em `text` 6.79:1. A inicial em `head` sobre `th`: 18.88:1.
- A borda `line` do nó é decorativa (1.41:1 sobre `panel`).

## Tokens usados

Cor: `td`, `th`, `line`, `link`, `head`, `text`. Espaço: `node-pad`, `node-pad-right`, `node-icon-gap`, `node-pad-table`, `node-pad-right-table`, `node-icon-gap-table`, `equipped-gap`. Borda: `border-hair`. Ícone: `icon-node`, `icon-node-table`. Tipo: `nome-no`, `legenda-no`, `inicial-no`, `inicial-no-tabela`.

Os ícones da wiki não estão neste sistema. O preview mostra a inicial, que é o que a página mostra sem o arquivo.

## Problemas conhecidos

- Numa coluna de tabela espremida, `overflow-wrap: anywhere` (L70) deixa o nome quebrar uma letra por linha: "The Tower Apart", "Corpo à esquerda" e "Steady Hand McDuff" na aba Onde pegar a 400px (`recorte-onde-celular.png`); "Uchigat" / "ana" na aba Dano a 1280px (`aba-dano-desktop.png`).
- O plano de exemplo cru mostra só iniciais: os ícones estão em `https://` e a página só aceita `icons/…` até o `prepare_page.py` rodar.
- A spec `2026-10-06-buildsmith-pagina-v2-design.md` lista 7 tipos, sem `inimigo`; o validador aceita 8.
