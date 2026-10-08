# Selo

Etiqueta curta no estilo da wiki, em Marcellus 13px com borda fina sobre `th`, que diz numa palavra o estado de uma fonte, de um feitiço, de um chefe, de um evento ou de um pedido da fila.

## Quando usar

- Use para estado com vocabulário fixo, numa célula de tabela: Acesso e Destaque (Onde pegar), Estado (Feitiços, Chefes, Eventos, Fila).
- Use `td.selos` na célula quando a coluna pode levar mais de um selo.

## Quando não usar

- Não use para o que o jogador liga e desliga com um clique. Isso é a Fogueira.
- Não use para número, ganho ou perda. Isso é texto com `.pos` ou `.neg`.
- Não ponha ícone, check ou cor nova no selo.

## O que entra

| Campo do plano | Valor | Texto | Variante |
|---|---|---|---|
| `itens[].fontes[].acesso` | `agora` | Agora | `.feito` |
| | `em_breve` | Em breve | base |
| | `tarde` | Tarde | `.apagado` |
| `itens[].fontes[].destaques[]` | `mais_cedo` | Mais cedo | `.destaque` |
| | `mais_rentavel` | Mais rentável | `.destaque` |
| `feiticos.lista[].estado` | `equipado` | Equipado | `.feito` |
| | `sugerido` | Sugerido | `.destaque` |
| | `tem` | Tem | base |
| `progresso.chefes[].estado` | `derrotado` | Derrotado | `.feito` |
| | `vivo` | Vivo | base |
| `progresso.eventos[].estado` | `feito` | Feito | `.feito` |
| | `pendente` | Pendente | base |
| `pedidos/<id>.estado` (banco, não o plano) | `respondido` | Respondido | `.feito` |
| | `na_fila` | Na fila | base |

Os textos vêm dos mapas `ACESSO`, `DESTAQUE`, `ESTADO_FEITICO` e `ESTADO` (`skills/build-page/template/index.html` L241–L243, L397) e da tabela da Fila (L559). Valor fora do mapa sai cru, no selo base.

Exemplo real: a 1ª fonte de Smooth & Silky Stone (`example/plano.json` L831–L837) tem `"acesso": "agora"` e `"destaques": ["mais_cedo", "mais_rentavel"]`. Na tabela vira um selo Agora e dois selos de destaque na mesma célula.

## Anatomia

```html
<td class="selos"><span class="estado feito">Agora</span></td>
<td class="selos"><span class="estado destaque">Mais cedo</span><span class="estado destaque">Mais rentável</span></td>
<td><span class="estado">Vivo</span></td>
```

- `.estado` (L123): `display: inline-block`, estilo `selo` (Marcellus 13px, `letter-spacing: 0.04em`), padding `seal-pad-y` `seal-pad-x`, borda `border-hair` em `line`, fundo `th`, texto `text`, `white-space: nowrap`.
- `td.selos` (L130–L131): `white-space: nowrap`; o segundo selo da célula ganha `margin-left` `seal-gap`. Os selos saem colados no HTML; o espaço é só esse `margin-left`.
- O JS põe `td.selos` trocando `<td><span class="estado` por `<td class="selos"><span class="estado` (L370, L458, L561). As tabelas de Chefes e Eventos (L404, L407) não passam por essa troca.

## Estados e variantes

| Variante | Classe | Texto | Borda | Onde |
|---|---|---|---|---|
| Base | `.estado` | `text` | `line` | Em breve, Tem, Vivo, Pendente, Na fila |
| Feito | `.estado.feito` | `head` | `link` | Agora, Equipado, Derrotado, Feito, Respondido |
| Destaque | `.estado.destaque` | `pos` | `pos` | Mais cedo, Mais rentável, Sugerido |
| Apagado | `.estado.apagado` | `dim` | `line` | Tarde |

O fundo é sempre `th`. Não há hover, foco nem ARIA: o selo não é interativo.

## Regras de conteúdo

- Escreva uma ou duas palavras, caixa normal, sem ponto: "Em breve", "Mais rentável". A Marcellus SC desenha o versalete; não use `text-transform`.
- Use só o vocabulário da tabela acima. Estado novo pede um valor novo no mapa e uma variante existente.
- Feito é dourado (`link`), destaque é âmbar (`pos`). Nada de verde, nada de check.
- Deixe a palavra carregar o estado. A cor reforça.

## Acessibilidade

- O selo é texto puro, sem `role`. O leitor de tela lê a palavra.
- Contraste sobre `th`: base `text` 8.93:1; feito `head` 18.88:1, com borda `link` 6.59:1; destaque `pos` 10.26:1.
- Apagado (`dim` sobre `th`) dá 4.29:1 e falha 4.5:1 em 13px.
- "Em breve" (`text`) e "Tarde" (`dim`) ficam a 2.08:1 um do outro. O que separa os dois é a palavra.

## Tokens usados

- Cor: `th`, `line`, `text`, `head`, `link`, `pos`, `dim`.
- Espaço: `seal-pad-y`, `seal-pad-x`, `seal-gap`.
- Borda: `border-hair`.
- Tipo: `selo`.

## Problemas conhecidos

- O selo Tarde fica abaixo de 4.5:1 (`dim` sobre `th`, 4.29:1; ver Problemas conhecidos, item 8).
- A spec `docs/superpowers/specs/2026-10-06-buildsmith-progresso-dano-design.md` (L71) pede Vivo e Pendente "em texto apagado". O código usa o selo base, em `text`.
- O `white-space: nowrap` do selo e de `td.selos` (L123, L130) ajuda a espremer a coluna Como da tabela: no celular o nome do nó quebra uma letra por linha (`recorte-onde-celular.png`, `aba-feiticos-celular.png`; item 1). O preview reproduz isso em tela estreita.
- O selo Em breve sai com `class="estado "` (espaço no fim), porque `selo()` recebe classe vazia (L356, L362). Não muda o visual.
