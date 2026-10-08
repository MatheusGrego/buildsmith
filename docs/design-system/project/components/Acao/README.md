# Acao

Botão grande de menu do DS2, com faixa dourada à esquerda e fogueira que acende no hover, que manda o servidor local rodar a skill: Atualizar plano e Responder fila.

## Quando usar

- Use só no grupo `.acoes` do Cabecalho, um botão por modo da skill: `data-rodar="plano"` e `data-rodar="fila"`.
- Mostre o grupo só quando o servidor tem runner (`forja.rodar`, que vem de `GET /api/ping`).

## Quando não usar

- Não use para ação pequena em linha (Pesquisar, Cancelar, Tentar de novo, Fechar). Isso é o `.pesq`.
- Não use para enviar o formulário da Fila. Ele tem botão próprio (`.fila-form button`).
- Não use fora do cabeçalho, nem para navegar.

## O que entra

Nada do `plano.json`. O estado vem do servidor e do banco (`paintActions()`, `skills/build-page/template/index.html` L579–L588):

- `forja.rodar` decide se `.acoes` aparece (L582). No Artifact não há servidor local: o grupo nunca aparece.
- Skill rodando (`forja.status.estado === "rodando"`) desativa os dois botões (L583, L585).
- `pendentes()` (L576–L577) soma os pedidos da fila ainda não respondidos e os passos marcados sem confirmação do save. O número vai no `.count` de Responder fila; com 0, o botão desativa e o contador some (L585–L587).

## Anatomia

```html
<div class="acoes" id="forja-acoes">
  <button class="acao" type="button" data-rodar="plano"><img src="icons/fogueira.png" alt="">Atualizar plano</button>
  <button class="acao" type="button" data-rodar="fila"><img src="icons/fogueira.png" alt="">Responder fila<span class="count" id="forja-fila">2</span></button>
</div>
```

- `.acoes` (L170): flex com `flex-wrap: wrap` e `gap: 8px 10px`; `[hidden]` vira `display: none` (L171).
- `.acao` (L172): `inline-flex`, `align-items: center`, `gap` `acao-icon-gap`, `min-height` `acao-min-height`, padding `acao-pad-y` `acao-pad-right` `acao-pad-y` `acao-pad-left`. Borda `border-hair` em `line` e borda esquerda `border-acao` em `link`. Fundo `linear-gradient(90deg, acao-tint, th 75%)`. Texto `head` no estilo `aba` (Marcellus 15px, `letter-spacing: 0.03em`).
- `.acao img` (L173): `icon-small`, `object-fit: contain`, `filter: grayscale(1) brightness(0.7)`, `transition: filter 0.2s ease-out`.
- `.acao .count` (L179): estilo `contador` (12px `body`), `link` sobre `th`, borda `border-hair` em `line`, padding `0` `count-pad-x`.
- O ícone `icons/fogueira.png` não está neste sistema. O preview mostra os botões sem ele; na página real o ícone vem antes do rótulo, a `acao-icon-gap` dele.

## Estados e variantes

| Estado | Gatilho | Visual |
|---|---|---|
| Oculta | `.acoes[hidden]` | `display: none` |
| Normal | habilitada | como na Anatomia |
| Hover | `:hover:not(:disabled)` (L174–L175) | as quatro bordas em `link`; ícone em cor com `drop-shadow(0 0 5px)` em `ember-glow` |
| Foco | `:focus-visible` (L176) | anel `focus-width` em `link`, `outline-offset` `focus-offset` |
| Desativada | `:disabled` (L177–L178) | texto `dim`, borda esquerda `line`, fundo `th` liso, ícone `grayscale(1) brightness(0.4)`, `cursor: default` |
| Com contador | `.count` sem `hidden` | número de pendências, só em Responder fila; aparece também com o botão desativado enquanto a skill roda |
| Movimento reduzido | `prefers-reduced-motion: reduce` | ícone sem transição (L229) |

O clique chama `rodar(modo)` (L681–L694): `POST <base>/rodar` com `{ modo }`, mostra a Forja e acompanha a execução.

## Regras de conteúdo

- Escreva verbo e objeto, caixa normal: "Atualizar plano", "Responder fila".
- O contador é só o número, sem rótulo.

## Acessibilidade

- `<button type="button">` com texto visível. O ícone é decorativo (`alt=""`).
- O contador entra no nome acessível do botão.
- Contraste do texto `head`: 13.87:1 sobre o começo do degradê (#302c26) e 18.88:1 sobre `th`. Contador `link` sobre `th`: 6.59:1.
- A faixa esquerda em `link` dá 6.19:1 contra `panel`. A borda em `line` (1.41:1) é decorativa: a faixa e o texto marcam o botão.
- Desativada usa `dim` (4.29:1 sobre `th`). Controle desativado é isento de contraste.

## Tokens usados

- Cor: `line`, `link`, `acao-tint`, `th`, `head`, `dim`, `ember-glow`.
- Espaço: `acao-icon-gap`, `acao-pad-y`, `acao-pad-left`, `acao-pad-right`, `count-pad-x`, `focus-offset`.
- Tamanho: `acao-min-height`, `icon-small`, `border-hair`, `border-acao`, `focus-width`.
- Tipo: `aba`, `contador`.

## Problemas conhecidos

- O ícone não tem `onerror` (L293–L294). Sem o arquivo aparece o ícone de imagem quebrada (`topo-desktop.png`, `topo-celular.png`; ver Problemas conhecidos, item 7).
- Sem a imagem, o hover só muda a cor das bordas: a fogueira que acende é o ícone.
- O contador fica colado ao rótulo, sem espaço: o nome acessível sai "Responder fila2".
