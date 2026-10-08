# Faixa

Aviso de fim no estilo "BONFIRE LIT": texto dourado e espaçado numa faixa escura que atravessa o meio da tela, acende e some sozinho em 2.8s.

## Quando usar

- Use só quando a Forja termina com `ok` e a execução é desta página (`terminou()`, `skills/build-page/template/index.html` L700–L701).
- Mostre uma por vez. Chamar de novo reinicia a animação.

## Quando não usar

- Não use para erro nem cancelamento. Esses estados ficam na caixa da Forja, em `neg`, com a mensagem do servidor.
- Não use para confirmar clique pequeno (Fogueira, Pesquisar).
- Não use para texto que precisa ser lido com calma: a faixa some em 2900ms.

## O que entra

- O título de fim da Forja, `TITULO[modo][1]` (L572): "Plano forjado" (`modo: "plano"`) ou "Fila respondida" (`modo: "fila"`).
- Nada do `plano.json`.

## Anatomia

HTML estático, fora do `#app` (L234):

```html
<div class="faixa" id="faixa" hidden><span></span></div>
```

`faixa(texto)` (L713–L724) põe o texto no `span`, reinicia a animação (`animation: none`, reflow, `animation: ""`), tira o `hidden` e põe de volta em 2900ms.

- `.faixa` (L223): `position: fixed`, `inset: 0`, `z-index` `z-faixa`, grid com `place-items: center`, `pointer-events: none`.
- `.faixa span` (L225): `width: 100%`, padding `faixa-pad-y` `faixa-pad-x`, `text-align: center`. Fundo `linear-gradient(90deg, transparent, band 18%, band 82%, transparent)`. Cor `faixa-text`. Estilo `faixa-aviso`: Marcellus `clamp(24px, 6vw, 46px)`, `letter-spacing: 0.18em`. `text-shadow: 0 0 18px` em `faixa-glow`. `animation: acende 2.8s ease-out both`.
- `@keyframes acende` (L226): em 0%, `opacity: 0` e `letter-spacing: 0.3em`; em 20%, `opacity: 1` e `0.18em`; em 75%, `opacity: 1`; em 100%, `opacity: 0`.
- O preview chama a mesma `faixa()` em ciclo, alternando os dois títulos, sobre o cabeçalho da página.

## Estados e variantes

| Estado | Gatilho | Visual |
|---|---|---|
| Oculta | `[hidden]` | `display: none` (L224) |
| Visível | `faixa(texto)` | acende, fica e some em 2.8s; o JS esconde em 2900ms |
| Movimento reduzido | `prefers-reduced-motion: reduce` | sem animação (L228): fica parada e opaca até o `hidden` |

## Regras de conteúdo

- Escreva em caixa normal: "Plano forjado". A Marcellus SC desenha o versalete; não use `text-transform`.
- Use só os dois títulos de sucesso da Forja.

## Acessibilidade

- `pointer-events: none`: a faixa não bloqueia clique.
- A faixa não tem `role` nem `aria-live`. O título da Forja, no `.forja-head` com `aria-live="polite"`, anuncia o mesmo fim.
- Contraste de `faixa-text` onde a faixa é cheia: 13.87:1 sobre o painel, 13.95:1 sobre a margem da página e 7.98:1 sobre um título branco (pior caso).
- Respeita `prefers-reduced-motion`.

## Tokens usados

- Cor: `band`, `faixa-text`, `faixa-glow`.
- Espaço: `faixa-pad-y`, `faixa-pad-x`.
- Outros: `z-faixa`.
- Tipo: `faixa-aviso`.

## Problemas conhecidos

- A cor do texto, a opacidade da faixa e o espaçamento foram supostos e não conferidos com o jogo (ver Wiki e fidelidade, item 31).
- Nas pontas o degradê vai a transparente. Sobre um título branco, a conta dá menos de 3:1 até 12,2% da largura de cada lado; em tela estreita os glifos podem entrar nessa rampa. Não foi medido na tela.
- O `text-shadow` em `faixa-glow` clareia o fundo em volta das letras. Esse contraste não foi medido.
- A spec `docs/superpowers/specs/2026-10-07-buildsmith-forja-design.md` (L32) escreve "PLANO FORJADO"; o código passa "Plano forjado" (L572) e o versalete vem da fonte.
