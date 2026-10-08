# Progresso

Aba Progresso com o que o save prova, em três tabelas wiki: chefes com selo Derrotado ou Vivo, compras feitas e eventos aprendidos.

## Quando usar

- Use no painel da aba `progresso` quando o plano tem `progresso` (`skills/build-page/template/index.html` L484).
- Mostre só o que veio do save e das tabelas do jogo. Eventos entram depois que o jogador ensina a skill (spec `2026-10-06-buildsmith-progresso-dano-design.md`, "Aprender eventos").

## Quando não usar

- Não use para o que falta fazer. Isso é Passo.
- Não marque progresso com ícone de check nem com texto riscado. Feito é o selo com borda `link`.
- Não use a fogueira aqui. A fogueira é marcação do jogador; o Progresso é o que o save confirma.

## O que entra

`progresso` (`example/plano.json` L1539–L2054, `icone` e `link` omitidos):

```json
{"chefes": [
   {"no": {"tipo": "chefe", "nome": "The Pursuer", "sub": "Forest of Fallen Giants"}, "estado": "derrotado"},
   {"no": {"tipo": "chefe", "nome": "The Duke's Dear Freja", "sub": "Brightstone Cove Tseldora"}, "estado": "vivo"}],
 "compras": [
   {"loja": {"tipo": "npc", "nome": "Lonesome Gavlan"}, "item": {"tipo": "item", "nome": "Poison Moss"}, "qtd": 5}],
 "eventos": []}
```

O exemplo tem 41 chefes (5 derrotados), 10 compras e nenhum evento. O caso de evento vem do spec `2026-10-06-buildsmith-progresso-dano-design.md` (L52, L63), no formato do plano: `{"nome": "Straid libertado", "estado": "feito"}`.

## Anatomia

`progress()` (L400–L412) e `estado()` (L397–L398):

```html
<section><h2>Chefes<small>5 de 41 derrotados</small></h2><div class="tw"><table><thead><tr><th>Chefe</th><th>Estado</th></tr></thead><tbody>
  <tr><td><a class="node" href="…"><span class="ini" aria-hidden="true">P</span><span class="nm">The Pursuer</span><span class="sub">Forest of Fallen Giants</span></a></td><td><span class="estado feito">Derrotado</span></td></tr>
  <tr><td><a class="node" href="…"><span class="ini" aria-hidden="true">D</span><span class="nm">The Duke's Dear Freja</span><span class="sub">Brightstone Cove Tseldora</span></a></td><td><span class="estado">Vivo</span></td></tr>
</tbody></table></div></section>
<section><h2>Compras<small>10</small></h2><div class="tw"><table><thead><tr><th>Loja</th><th>Item</th><th class="r">Qtd</th></tr></thead><tbody>
  <tr><td><a class="node solo" href="…">…Lonesome Gavlan…</a></td><td><a class="node solo" href="…">…Poison Moss…</a></td><td class="r">5</td></tr>
</tbody></table></div></section>
<section><h2>Eventos</h2><div class="tw"><table><thead><tr><th>Evento</th><th>Estado</th></tr></thead><tbody>
  <tr><td>Straid libertado</td><td><span class="estado feito">Feito</span></td></tr>
</tbody></table></div></section>
```

| Parte | Regra |
|---|---|
| Seções | Três `section` no `.tab-panel`, separadas por `tab-panel-gap`. Título `h2` com contagem em `small` (ver TituloSecao). |
| Tabelas | Tabela wiki (ver TabelaWiki). Chefe, Loja e Item são nós compactos dentro de `td` (ver No). Qtd à direita (`.r`), formatada com `Intl` pt-BR. |
| Selo | `.estado.feito` para Derrotado e Feito (borda `link`, texto `head`); `.estado` neutro para Vivo e Pendente (borda `line`, texto `text`) (L123–L124, L398; ver Selo). |

Os ícones da wiki não estão neste sistema. O preview mostra a inicial em `.ini`, sem o "The " do começo ("The Pursuer" vira "P").

## Estados e variantes

| Caso | Resultado |
|---|---|
| Chefe derrotado / vivo | selo Derrotado em `.estado.feito` / Vivo em `.estado` |
| Evento feito / pendente | selo Feito em `.estado.feito` / Pendente em `.estado` |
| Estado fora do mapa | o valor sai cru (`ESTADO[value] || value`, L398) |
| Contagem dos chefes | "<derrotados> de <total> derrotados" no `small` (L409); o mesmo número de derrotados vai no contador da aba (L484) |
| Contagem das compras | o total no `small` (L410) |
| Sem chefes | `<p class="empty">Nenhum chefe listado.</p>` (L404) |
| Sem compras | `<p class="empty">Nenhuma compra registrada.</p>` (L405) |
| Sem eventos | `<p class="empty">Nenhum evento aprendido. Rode /buildsmith:build ds2 antes e depois do evento, contando o que aconteceu.</p>` (L408) |
| Sem `progresso` | uma seção "Progresso" com "Este plano não tem dados de progresso." (L402) |

## Regras de conteúdo

- Use `estado` de chefe entre `derrotado` e `vivo`, e de evento entre `feito` e `pendente` (`validate_plano.py` L17–L18, L275, L285). Rótulos fixos: Derrotado, Vivo, Feito, Pendente (template L397).
- Ponha os chefes derrotados primeiro (`skills/build/SKILL.md` L65).
- Use o `sub` do chefe para a área: "Forest of Fallen Giants", "Iron Keep". Até 30 caracteres (`validate_plano.py` L36).
- Escreva `qtd` como inteiro (L280–L281). Loja e item são nós.
- Dê ao evento um nome curto do que aconteceu: "Straid libertado".

## Acessibilidade

- O estado é a palavra do selo. A borda `link` só reforça.
- Contraste: Derrotado (`head` sobre `th`) 18.88:1; Vivo (`text` sobre `th`) 8.93:1; nome do chefe (`link` sobre célula) 5.01:1; `sub` (`text` sobre célula) 6.79:1.
- As tabelas não têm `caption` nem `scope` nos `th`.

## Tokens usados

Cor: `head`, `text`, `link`, `line`, `th`, `td`, `edge`. Espaço: `tab-panel-gap`, `section-gap`, `title-small-gap`, `cell-pad-y`, `cell-pad-x`, `seal-pad-y`, `seal-pad-x`, `node-pad-table`, `node-pad-right-table`, `node-icon-gap-table`. Borda: `border-hair`, `border-table`. Layout: `icon-node-table`, `table-min-width`. Tipo: `titulo-secao`, `subtitulo-secao`, `cabecalho-tabela`, `corpo`, `nome-no`, `legenda-no`, `inicial-no-tabela`, `selo`, `vazio`.

## Problemas conhecidos

- A spec `2026-10-06-buildsmith-progresso-dano-design.md` (L71) pede Vivo e Pendente "em texto apagado". O código usa o selo neutro em `text`, não `.estado.apagado`.
- As tabelas do Progresso não recebem `td.selos` (L404, L407), ao contrário de Onde pegar, Feitiços e Fila. Não muda o visual hoje: `.estado` já tem `white-space: nowrap`.
