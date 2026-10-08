# TabelaWiki

Tabela no estilo da wiki Fextralife que carrega todo dado numérico ou comparativo da página: contorno claro de 3px, cabeçalho preto em Marcellus SC e células cinza translúcidas com texto branco.

## Quando usar

- Use para todo dado que compara ou soma: Dado | Agora | Depois | Efeito de um passo, Desde a última vez, Com o item, Você × Build, Chefes, Compras, Eventos, Dano, Feitiços, Fases e Ficha.
- Use a variante com sinal (`rows()`) quando a linha é uma mudança com ganho ou perda. Use a genérica (`grid()`) quando as células já trazem nó, selo, botão ou número formatado.

## Quando não usar

- Não ponha nós soltos numa tabela de uma coluna. Equipamento vai em `.equipped` (ver No).
- Não use para texto corrido nem para a lista de Fontes (`ul.sources`).
- Não monte tabela fora de `.tw`.

## O que entra

Linha (`rows()`, `skills/build-page/template/index.html` L280–L284): `{"dado", "agora", "depois", "efeito", "sinal"}`. `dado` é obrigatório; `sinal` é `"+"`, `"-"` ou `""` (`validate_plano.py` L16, L53–L56). Exemplo real, passo "Large Titanite Shard ×1" do `example/plano.json`:

```json
{"dado": "Large Titanite Shard", "agora": "2", "depois": "3", "efeito": "+1 (pro +6)", "sinal": "+"},
{"dado": "Almas", "agora": "0", "depois": "−2.500", "efeito": "faltam 2.500", "sinal": "-"}
```

Genérica (`grid(heads, lines, right)`, L391–L395): `heads` é a lista de cabeçalhos, `lines` é uma lista de células já em HTML e `right` lista os índices das colunas alinhadas à direita.

## Anatomia

HTML que `rows()` gera para o exemplo acima:

```html
<div class="tw"><table><thead><tr><th>Dado</th><th>Agora</th><th>Depois</th><th>Efeito</th></tr></thead><tbody><tr><td>Large Titanite Shard</td><td>2</td><td>3</td><td class="pos">+1 (pro +6)</td></tr><tr><td>Almas</td><td>0</td><td>−2.500</td><td class="neg">faltam 2.500</td></tr></tbody></table></div>
```

HTML que `grid()` gera com coluna à direita (Compras do Progresso, `right = [2]`):

```html
<div class="tw"><table><thead><tr><th>Loja</th><th>Item</th><th class="r">Qtd</th></tr></thead><tbody><tr><td><a class="node solo" …>…</a></td><td><a class="node solo" …>…</a></td><td class="r">5</td></tr></tbody></table></div>
```

| Parte | Regra (L53–L61) |
|---|---|
| `.tw` | `overflow-x: auto`. A tabela rola aqui dentro; a página não rola. |
| `table` | `border-collapse: collapse`, `width: 100%`, `min-width` `table-min-width`, contorno `border-table` em `edge`. |
| `th` | Fundo `th`, texto `head`, estilo `cabecalho-tabela`, à esquerda, padding `cell-pad-y` `cell-pad-x`, `white-space: nowrap`. Sem borda própria: o contorno vem da tabela e as divisórias do `td`. |
| `td` | Fundo `td`, texto `head`, borda `border-hair` em `line`, mesmo padding, `vertical-align: middle`, `font-variant-numeric: tabular-nums`. Texto em `corpo`. |
| `td.r`, `th.r` | Alinha à direita. |
| `td.pos`, `td.neg` | Cor `pos` ou `neg` e peso 500 na coluna Efeito (`cls()`, L259). `td class=""` fica neutro, em `head`. |
| `tfoot td` | Troca a família para Marcellus SC (`rodape-tabela`). Só existe em Fases. |
| `.cell-ic` | Ícone e valor na mesma célula: `display: flex`, `gap` `cell-icon-gap`; a imagem em `icon-small`. Só em Ficha (Nível) e Fases (Fase). |
| `td .node`, `td .flow` | Nó e fluxo ficam compactos dentro da célula (ver No e Fluxo). |
| `td.selos` | `white-space: nowrap`; dois selos lado a lado com `seal-gap`. Entra por troca de texto em Onde pegar, Feitiços e Fila. |

Tabelas da página:

| Tabela | Cabeçalhos | À direita |
|---|---|---|
| Ficha | Nível · Almas em mãos · Soul memory · Objetivo | 2ª e 3ª |
| Desde a última vez | Dado · Antes · Agora · Efeito | nenhuma |
| Passo | Dado · Agora · Depois · Efeito | nenhuma |
| Fases | Fase · Nível · Custo (almas) · Acumulado | 3ª e 4ª |
| Onde pegar, fontes | # · Como · Requisito · Acesso · Rendimento · Destaque | nenhuma |
| Onde pegar, item | Dado · Agora · Com o item · Efeito | nenhuma |
| Builds | Dado · Você · Build · Diferença | nenhuma |
| Chefes | Chefe · Estado | nenhuma |
| Compras | Loja · Item · Qtd | Qtd |
| Eventos | Evento · Estado | nenhuma |
| Dano | Arma · Agora · Depois · Diferença · Mudança · Por causa de | Agora, Depois, Diferença |
| Feitiços | (vazio) · Feitiço · Estado · Elemento · AR · Usos · Slots · Requisito | AR, Usos, Slots |
| Fila | Pedido · De onde · Estado · Resposta | nenhuma |

## Estados e variantes

- Efeito com sinal: `+` vira `td.pos`, `-` vira `td.neg`, `""` fica neutro.
- Lista vazia: `rows()` devolve nada e a tabela some. A seção mostra o próprio `.empty` quando tem um.
- Coluna à direita: pelo parâmetro `right` de `grid()` ou fixa no HTML da Ficha e das Fases.
- Rodapé: só nas Fases, `<tfoot>` com a linha de total.
- Tela estreita: abaixo de `table-min-width` a tabela rola dentro do `.tw`.
- Sem zebra, sem hover de linha.

## Regras de conteúdo

- Envolva toda `table` em `.tw`.
- Escreva `agora`, `depois` e `efeito` já formatados em pt-BR: milhar com ponto ("2.500"), decimal com vírgula ("+12,5%"), menos com "−" (U+2212). A página só escapa o texto (`esc`, L255).
- Escreva "—" quando o dado não tem fonte.
- Ponha a palavra no Efeito ("faltam 2.500", "economia 16.840", "ok", "usada"). A cor só reforça.
- Marque `sinal` "+" para ganho, "-" para perda ou falta e "" para o que não é nenhum dos dois ("3 por nível de +4 a +6").
- Deixe para a página os números que ela formata com `Intl.NumberFormat("pt-BR")` (`fmt`, L254): nível, almas, soul memory, custo e acumulado de fase, dano, AR, usos, slots, quantidade.
- Escreva o cabeçalho em caixa normal e curto. A Marcellus SC já desenha versalete.

## Acessibilidade

- Contraste sobre a célula (`td` sobre `panel` = #2a2a2a): `head` 14.35:1, `pos` 7.80:1, `neg` 5.40:1, `link` 5.01:1. `head` sobre `th`: 18.88:1. Todos passam 4.5:1.
- O contorno `edge` dá 12.58:1 sobre `panel`. A divisória `line` (1.41:1) é decorativa e nunca é o único sinal.
- Ganho e perda nunca vão só pela cor: o texto do Efeito traz o sinal ou a palavra.

## Tokens usados

Cor: `edge`, `th`, `td`, `head`, `line`, `pos`, `neg`. Espaço: `cell-pad-y`, `cell-pad-x`, `cell-icon-gap`, `seal-gap`. Borda: `border-table`, `border-hair`. Ícone: `icon-small`. Layout: `table-min-width`. Tipo: `cabecalho-tabela`, `corpo`, `rodape-tabela`.

## Problemas conhecidos

- Coluna espremida: a tabela tem `width: 100%` e as colunas com `white-space: nowrap` guardam a largura. A coluna com nó encolhe até o mínimo que `.node .nm { overflow-wrap: anywhere }` deixa, e o nome quebra no meio ou uma letra por linha (capturas `aba-dano-desktop.png` e `recorte-onde-celular.png`).
- Sem `<caption>` e sem `scope` nos `<th>` (L283, L392–L394, L303, L348–L351). A tabela de Feitiços abre com um `<th>` vazio (L458).
- A wiki centraliza cabeçalho e valores e usa `<th>` na 1ª coluna; aqui tudo vai à esquerda e a 1ª coluna é `td` (ver Wiki e fidelidade).
- A spec `2026-10-06-buildsmith-pagina-v2-design.md` chama o contorno de `--table-edge`; o código usa `edge`.
