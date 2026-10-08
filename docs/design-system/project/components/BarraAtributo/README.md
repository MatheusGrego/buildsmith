# BarraAtributo

Linha da aba Atributos com ícone, sigla, uma barra de 0 a 99 com o valor atual em `link` e a marca do alvo em `pos`, e o número ao lado.

## Quando usar

- Use na aba Atributos, uma linha para cada um dos 9 atributos, sempre na ordem VGR, END, VIT, ATN, STR, DEX, INT, FTH, ADP (L238).
- Use para mostrar onde o atributo está e onde a build quer chegar.

## Quando não usar

- Não use para custo ou ordem de subida. Isso é a TabelaFases.
- Não use para outro número de 0 a 99, nem para progresso de tarefa. A barra de etapas da Forja é outro componente.

## O que entra

`personagem.stats` e `alvo_stats`, com os 9 atributos como inteiros (`validate_plano.py` L75–L78). Exemplo real (`example/plano.json` L11–L21 e L74–L84):

```json
"stats":      {"VGR": 9,  "END": 6,  "VIT": 5, "ATN": 30, "STR": 10, "DEX": 18, "INT": 26, "FTH": 6, "ADP": 8}
"alvo_stats": {"VGR": 20, "END": 15, "VIT": 5, "ATN": 30, "STR": 10, "DEX": 25, "INT": 40, "FTH": 6, "ADP": 8}
```

## Anatomia

`stats()` (`skills/build-page/template/index.html` L326–L338), com `pct = (v) => Math.min(v, 99) / 99 * 100`. HTML real de VGR:

```html
<div class="stat">
  <img src="icons/stat-VGR.png" alt="" onerror="this.style.visibility='hidden'">
  <span class="abbr">VGR</span>
  <div class="bar" role="img" aria-label="VGR: 9 de 99, alvo 20"><div class="now" style="width:9.090909090909092%"></div><div class="goal" style="left:calc(20.2020202020202% - 1px)"></div></div>
  <span class="val">9 <span class="pos">→ 20</span></span>
</div>
```

As linhas ficam em `<section><h2>Atributos</h2><div class="stats">…</div></section>`.

| Parte | Regra (L86–L93) |
|---|---|
| `.stats` | Grade `repeat(auto-fill, minmax(stats-col-min, 1fr))`, `gap` `stats-gap-y` `stats-gap-x`. Três colunas a 1280px, uma no celular. |
| `.stat` | Grade de 4 colunas: `icon-stat`, `stat-abbr-col`, `minmax(0, 1fr)`, `stat-val-col`; `align-items: center`, `gap` `stat-gap`. |
| `img` | `icon-stat`, `object-fit: contain`. |
| `.abbr` | Família Marcellus SC (`rodape-tabela`), cor `head`. |
| `.bar` | `position: relative`, altura `bar-height`, fundo `track`, borda `border-hair` em `line`. Por dentro sobram 6px. |
| `.now` | Preenche da esquerda até o valor atual, em `link`. |
| `.goal` | Marca de `bar-goal-width` em `pos`, com `top` e `bottom` em `bar-goal-overhang`: passa 5px para fora em cima e embaixo, 16px de altura. O `calc(N% - 1px)` centra a marca no alvo. |
| `.val` | À direita, `head`, `tabular-nums`, sem quebra. O alvo vem em `.pos` com "→". |

O ícone `icons/stat-<ATR>.png` não está neste sistema. Sem o arquivo a página deixa a imagem invisível e guarda a coluna; o preview reproduz isso com uma `img` sem `src` e `visibility: hidden`.

## Estados e variantes

| Caso | Resultado |
|---|---|
| alvo maior que o atual | marca `.goal` e "→ alvo" em `.pos` (VGR 9 → 20, END 6 → 15, DEX 18 → 25, INT 26 → 40) |
| alvo igual ou menor | só a barra e o número (VIT 5, ATN 30, STR 10, FTH 6, ADP 8) |
| valor acima de 99 | a barra trava em 100% |
| ícone que falha | invisível, a coluna de `icon-stat` continua ocupada |

## Regras de conteúdo

- Use as siglas do jogo: VGR, END, VIT, ATN, STR, DEX, INT, FTH, ADP. Não use FOR nem DES.
- Defina `alvo_stats` a partir do perfil da build (`skills/build/SKILL.md`).
- Ponha os 9 atributos nos dois objetos, mesmo os que não mudam.

## Acessibilidade

- A barra é `role="img"` com `aria-label` no formato "VGR: 9 de 99, alvo 20". O rótulo sempre cita o alvo, mesmo igual ao atual ("VIT: 5 de 99, alvo 5").
- O número está escrito ao lado; a barra não é o único sinal.
- Contraste não textual: `.now` em `link` dá 4.94:1 sobre `track`; `.goal` em `pos` dá 7.70:1 sobre `track` e 9.65:1 sobre `panel`. O trilho vazio `track` dá 1.25:1 e a borda `line` 1.41:1: são decorativos.
- Valor em `head` sobre `panel`: 17.76:1. Alvo em `pos` sobre `panel`: 9.65:1.

## Tokens usados

Cor: `track`, `line`, `link`, `pos`, `head`. Espaço: `stats-gap-y`, `stats-gap-x`, `stat-gap`. Borda: `border-hair`. Ícone: `icon-stat`. Layout: `stats-col-min`, `stat-abbr-col`, `stat-val-col`, `bar-height`, `bar-goal-width`, `bar-goal-overhang`. Tipo: `rodape-tabela`, `corpo`, `titulo-secao`.

## Problemas conhecidos

- O ícone de atributo depende de `icons/stat-<ATR>.png` copiado pelo `prepare_page.py`. Sem ele, a coluna fica vazia (capturas `aba-atributos-desktop.png` e `aba-atributos-celular.png`).
- Nenhum defeito de layout registrado em Problemas conhecidos.
