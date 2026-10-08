# Passo

Bloco da aba Passos com fogueira, número, título, fluxo e a tabela Dado | Agora | Depois | Efeito, agrupado por tipo de passo em ordem fixa.

## Quando usar

- Use para cada ação do plano: equipar, explorar, chefe, troca de alma, compra, upgrade, farm e nível.
- Use dentro da seção "Próximos passos", num `.grupo` por tipo.

## Quando não usar

- Não use para um item a pegar. Item vai no bloco de Onde pegar, com a tabela de fontes.
- Não repita o passo inteiro no painel Agora. O Agora mostra fogueira, título como link para o passo e fluxo, sem a tabela.
- Não escreva frase explicativa. O passo é fluxo mais dados.

## O que entra

`passos[]`: `{"id", "tipo", "titulo", "fluxo": [Nó], "dados": [Linha]}`. Exemplo real (`example/plano.json` L87 em diante, `icone` e `link` omitidos aqui):

```json
{"titulo": "Trocar anel", "tipo": "equipar",
 "fluxo": [{"tipo": "item", "nome": "Old Leo Ring", "sub": "sai", "tem": true}, {"tipo": "item", "nome": "Ring of Binding", "sub": "entra", "tem": true}],
 "dados": [{"dado": "PV máx. em Hollow", "agora": "50%", "depois": "75%", "efeito": "+25 p.p.", "sinal": "+"},
           {"dado": "Contra-ataque de estocada", "agora": "+12,5%", "depois": "0%", "efeito": "−12,5%", "sinal": "-"}],
 "id": "equipar-trocar-anel"}
```

Do banco (Artifact ou servidor local), não do plano: `feitos/<id>` com `marcado`, `em` e `confirmado`. Ele acende a fogueira e escreve o `.confirmado` (`applyState()`, L535–L542).

## Anatomia

`steps()` (`skills/build-page/template/index.html` L313–L324):

```html
<section><h2>Próximos passos</h2><div class="grupo">
  <h3>Equipar<small>1</small></h3>
  <ol class="steps"><li class="step">
    <div class="step-head" id="passo-equipar-trocar-anel"><button class="fogueira" type="button" data-passo="equipar-trocar-anel" aria-pressed="false" aria-label="Marcar como feito" title="Marcar como feito" hidden><img src="icons/fogueira.png" alt=""></button><span class="step-no">1</span><span class="step-title">Trocar anel</span><span class="confirmado" data-confirma="equipar-trocar-anel"></span></div>
    <div class="flow">…</div>
    <div class="tw"><table><thead><tr><th>Dado</th><th>Agora</th><th>Depois</th><th>Efeito</th></tr></thead><tbody>…</tbody></table></div>
  </li></ol>
</div></section>
```

| Parte | Regra |
|---|---|
| `.grupo` | Grade com `gap` `group-gap` (L127). |
| `.grupo h3` | `titulo-grupo` em `head`, `display: flex`, `align-items: baseline`, `gap` `group-title-gap` (L128). |
| `.grupo h3 small` | Contagem do grupo em `subtitulo-grupo`, cor `text` (L129). |
| `.steps` | `ol` sem marcador, sem margem, `gap: 0` (L77). |
| `.step` | Grade com `gap` `step-gap`, `padding-block` `step-pad-y`, borda de cima `border-hair` em `line` (L78). |
| `.step:first-child` | Sem borda, `padding-top` `list-first-pad-top` (L79). |
| `.step-head` | `display: flex`, `flex-wrap: wrap`, `align-items: center`, `gap: 8px 12px` (L80; sem token). Guarda a âncora `id="passo-<id>"`. |
| `.fogueira` | Botão de `fogueira-size` com fundo `th` e borda `line`; imagem em `icon-fogueira` (L134–L142). |
| `.step-no` | Número em `numero-passo`, cor `head`, `min-width` `step-no-min-width` (L81). |
| `.step-title` | Título em `titulo-passo`, cor `head` (L82). |
| `.confirmado` | 12px em `pos` (L143). |
| `.flow`, `.tw` | ver Fluxo e TabelaWiki. |

Grupos, sempre nesta ordem (L239–L240): Equipar, Explorar, Chefes, Trocas de alma, Compras, Upgrades, Farms, Nível. Grupo sem passo não aparece. A numeração recomeça em cada grupo.

O ícone `icons/fogueira.png` não está neste sistema. O preview mostra o botão sem a imagem.

## Estados e variantes

| Estado | Como fica |
|---|---|
| Sem banco | Fogueira com `hidden`; o passo é só leitura. |
| Com banco, pendente | Fogueira visível, `aria-pressed="false"`, borda `line`, imagem `grayscale(1) brightness(0.55)`. |
| Hover na fogueira | Imagem `grayscale(0.4) brightness(0.85)`. |
| Marcado | `aria-pressed="true"`, borda `pos`, imagem com `drop-shadow(0 0 5px)` em `fogueira-glow`. |
| Gravando | Fogueira `disabled`, `cursor: progress` (L771–L778). |
| Depois de marcar | `.confirmado` mostra "confirma no próximo /build" (`confirmado` nulo), "confirmado pelo save" (true) ou "o save ainda não mostra" (false) (L541). |
| Sem passos | `<section><h2>Próximos passos</h2><p class="empty">Nenhum passo pendente.</p></section>` (L315). |

## Regras de conteúdo

- Escreva o título com até 40 caracteres (`validate_plano.py` L85–L86), no padrão do exemplo: "Trocar anel", "Uchigatana +5 → +6", "Large Titanite Shard ×1", "VGR 9 → 20".
- Escolha `tipo` entre os 8 grupos (`validate_plano.py` L87–L88).
- Dê a cada passo um `id` único (`validate_plano.py` L125–L133).
- Ponha no máximo 3 passos por tipo, em ordem cronológica: primeiro o que dá para fazer na área atual (`skills/build/SKILL.md` L54).
- Monte o passo só com `fluxo` e `dados`. Sem frase (`skills/build-page/SKILL.md` L24).
- Siga as regras de Linha da TabelaWiki na tabela do passo.

## Acessibilidade

- A fogueira é um botão de alternância: `aria-pressed`, `aria-label` e `title` "Marcar como feito". O foco é o anel `focus-width` em `link` com `focus-offset`. Enter e Espaço vêm do `button`.
- Feito é fogo aceso e borda `pos`, nunca check nem texto riscado. A borda `pos` dá 10.26:1 sobre `th` e 9.65:1 sobre `panel`.
- `.confirmado` em `pos` dá 9.65:1 sobre `panel`. Ele não tem `aria-live`; o leitor de tela ouve a mudança pelo `aria-pressed` do botão.
- `.step-no` repete o número que o `ol` já dá; a lista usa `list-style: none`.

## Tokens usados

Cor: `head`, `text`, `line`, `th`, `pos`, `link`, `fogueira-glow`. Espaço: `group-gap`, `group-title-gap`, `step-gap`, `step-pad-y`, `list-first-pad-top`, `focus-offset`. Borda: `border-hair`, `focus-width`. Ícone: `icon-fogueira`. Layout: `fogueira-size`, `step-no-min-width`. Tipo: `titulo-grupo`, `subtitulo-grupo`, `numero-passo`, `titulo-passo`, `legenda-no`. Mais os tokens de Fluxo e TabelaWiki.

## Problemas conhecidos

- A imagem da fogueira não tem fallback: sem o arquivo, cada fogueira mostra o ícone de imagem quebrada (`aba-passos-desktop.png`, `topo-desktop.png`). O `img` entra com `alt=""` e sem `onerror` (L246); `fallbackIcons()` só trata `img.ic` (L266–L271).
- `.badge` está no CSS (L83) e nada a gera. A spec `2026-10-06-buildsmith-pagina-v2-design.md` previa o tipo do passo como selo no título; o código agrupa por tipo com `h3`.
- A seta do fluxo fica pendurada no fim da linha quando o fluxo quebra (ver Fluxo).
