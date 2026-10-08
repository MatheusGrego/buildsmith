# OndePegar

Bloco da aba Onde pegar que lista, para cada item do plano, as fontes com requisito, acesso, rendimento e destaque, com a fonte mais cedo e a mais rentável na frente.

## Quando usar

- Use um `.block` por entrada de `itens`, dentro de `.blocks`, na seção "Onde pegar" da aba `onde`.
- Dê entrada a todo nó `item` citado em passo, dano, ajuste de build, `agora.faltam` ou feitiço sugerido que o jogador ainda não tem. O validador bloqueia o plano sem ela (`validate_plano.py` L244–L266).
- Dê entrada própria ao item que é ingrediente de outro (Smooth & Silky Stone para a Magic Stone, `skills/build/SKILL.md` L63).

## Quando não usar

- Não use para uma ação do plano. Ação é Passo.
- Não crie entrada para item que o jogador já tem. Marque `"tem": true` no nó citado (`skills/build/SKILL.md` L62).
- Não escreva a rota em frase. A rota é o fluxo da coluna Como.

## O que entra

`itens[]`: `{"id", "item": Nó, "fonte": URL da wiki, "fontes": [Fonte], "dados": [Linha]}`. Fonte: `{"tipo", "fluxo": [Nó], "requisito", "acesso", "rendimento", "destaques"}`. Exemplo real, Large Titanite Shard (`example/plano.json` L539–L637, `icone` e `link` omitidos):

```json
{"id": "large-titanite-shard", "item": {"tipo": "item", "nome": "Large Titanite Shard"},
 "fonte": "https://darksouls2.wiki.fextralife.com/Large+Titanite+Shard",
 "fontes": [
  {"tipo": "bau", "fluxo": [{"tipo": "local", "nome": "The Tower Apart", "sub": "fogueira"}, {"tipo": "bau", "nome": "Corpo à esquerda", "sub": "colado na parede"}],
   "acesso": "agora", "requisito": "Lost Bastille", "rendimento": "1 (uma vez)", "destaques": ["mais_cedo"]},
  {"tipo": "compra", "fluxo": [{"tipo": "npc", "nome": "Steady Hand McDuff", "sub": "estoque ilimitado"}, {"tipo": "item", "nome": "Large Titanite Shard", "sub": "2.500 almas"}],
   "acesso": "agora", "requisito": {"texto": "Dull Ember entregue", "item": "dull-ember"}, "rendimento": "ilimitado · 2.500 almas cada", "destaques": ["mais_rentavel"]},
  {"tipo": "drop", "fluxo": [{"tipo": "inimigo", "nome": "Great Basilisk", "sub": "Huntsman's Copse"}],
   "acesso": "em_breve", "requisito": "1ª caverna após a fogueira", "rendimento": "sempre 3"},
  {"tipo": "compra", "fluxo": [{"tipo": "npc", "nome": "Stone Trader Chloanne", "sub": "Majula"}],
   "acesso": "tarde", "requisito": "depois do Old Iron King", "rendimento": "10 · ilimitado após Looking Glass Knight"}],
 "dados": [{"dado": "Uchigatana", "agora": "+5", "depois": "+6", "efeito": "3 por nível de +4 a +6", "sinal": ""}]}
```

O exemplo tem 15 itens. A aba mostra o número no contador (`p.itens.length`, `skills/build-page/template/index.html` L489).

## Anatomia

`items()` (L355–L380), com `requisito()` (L248–L253) e `grid()` (L391–L395):

```html
<section><h2>Onde pegar<small>mais cedo e mais rentável a partir de onde você está</small></h2><div class="blocks">
  <div class="block" id="item-large-titanite-shard">
    <div class="block-head"><a class="node solo" href="…" target="_blank" rel="noopener noreferrer"><span class="ini" aria-hidden="true">L</span><span class="nm">Large Titanite Shard</span></a><a class="muted" href="…" target="_blank" rel="noopener noreferrer">fonte</a></div>
    <div class="tw"><table><thead><tr><th>#</th><th>Como</th><th>Requisito</th><th>Acesso</th><th>Rendimento</th><th>Destaque</th></tr></thead><tbody>
      <tr><td>1</td><td><div class="flow">…</div></td><td>Lost Bastille<button class="pesq" type="button" data-q="Lost Bastille" data-origem="Large Titanite Shard">Pesquisar</button></td><td class="selos"><span class="estado feito">Agora</span></td><td>1 (uma vez)</td><td class="selos"><span class="estado destaque">Mais cedo</span></td></tr>
      <tr><td>2</td><td><div class="flow">…</div></td><td><a class="req-link" href="#item-dull-ember" data-goto-item="dull-ember">Dull Ember entregue</a></td><td class="selos"><span class="estado feito">Agora</span></td><td>ilimitado · 2.500 almas cada</td><td class="selos"><span class="estado destaque">Mais rentável</span></td></tr>
    </tbody></table></div>
    <details class="mais"><summary>Ver todas as fontes (4)</summary><div class="tw"><table>… fontes 3 e 4 …</table></div></details>
    <div class="tw"><table><thead><tr><th>Dado</th><th>Agora</th><th>Com o item</th><th>Efeito</th></tr></thead><tbody>…</tbody></table></div>
  </div>
</div></section>
```

| Parte | Regra |
|---|---|
| `.blocks` | Grade com `gap: 0` (L96). |
| `.block` | Grade com `gap` `block-gap`, `padding-block` `block-pad-y`, borda de cima `border-hair` em `line`, `min-width: 0` (L97). Guarda a âncora `id="item-<id>"`. |
| `.block:first-child` | Sem borda, `padding-top` `list-first-pad-top` (L98). |
| `.block-head` | `display: flex`, `flex-wrap: wrap`, `align-items: center`, `gap: 8px 14px` (L99; sem token). Nó do item mais o link "fonte" em `.muted` (`pequeno`). |
| Nó do item | Nó cheio (ver No). O item não tem `sub`, então sai `.node.solo`. |
| Tabela de fontes | Tabela wiki de 6 colunas (ver TabelaWiki). Os nós da coluna Como ficam compactos dentro de `td` (ver No e Fluxo). |
| Requisito | Texto mais `.pesq` (ver Pesquisar); ou `a.req-link` em `link`, com o sublinhado do navegador (L164); ou "—". |
| Acesso | Selo `.estado` (ver Selo): `feito` para Agora, sem modificador para Em breve, `apagado` para Tarde (L362). |
| Destaque | Um `.estado.destaque` por destaque; sem destaque, `<td></td>` (L364). |
| `td.selos` | `white-space: nowrap`; dois selos na mesma célula ganham `margin-left` `seal-gap` (L130–L131). Entra pela troca de `<td><span class="estado` por `<td class="selos">…` (L370). |
| `details.mais` | `summary` em `mais-fontes` (Marcellus 13px) e `link`, `margin-top: 6px`; aberto ganha `margin-bottom: 6px` (L162–L163; sem token). |
| Tabela de dados | `rows()` com Dado, Agora, Com o item, Efeito (L376). Sinal na coluna Efeito como na TabelaWiki. |

Os ícones da wiki não estão neste sistema. O preview mostra a inicial em `.ini`, que é o fallback real da página (L262).

## Estados e variantes

| Caso | Resultado |
|---|---|
| Algumas fontes com destaque, outras sem | Tabela principal só com as de destaque; as outras dentro de `details.mais` "Ver todas as fontes (N)" (L367–L372). A coluna # guarda o número original (`i + 1`). |
| Todas com destaque, ou nenhuma | Tabela única, sem `details`. |
| Uma fonte com os dois destaques | "Mais cedo" e "Mais rentável" lado a lado em `td.selos` (Smooth & Silky Stone, `example/plano.json` L831–L837). |
| Requisito texto | Texto e botão Pesquisar (`data-q` = texto, `data-origem` = nome do item). |
| Requisito `{"texto", "item"}` | Link `.req-link`. O clique abre a aba `onde` e rola até `#item-<id>` (L802–L803, `goTo()` L523–L527). |
| Requisito ausente | "—" (L249). |
| Rendimento vazio | "—" (L363). |
| `fonte` ausente | Sem o link "fonte" no `.block-head`. |
| `dados` vazio | Sem a segunda tabela (Heavy Soul Arrow, Soul Spear e mais dois no exemplo). |
| Acesso fora do mapa | O valor sai cru: `ACESSO[f.acesso] || f.acesso` (L362). |
| Nenhum item | `<p class="empty">Nenhum item pendente.</p>` no lugar de `.blocks` (L379). Ver EstadoVazio. |

## Regras de conteúdo

- Marque exatamente uma fonte `mais_cedo` (a primeira que o jogador consegue pegar) e no máximo uma `mais_rentavel` (a melhor repetível) (`validate_plano.py` L236–L240; `skills/build/SKILL.md` L63).
- Ordene as fontes por acesso: `agora`, depois `em_breve`, depois `tarde` (`validate_plano.py` L241–L243).
- Use `tipo` de fonte entre `compra`, `troca`, `drop`, `bau`, `farm`, `recompensa` (L11). A página não mostra o tipo.
- Use `acesso` entre `agora`, `em_breve`, `tarde` (L12). Rótulos fixos: Agora, Em breve, Tarde, Mais cedo, Mais rentável (template L241–L242).
- Escreva o requisito em uma linha, com até 80 caracteres (`validate_plano.py` L21–L22, L172). O `requisito.item` precisa existir em `itens[].id` (L178).
- Escreva o rendimento como quantidade e repetição: "1 (uma vez)", "ilimitado · 2.500 almas cada", "1 por Bonfire Ascetic (3 no NG+)", "~1 a cada 4".
- Mantenha o `sub` de cada nó com até 30 caracteres (`validate_plano.py` L36).
- Dado sem fonte verificada é "—" (`skills/build-page/SKILL.md` L16).

## Acessibilidade

- A seta do fluxo e a inicial do nó levam `aria-hidden="true"`. O nome do nó está sempre escrito.
- O acesso e o destaque são palavras dentro do selo. A cor só reforça.
- `details` e `summary` são nativos: Enter e Espaço abrem e fecham. O `summary` não tem `:focus-visible` próprio e usa o anel do navegador.
- Contraste: `head` sobre célula 14.35:1; nó com link (`link`) sobre célula 5.01:1; selo Agora (`head` sobre `th`) 18.88:1; Em breve (`text` sobre `th`) 8.93:1; destaque (`pos` sobre `th`) 10.26:1; "Ver todas" (`link` sobre `panel`) 6.19:1; "fonte" (`text` sobre `panel`) 8.40:1.
- Tarde usa `dim` sobre `th`: 4.29:1, abaixo de 4.5:1.

## Tokens usados

Cor: `head`, `text`, `link`, `pos`, `dim`, `th`, `td`, `line`, `edge`, `panel`. Espaço: `block-gap`, `block-pad-y`, `list-first-pad-top`, `seal-pad-y`, `seal-pad-x`, `seal-gap`, `cell-pad-y`, `cell-pad-x`, `section-gap`, `title-small-gap`. Borda: `border-hair`, `border-table`. Layout: `table-min-width`, `icon-node-table`. Tipo: `titulo-secao`, `subtitulo-secao`, `cabecalho-tabela`, `corpo`, `nome-no`, `legenda-no`, `inicial-no`, `inicial-no-tabela`, `selo`, `mais-fontes`, `pequeno`, `seta-tabela`. Mais os tokens de Pesquisar e TabelaWiki.

## Problemas conhecidos

- A 400px os nomes da coluna Como quebram uma letra por linha (`recorte-onde-celular.png`; ver Problemas conhecidos, item 1). `overflow-wrap: anywhere` no nome (L70) deixa a coluna encolher até um caractere, porque `.pesq`, `.estado` e `td.selos` não quebram (L123, L130, L153).
- "Ver todas as fontes (N)" conta todas as fontes, mas o `details` mostra só as que ficaram fora da tabela principal (L372). No exemplo, "(4)" abre duas linhas.
- O link "fonte" sai em `text`, não em `link`: `.muted` (L42) vence a cor de `a` (L37). Fica cinza e sublinhado (`aba-onde-desktop.png`), fora da regra de que link da wiki é dourado.
- O selo Tarde em `dim` falha 4.5:1 (4.29:1 sobre `th`).
- As tabelas não têm `caption` nem `scope` nos `th` (L392–L394).
