# Abas

Barra `.tabs` presa no topo do painel que mostra uma seção por vez: onze botões `.tab`, com contador opcional, cada um ligado a um `.tab-panel`.

## Quando usar

- Use uma barra só, depois do Agora, como filho direto do `.panel`. A margem negativa encosta a barra nas bordas do painel.
- Ponha no `.count` o número de itens da seção quando ele ajuda a escolher a aba.

## Quando não usar

- Não use abas dentro de uma aba, nem para filtrar uma tabela.
- Não ponha contador com zero. Sem número, sem `.count`.
- Não crie aba nova para um bloco que cabe numa seção existente.

## O que entra

| Aba (`id`) | Rótulo | Contador (`skills/build-page/template/index.html` L481–L493) | No exemplo |
|---|---|---|---|
| `ficha` | Ficha | `mudancas.length`, se maior que 0 | sem contador |
| `passos` | Passos | `passos.length` | 11 |
| `progresso` | Progresso | chefes com `"estado": "derrotado"` | 5 |
| `dano` | Dano | `dano.length`, se maior que 0 | 4 |
| `feiticos` | Feitiços | `feiticos.lista.length` | 11 |
| `atributos` | Atributos | nenhum | sem contador |
| `fases` | Fases | `fases.length` | 4 |
| `onde` | Onde pegar | `itens.length` | 15 |
| `builds` | Builds | `comparacao.length` | 1 |
| `fila` | Fila | pedidos abertos no banco (L563–L565) | sem contador até haver pedido |
| `fontes` | Fontes | `fontes.length` | 16 |

A aba inicial é a primeira que existir entre o `#hash` da URL, `localStorage["buildsmith-aba"]` e `passos` (L494–L497).

## Anatomia

HTML de `render(p)` (L500–L501):

```html
<nav class="tabs" role="tablist" aria-label="Seções">
  <button class="tab" role="tab" id="aba-ficha" aria-controls="painel-ficha" aria-selected="false" data-tab="ficha">Ficha</button>
  <button class="tab" role="tab" id="aba-passos" aria-controls="painel-passos" aria-selected="true" data-tab="passos">Passos<span class="count">11</span></button>
  …
</nav>
<div class="tab-panel" role="tabpanel" id="painel-passos" aria-labelledby="aba-passos">…</div>
<div class="tab-panel" role="tabpanel" id="painel-ficha" aria-labelledby="aba-ficha" hidden>…</div>
```

- `.tabs` (L106): `position: sticky`, `top: env(safe-area-inset-top, 0px)`, `z-index` `z-tabs`, flex sem gap, `overflow-x: auto`, fundo `panel`, borda inferior `border-hair` em `line`, `margin-inline: calc(-1 * panel-pad-x)`, `padding-inline` `panel-pad-x`, `scrollbar-width: thin`.
- `.tab` (L107): `flex: none`, flex com `gap: 6px`, padding `tab-pad-y` `tab-pad-x`, sem fundo, borda inferior `border-tab` transparente, texto `text` no estilo `aba` (Marcellus 15px, `letter-spacing: 0.03em`), `cursor: pointer`.
- `.tab .count` (L111): estilo `contador` (12px `body`), `link` sobre `th`, borda `border-hair` em `line`, padding `0` `count-pad-x`.
- `.tab-panel` (L112–L113): grid com `gap` `tab-panel-gap`; `[hidden]` vira `display: none`.

## Estados e variantes

| Estado | Gatilho | Visual |
|---|---|---|
| Normal | `aria-selected="false"` | texto `text`, borda inferior transparente |
| Hover | `:hover` | texto `head` |
| Selecionada | `aria-selected="true"` | texto `head`, borda inferior `link` |
| Foco | `:focus-visible` | anel `focus-width` em `link`, `outline-offset: -2px` (para dentro, porque a barra corta o que passa da borda) |
| Com contador | `span.count` | número em `link` sobre `th` |
| Fila com pedido aberto | `applyState()` reescreve o botão (L565) | `Fila<span class="count">2</span>` |

Comportamento: clique ou seta chama `select(id)` (L517–L522). Ele marca a aba, mostra só o `#painel-<id>`, grava a aba em `localStorage` e troca o `#hash` com `history.replaceState`. Os links internos usam `goTo()` (L523–L527): trocam de aba e rolam suave até o alvo.

## Regras de conteúdo

- Use os rótulos na ordem fixa: Ficha, Passos, Progresso, Dano, Feitiços, Atributos, Fases, Onde pegar, Builds, Fila, Fontes. Uma ou duas palavras, caixa normal.
- O contador é só o número. Escreva-o quando for maior que zero.
- O rótulo pode ser mais curto que o `h2` do painel: "Fases" abre "Fases de nível" (ver TituloSecao).

## Acessibilidade

- `nav[role="tablist"][aria-label="Seções"]`. Cada botão tem `role="tab"`, `id="aba-<id>"`, `aria-controls="painel-<id>"` e `aria-selected`. Cada painel tem `role="tabpanel"` e `aria-labelledby="aba-<id>"`.
- Teclado (L507–L514): seta direita e seta esquerda, em círculo. O foco anda e a aba ativa junto.
- Contraste sobre `panel`: `text` 8.40:1, `head` 17.76:1, indicador `link` 6.19:1. Contador `link` sobre `th`: 6.59:1.
- A aba ativa não depende só da cor do texto: tem a linha `border-tab` em `link`.

## Tokens usados

- Cor: `panel`, `line`, `text`, `head`, `link`, `th`.
- Espaço: `panel-pad-x`, `tab-pad-y`, `tab-pad-x`, `count-pad-x`, `tab-panel-gap`.
- Borda e foco: `border-hair`, `border-tab`, `focus-width`.
- Outros: `z-tabs`.
- Tipo: `aba`, `contador`.

## Problemas conhecidos

- As 11 abas passam da largura do painel e a barra corta a última sem aviso: "Fi" na borda direita a 1280px (`topo-desktop.png`, `aba-dano-desktop.png`) e "pegar" no começo a 400px (`aba-fontes-celular.png`). Não há degradê nem seta (ver Problemas conhecidos, item 3).
- Não há `Home` nem `End`, e todas as abas ficam na ordem do Tab: as não selecionadas não têm `tabindex="-1"` (item 14).
- O contador fica colado ao rótulo no nome acessível: "Passos11".
- A rolagem suave de `goTo()` ignora `prefers-reduced-motion` (L526; item 18).
