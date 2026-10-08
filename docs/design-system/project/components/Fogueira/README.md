# Fogueira

Checkbox no estilo do DS2: um botão de alternância de 34px com o ícone da fogueira, apagado (cinza) para pendente e aceso (borda `pos` e brilho de brasa) para feito ou selecionado.

## Quando usar

- Use para marcar um passo como feito: `data-passo`, rótulo "Marcar como feito". Ela aparece no cabeçalho do passo (aba Passos) e em cada ação do Agora.
- Use para escolher um feitiço para sintonizar: `data-feitico`, rótulo "Selecionar para sintonizar", na primeira coluna da tabela de Feitiços.

## Quando não usar

- Não troque por checkbox, ícone de check ou texto riscado. Feito é fogo aceso.
- Não use para estado que o jogador não muda. Isso é o Selo.
- Não mostre a fogueira sem banco para gravar. Ela nasce com `hidden` e só aparece quando há banco (`skills/build-page/template/index.html` L707, L856).

## O que entra

| Uso | Atributo | Valor (exemplo real) | Estado lido de |
|---|---|---|---|
| Passo | `data-passo` | `passos[].id`: `equipar-trocar-anel` (`example/plano.json` L124) | `feitos/<id>.marcado` no banco |
| Feitiço | `data-feitico` | `feiticos.lista[].id`: `soul-arrow` | `config/feiticos.selecionados`; sem esse documento, os feitiços com `"estado": "equipado"` (L529–L532) |

Só no passo, o `.confirmado` ao lado diz o que o save mostrou (L539–L542):

| Banco | Texto |
|---|---|
| marcado, `confirmado: true` | confirmado pelo save |
| marcado, `confirmado: false` | o save ainda não mostra |
| marcado, `confirmado` nulo | confirma no próximo /build |
| não marcado | vazio |

## Anatomia

HTML do helper `fogueira()` (L246):

```html
<button class="fogueira" type="button" data-passo="equipar-trocar-anel" aria-pressed="false" aria-label="Marcar como feito" title="Marcar como feito" hidden><img src="icons/fogueira.png" alt=""></button>
```

No passo (L319) ela vem antes do número e do título, e o `.confirmado` fecha a linha:

```html
<div class="step-head" id="passo-equipar-trocar-anel"><button class="fogueira" …>…</button><span class="step-no">1</span><span class="step-title">Trocar anel</span><span class="confirmado" data-confirma="equipar-trocar-anel"></span></div>
```

- `.fogueira` (L134): `flex: none`, `fogueira-size` por `fogueira-size`, `padding: 0`, borda `border-hair` em `line`, fundo `th`, `display: grid`, `place-items: center`, `cursor: pointer`.
- `.fogueira img` (L135): `icon-fogueira`, `object-fit: contain`, `filter: grayscale(1) brightness(0.55)`, `transition: filter 0.2s ease-out`.
- `.confirmado` (L143): 12px, cor `pos`.
- O ícone `icons/fogueira.png` vem de `games/ds2/icons.json` e é baixado a cada plano. Ele não está neste sistema: o preview mostra o botão sem a imagem.

## Estados e variantes

| Estado | Gatilho | Visual |
|---|---|---|
| Oculta | `hidden` | `display: none` (L140) |
| Apagada | `aria-pressed="false"` | borda `line`; ícone cinza e escuro |
| Hover apagada | `:hover` | ícone `grayscale(0.4) brightness(0.85)` (L136) |
| Acesa | `aria-pressed="true"` | borda `pos`; ícone em cor com `drop-shadow(0 0 5px)` em `fogueira-glow` (L137–L138) |
| Hover acesa | `:hover` com `aria-pressed="true"` | continua acesa: a regra de L138 vem depois da de L136, com a mesma especificidade |
| Gravando | `:disabled` | só `cursor: progress` (L141) |
| Foco | `:focus-visible` | anel `focus-width` em `link`, `outline-offset` `focus-offset` (L139) |
| Movimento reduzido | `prefers-reduced-motion: reduce` | sem a transição do filtro (L142) |

O clique (L771–L789) desativa o botão, grava no banco e reativa no fim. No passo grava `{ marcado, em, confirmado: null }`; desmarcar também zera a confirmação. No feitiço alterna o id em `config/feiticos`. A fogueira do mesmo passo no Agora e na aba Passos lê o mesmo `feitos/<id>` e muda junto.

## Regras de conteúdo

- Escreva no rótulo a ação, não o estado: "Marcar como feito", "Selecionar para sintonizar". Repita o mesmo texto em `aria-label` e `title`.
- Ponha o estado em `aria-pressed`. Não troque o rótulo quando a fogueira acende.
- Use só os três textos de `.confirmado` da tabela acima.

## Acessibilidade

- `<button type="button" aria-pressed>`: Enter e Espaço alternam. A imagem é decorativa (`alt=""`); o nome vem do `aria-label`.
- Foco: 2px em `link`, 6.59:1 sobre `th` e 6.19:1 sobre `panel`.
- Borda acesa em `pos`: 10.26:1 sobre `th`, 9.65:1 sobre `panel`, 7.80:1 sobre a célula (#2a2a2a).
- Borda apagada em `line`: 1.49:1 sobre `th`, 1.41:1 sobre `panel`, 1.14:1 sobre a célula. Fica abaixo de 3:1; quem identifica o botão é o ícone.
- `.confirmado` em `pos` sobre `panel`: 9.65:1.

## Tokens usados

- Cor: `th`, `line`, `pos`, `fogueira-glow`, `link`.
- Tamanho: `fogueira-size`, `icon-fogueira`, `border-hair`, `focus-width`, `focus-offset`.

## Problemas conhecidos

- A imagem não tem `onerror` (L246) e o `fallbackIcons()` só troca `img.ic` (L266–L271). Sem o arquivo aparece o ícone de imagem quebrada; na aba Feitiços, acesa e apagada só se distinguem pela borda `pos` (`aba-feiticos-desktop.png`; ver Problemas conhecidos, item 7).
- Gravando não tem sinal visual além do cursor.
- Sem a imagem, a borda apagada (1.49:1 sobre `th`) é o único contorno do botão.
- O Agora não tem `.confirmado`: o texto de confirmação só aparece na aba Passos.
