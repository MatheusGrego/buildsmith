# Cabecalho

O `header.top` abre o painel com o jogo e a data do plano, o nome do personagem em `h1` e a legenda de cores; com o servidor local, mostra também as ações da Forja e a caixa de progresso.

## Quando usar

- Use um só, como primeiro filho do `.panel`, antes do Agora e das Abas.
- Deixe no `h1` só o nome do personagem.

## Quando não usar

- Não ponha nível, almas ou objetivo no cabeçalho. Esses dados ficam na Ficha.
- Não repita o cabeçalho dentro das abas.
- Não ponha botão no cabeçalho fora do grupo `.acoes`.

## O que entra

| Parte | Campo | Exemplo real (`example/plano.json`) |
|---|---|---|
| `.meta` | `jogo` e `gerado_em` | `"jogo": "Dark Souls II: Scholar of the First Sin"` (L4) e `"gerado_em": "2026-10-06T17:26"` (L3) viram "Dark Souls II: Scholar of the First Sin · atualizado 06/10/2026, 17:26" |
| `h1` | `personagem.name` | "Melatonina Vorcaro" (L7) |
| `.legend` | texto fixo | ver Legenda |
| `.acoes` | servidor local e banco, não o plano | ver Acao |
| `.forja` | execução da skill, não o plano | ver Forja |

## Anatomia

HTML de `top(p)` (`skills/build-page/template/index.html` L288–L297):

```html
<header class="top">
  <p class="meta">Dark Souls II: Scholar of the First Sin · atualizado 06/10/2026, 17:26</p>
  <h1>Melatonina Vorcaro</h1>
  <div class="legend"><span class="l-pos">ganho</span><span class="l-neg">perda / falta</span><span class="l-link">link da wiki</span></div>
  <div class="acoes" id="forja-acoes" hidden>
    <button class="acao" type="button" data-rodar="plano"><img src="icons/fogueira.png" alt="">Atualizar plano</button>
    <button class="acao" type="button" data-rodar="fila"><img src="icons/fogueira.png" alt="">Responder fila<span class="count" id="forja-fila" hidden></span></button>
  </div>
  <div class="forja" id="forja" hidden></div>
</header>
```

- `.top` (L45): grid com `gap` `header-gap`.
- `.meta` (L46): 13px (`pequeno`), cor `text`. A data sai de `when()` (L260): `toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" })`.
- `h1` (L33–L34): estilo `titulo-pagina`, Marcellus `clamp(28px, 5vw, 40px)`, `line-height: 1.15`, cor `head`, `margin: 0`, `text-wrap: balance`.
- `.legend`: ver Legenda. `.acoes` e `.acao`: ver Acao. `.forja`: ver Forja.
- O preview mostra as ações sem `icons/fogueira.png`: o ícone da wiki não está neste sistema.

## Estados e variantes

| Variante | Quando | O que muda |
|---|---|---|
| Só leitura | Artifact, ou arquivo aberto sem o servidor local | `.acoes` fica `hidden`: meta, `h1` e legenda |
| Com ações | servidor local com runner (`/api/ping` responde `rodar`) | `.acoes` aparece; Responder fila desativa sem pendência (L585) |
| Forja visível | depois de um clique em Acao, ou ao abrir a página com a skill rodando | `.forja` sai de `hidden`, dentro do cabeçalho |
| Data ilegível | `gerado_em` que `new Date()` não lê | a `.meta` mostra o texto cru |

## Regras de conteúdo

- `h1`: o nome do personagem, de 1 a 32 caracteres, sem quebra de linha (`skills/build-page/scripts/validate_plano.py` L20, L118–L119). Caixa normal; a Marcellus SC desenha o versalete.
- `.meta`: `<jogo> · atualizado <data>`, com data e hora curtas em pt-BR. Separe com "·".
- Não use `text-transform` nem caixa alta.

## Acessibilidade

- `<header>` dentro do `<main>`. O `h1` é o único da página.
- Contraste sobre `panel`: `h1` em `head` 17.76:1; `.meta` em `text` 8.40:1.
- A ordem do DOM é a ordem de leitura: meta, nome, legenda, ações, Forja.

## Tokens usados

- Cor: `head`, `text`, `pos`, `neg`, `link`.
- Espaço: `header-gap`, `legend-gap-y`, `legend-gap-x`.
- Tipo: `titulo-pagina`, `pequeno`.

## Problemas conhecidos

- As imagens `icons/fogueira.png` das ações não têm fallback (L293–L294). Sem o arquivo aparece o ícone de imagem quebrada nos dois botões (`topo-desktop.png`, `topo-celular.png`; ver Problemas conhecidos, item 7).
