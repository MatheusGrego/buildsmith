# Fontes

Aba Fontes com a lista de onde veio cada fato do plano, página da wiki com link ou tabela do jogo sem link, e a data da consulta.

## Quando usar

- Use uma vez por página, no painel da aba `fontes`, a última aba (`skills/build-page/template/index.html` L492).
- Liste toda fonte consultada para o plano: a página da wiki (URL e data) ou a tabela do jogo lida pelos scripts.

## Quando não usar

- Não use para citar a fonte de um item. O item leva o próprio link "fonte" no Onde pegar.
- Não escreva comentário sobre a fonte. A linha é título e data.

## O que entra

`fontes[]`: `{"titulo", "url", "data"}` (`example/plano.json` L1457–L1538). Exemplo real:

```json
[{"titulo": "Level (custos de nível)", "url": "https://darksouls2.wiki.fextralife.com/Level", "data": "2026-10-06"},
 {"titulo": "Tabelas do jogo (ShopLineupParam, ReinforceCostParam, ItemParam)", "url": "", "data": "2026-10-07"}]
```

O exemplo tem 16 fontes: 14 páginas da wiki e 2 tabelas do jogo sem URL. O número vai no contador da aba.

## Anatomia

`sources()` (L473–L475):

```html
<section><h2>Fontes</h2><ul class="sources">
  <li><a class="" href="https://darksouls2.wiki.fextralife.com/Level" target="_blank" rel="noopener noreferrer">Level (custos de nível)</a> <span class="muted">· 2026-10-06</span></li>
  <li>Tabelas do jogo (ShopLineupParam, ReinforceCostParam, ItemParam) <span class="muted">· 2026-10-07</span></li>
</ul></section>
```

| Parte | Regra |
|---|---|
| `.sources` | `ul` sem margem, `padding-left` `sources-indent`, grade com `gap: 2px` (L101; sem token para o gap). Marcadores do navegador. |
| Título com URL | Link de `ext()` (L258): `link`, sublinhado do navegador, nova aba com `noopener noreferrer`. |
| Título sem URL | Texto em `text`. URL que não é `http(s)` também vira texto (`safeUrl()`, L257). |
| Data | ` · <data>` em `.muted` (`pequeno`, `text`), crua como está no JSON. |

## Estados e variantes

| Caso | Resultado |
|---|---|
| Com `url` | título é link |
| `url` vazia | título é texto |
| Sem `data` | sem o trecho `· <data>` |
| Lista vazia | `<p class="empty">Sem fontes.</p>` (L474) |

## Regras de conteúdo

- Dê a cada fato do plano uma fonte verificada: tabela do jogo e save, pelos scripts, ou wiki, com URL e data (`skills/build-page/SKILL.md` L8–L18).
- Escreva o título como o nome da página da wiki, com o recorte entre parênteses quando ajuda: "Vigor (PV por nível)", "Uchigatana (infusão mágica)".
- Para tabela do jogo, nomeie as tabelas lidas e deixe `url` vazia: "Tabelas do jogo (SpellParam, PlayerDamageParam, PhysicalStatsPerLevelStatValuesParam)".
- Use URL `http` ou `https` (`validate_plano.py` L19, L136–L150).
- Escreva a data no formato do exemplo, `AAAA-MM-DD`. A página não reformata.

## Acessibilidade

- Lista real (`ul` e `li`). O link abre em nova aba sem aviso no texto.
- Contraste sobre `panel`: link 6.19:1; título sem link e data (`text`) 8.40:1.

## Tokens usados

Cor: `link`, `text`, `head`, `line`, `panel`. Espaço: `sources-indent`, `section-gap`. Borda: `border-hair`. Tipo: `titulo-secao`, `corpo`, `pequeno`, `vazio`.

## Problemas conhecidos

- A data sai em ISO e quebra no hífen em tela estreita: "· 2026-" numa linha e "10-07" na seguinte (`aba-fontes-celular.png`; L474). O cabeçalho formata `gerado_em` em pt-BR (L260); aqui não há formatação.
- O link sai com `class=""` vazio, porque `ext()` recebe a classe padrão `""` (L258, L474).
