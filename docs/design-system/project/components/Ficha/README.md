# Ficha

Aba Ficha: o retrato atual do personagem numa tabela de uma linha (Nível, Almas em mãos, Soul memory, Objetivo), os nós do equipamento e a seção Desde a última vez.

## Quando usar

- Use uma vez, na aba Ficha, com a seção "Ficha" seguida de "Desde a última vez".
- Use os nós do equipamento para o que está equipado agora, com a mão ou o slot no `sub`.

## Quando não usar

- Não use para atributos. Atributos têm aba própria (ver BarraAtributo).
- Não use para o que vai mudar. Mudança planejada é passo (ver Passo); mudança já lida do save é Desde a última vez.

## O que entra

| Campo | Exemplo real (`example/plano.json`) | Vira |
|---|---|---|
| `personagem.level` | `65` | coluna Nível, formatado com `fmt` |
| `personagem.souls` | `0` | Almas em mãos, à direita |
| `personagem.soul_memory` | `221118` | Soul memory, à direita: "221.118" |
| `objetivo` | `"Mago INT + Uchigatana DEX · piro secundária · sem migrar"` | coluna Objetivo |
| `personagem.equipado` | 7 nós: Uchigatana `R1 · +5`, Sorcerer's Staff `L1 · +2`, Pyromancy Flame `R2`, Life Ring, Covetous Silver Serpent Ring+1, Clear Bluestone Ring e Old Leo Ring com `anel` | `.equipped` |
| `mudancas` | `[]` | Desde a última vez |

`personagem` precisa de `name`, `level`, `souls`, `soul_memory`, `stats` e `equipado` (`validate_plano.py` L71–L73). Em `mudancas`, o campo `agora` guarda a leitura anterior e aparece na coluna "Antes"; o campo `depois` guarda a leitura atual e aparece na coluna "Agora".

## Anatomia

`sheet()` e `changes()` (`skills/build-page/template/index.html` L300–L311):

```html
<section><h2>Ficha</h2>
  <div class="tw"><table><thead><tr><th>Nível</th><th class="r">Almas em mãos</th><th class="r">Soul memory</th><th>Objetivo</th></tr></thead>
    <tbody><tr><td><span class="cell-ic"><img src="icons/almas.png" alt="" onerror="this.remove()">65</span></td><td class="r">0</td><td class="r">221.118</td><td>Mago INT + Uchigatana DEX · piro secundária · sem migrar</td></tr></tbody></table></div>
  <div class="equipped"><a class="node" href="https://darksouls2.wiki.fextralife.com/Uchigatana" target="_blank" rel="noopener noreferrer"><span class="ini" aria-hidden="true">U</span><span class="nm">Uchigatana</span><span class="sub">R1 · +5</span></a>…</div>
</section>
<section><h2>Desde a última vez</h2><p class="empty">Primeira leitura do save.</p></section>
```

| Parte | Regra |
|---|---|
| tabela | TabelaWiki de uma linha; 2ª e 3ª colunas com `.r`. |
| `.cell-ic` | Ícone `icons/almas.png` em `icon-small` antes do nível, `gap` `cell-icon-gap`. |
| `.equipped` | `display: flex`, `flex-wrap: wrap`, `gap` `equipped-gap` (L74). Os nós ficam fora de tabela: caixa cheia com ícone de `icon-node`. |
| Desde a última vez | `rows(p.mudancas, ["Dado", "Antes", "Agora", "Efeito"])` ou `.empty`. |
| seções | Dentro do `.tab-panel`, separadas por `tab-panel-gap`. |

O ícone `icons/almas.png` não está neste sistema. Sem o arquivo a página remove a imagem (`onerror="this.remove()"`); o preview já vem sem ela.

## Estados e variantes

- `mudancas` vazia: "Primeira leitura do save." em `.empty` (`vazio`).
- `mudancas` com linhas: tabela Dado | Antes | Agora | Efeito, com sinal na coluna Efeito.
- A aba mostra o contador com `mudancas.length` e fica sem número quando a lista está vazia (L482).
- Ícone do nível que falha: some, e o nível fica sozinho na célula.

## Regras de conteúdo

- Grave `level`, `souls` e `soul_memory` como inteiros. A página põe o milhar.
- Escreva o `objetivo` curto, com os campos separados por "·".
- Escreva o `sub` do equipamento com a mão e o upgrade ("R1 · +5", "L1 · +2", "R2") ou com o slot ("anel").
- Tire nível, almas e soul memory do save, nunca de cabeça.

## Acessibilidade

- Sobre a célula: `head` 14.35:1. Nome de nó em `link` 5.01:1 sobre `td`.
- Os nós equipados são links da wiki e abrem em outra aba; o foco é o anel `focus-width` em `link`.

## Tokens usados

Cor: os da TabelaWiki e do No. Espaço: `equipped-gap`, `cell-icon-gap`, `tab-panel-gap`, `section-gap`, `title-rule-gap`. Ícone: `icon-small`, `icon-node`. Tipo: `titulo-secao`, `corpo`, `vazio`, `cabecalho-tabela`.

## Problemas conhecidos

- A tabela não tem `<caption>` nem `scope` nos `<th>` (L303).
- A wiki abre a página do item com um infobox (nome, imagem, pares ícone e valor); a Ficha é uma tabela de uma linha mais os nós (ver Wiki e fidelidade).
