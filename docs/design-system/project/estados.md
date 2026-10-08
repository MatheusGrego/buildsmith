# Estados

Matriz de estado por componente. Cada estado sai de uma classe, de um atributo ARIA ou de `hidden`/`disabled`; nenhum vem de estilo inline. As linhas `L` são de `skills/build-page/template/index.html` (CSS em L5–L231, JS em L236–L873).

Regras que valem para todos:

- Mude o estado trocando a classe ou o atributo. O visual sai do CSS.
- Ponha o estado em ARIA quando ele muda o significado: `aria-pressed`, `aria-selected`, `aria-current`.
- Mantenha o texto do estado visível. Cor e borda reforçam, não substituem.
- Use `link` para feito, `pos` para destaque e aceso, `neg` para erro e falta, `dim` para apagado.

## Selo `.estado`

Fundo `th`, borda `border-hair`, Marcellus 13px (`selo`), `white-space: nowrap` (L123–L126).

| Estado | Classe | Texto e borda | Onde aparece |
|---|---|---|---|
| Neutro | `.estado` | `text`, borda `line` | Em breve, Tem, Vivo, Pendente, Na fila |
| Feito | `.estado.feito` | `head`, borda `link` | Agora (acesso), Equipado, Derrotado, Feito, Respondido |
| Destaque | `.estado.destaque` | `pos`, borda `pos` | Mais cedo, Mais rentável, Sugerido |
| Apagado | `.estado.apagado` | `dim` (4.29:1 sobre `th`, falha), borda `line` | Tarde |
| Dois na mesma célula | `td.selos .estado + .estado` | `margin-left` `seal-gap` | Mais cedo e Mais rentável juntos |

ARIA: nenhum. O estado é o próprio texto.

## Fogueira `.fogueira`

Botão de alternância de `fogueira-size` (34px), fundo `th`, ícone `icons/fogueira.png` em `icon-fogueira` (L133–L142). Usada para marcar passo feito (`data-passo`, rótulo "Marcar como feito") e para escolher feitiço (`data-feitico`, rótulo "Selecionar para sintonizar").

| Estado | Gatilho | Visual | ARIA e teclado |
|---|---|---|---|
| Oculta | `hidden` (sem banco) | `display: none` | fora da leitura |
| Apagada | `aria-pressed="false"` | borda `line`; ícone `grayscale(1) brightness(0.55)` | `aria-label` e `title` com o rótulo |
| Hover apagada | `:hover` | ícone `grayscale(0.4) brightness(0.85)` | — |
| Acesa | `aria-pressed="true"` | borda `pos`; ícone em cor com `drop-shadow(0 0 5px)` em `fogueira-glow` | `aria-pressed="true"` |
| Gravando | `:disabled` (L775, L785) | `cursor: progress`, sem mudança de cor | botão desativado |
| Foco | `:focus-visible` | anel `focus-width` em `link`, offset `focus-offset` | Enter e Espaço nativos |
| Movimento reduzido | `prefers-reduced-motion: reduce` | sem `transition` no filtro | — |

A acesa mantém o brilho no hover: a regra de `[aria-pressed="true"] img` vem depois da de `:hover img` com a mesma especificidade. Depois de marcar um passo, `.confirmado` (12px, `pos`) mostra "confirma no próximo /build", "confirmado pelo save" ou "o save ainda não mostra" (L539–L542).

## Aba `.tab`

Marcellus 15px (`aba`), padding `tab-pad-y` e `tab-pad-x`, borda inferior `border-tab` (L106–L113).

| Estado | Gatilho | Visual | ARIA e teclado |
|---|---|---|---|
| Normal | `aria-selected="false"` | texto `text`, borda inferior `transparent` | `role="tab"`, `aria-controls="painel-<id>"` |
| Hover | `:hover` | texto `head` | — |
| Selecionada | `aria-selected="true"` | texto `head`, borda inferior `link` | painel `role="tabpanel"` visível, os outros com `hidden` |
| Foco | `:focus-visible` | anel `focus-width` em `link`, offset -2px | Seta direita e esquerda, em círculo, focam e ativam |
| Com contador | `<span class="count">` | 12px `body` (`contador`), `link` sobre `th`, borda `line` | o número entra no nome da aba |
| Contador zero | sem `span.count` | — | — |

A aba escolhida fica na URL (`#<id>`) e em `localStorage` (`buildsmith-aba`). Sem os dois, abre em Passos.

## Ação `.acao`

Botão de menu do cabeçalho (Atualizar plano, Responder fila), `acao-min-height` 38px, ícone `icon-small` (L170–L180).

| Estado | Gatilho | Visual | ARIA |
|---|---|---|---|
| Oculta | `.acoes[hidden]` (servidor sem runner, ou Artifact) | `display: none` | — |
| Normal | — | borda `line`, esquerda `border-acao` em `link`; fundo `acao-tint` até `th` em 75%; texto `head`; ícone `grayscale(1) brightness(0.7)` | `button` com texto |
| Hover | `:hover:not(:disabled)` | as quatro bordas em `link`; ícone em cor com `drop-shadow(0 0 5px)` em `ember-glow` | — |
| Foco | `:focus-visible` | anel `focus-width` em `link`, offset `focus-offset` | Enter e Espaço |
| Desativada | `:disabled` (skill rodando; Responder fila sem pendência) | texto `dim`, borda esquerda `line`, fundo `th` liso, ícone `grayscale(1) brightness(0.4)` | isenta de contraste |
| Com contador | `.count` sem `hidden` (só Responder fila) | igual ao contador da aba | o número entra no nome do botão |

## Botão pequeno `.pesq`

Marcellus 12px (`botao-pequeno`), borda `border-hair` em `link`, sem fundo (L153–L156, L191).

| Estado | Gatilho | Texto | Visual |
|---|---|---|---|
| Livre | sem pedido com o mesmo slug | Pesquisar | texto e borda `link` |
| Hover | `:hover` | — | fundo `panel` (vale também desativado) |
| Gravando | `disabled` (L761) | mantém | borda `line`, texto `text`, `cursor: default` |
| Na fila | `disabled`, pedido aberto (L551–L552) | Na fila | igual a gravando |
| Respondido | `disabled`, pedido respondido | Respondido | igual a gravando |
| Sem banco | clique copia o comando | Pesquisar | aparece `.copiado` ao lado: "Copiado: /buildsmith:build ds2 onde pegar: <texto>", ou só o comando se o clipboard falhar |
| Foco | `:focus-visible` | — | anel `focus-width` em `link`, offset `focus-offset` |

Na Forja o mesmo botão vira controle: rodando mostra Cancelar (fica `disabled` depois do clique, L795); ok mostra Fechar; erro e cancelado mostram Tentar de novo e Fechar.

## Formulário da fila `.fila-form`

| Parte | Estado | Visual |
|---|---|---|
| Campo | normal | fundo `td`, borda `line`, texto `head`, 14px `body` (`campo`), `maxlength="120"` |
| Campo | foco | anel `focus-width` em `link`, offset 1px |
| Botão Pesquisar | normal | Marcellus 14px (`botao-fila`), borda `link`, fundo `th`, texto `head` |
| Botão Pesquisar | foco, hover, desativado | sem regra própria: foco padrão do navegador |
| Lista | vazia | `.empty` "Nenhum pedido ainda." |
| Lista | com pedidos | tabela Pedido · De onde · Estado · Resposta, selo Na fila ou Respondido |

O rótulo do campo é "O que você quer saber", em `.sr-only`.

## Etapa da Forja `.etapas > .etapa`

Segmento de `segment-height` (6px) com rótulo Marcellus 11px (`rotulo-etapa`) embaixo (L192–L201). A classe vem do servidor (`e.estado`, L627).

| Estado | Classe | Segmento | Rótulo | ARIA |
|---|---|---|---|---|
| Pendente | `.etapa` (sem regra própria) | `track`, borda `line` | `dim` | — |
| Feita | `.etapa.feita` | `link`, borda `link` | `link` | — |
| Pulada | `.etapa.pulada` | listra `line` de 3px e vazio de 4px | `dim` | — |
| Atual | `.etapa.atual` | degradê `brasa` animado (1.6s linear infinite), borda `ember`, `box-shadow: 0 0 8px` em `ember-glow` | `head` | `aria-current="step"` |
| Tela estreita | `@media (max-width: 560px)` | igual | `display: none` | — |
| Movimento reduzido | `prefers-reduced-motion: reduce` | degradê parado | igual | — |

## Linha do microtexto `.linha`

12px/1.55 `body` (`texto-log`), tempo à esquerda em `dim` com `tabular-nums` (L205–L214).

| Tipo | Classe | Visual do texto |
|---|---|---|
| Ação | `.linha-acao` | prefixo "› " em `link`, texto `text` |
| Texto | `.linha-texto` | `head` |
| Pensamento | `.linha-pensamento` | `dim`, itálico (`pensamento-log`) |
| Etapa | `.linha-etapa` | Marcellus 12px, `letter-spacing: 0.08em`, `ember` (`etapa-log`) |
| Erro | `.linha-erro` | `neg` |
| Nova | `.nova` | entra com `surge` (0.35s ease-out) |

O `.microtexto` tem `role="log"`, `aria-live="off"`, `aria-label="O que o Claude está fazendo"` e `tabindex="0"`; o foco é 1px em `line` (`focus-width-log`). Guarda no máximo 200 linhas.

## Caixa da Forja `.forja`

Fundo `th`, borda `line`, padding `box-pad-y` `box-pad-x` 12px (L183–L217).

| Estado (`st.estado`) | Título (`titulo-passo`) | Classe | Botões | Mensagem |
|---|---|---|---|---|
| Oculta | — | `[hidden]` | — | — |
| `rodando` | Forjando o plano / Respondendo a fila; outro personagem: "Rodando para <nome>" | — | Cancelar | oculta |
| `ok` | Plano forjado / Fila respondida | — | Fechar | resposta do servidor, `text` |
| `erro` | A forja apagou | `.forja.erro` (título e mensagem em `neg`) | Tentar de novo, Fechar | mensagem do servidor |
| `cancelado` | Cancelado | `.forja.erro` | Tentar de novo, Fechar | mensagem do servidor |

Ao lado do título: a etapa atual em `ember` ("Pesquisa · 4 de 8") e o relógio `M:SS` em `text`, com o custo em US$ no fim. O cabeçalho `.forja-head` é `aria-live="polite"`.

## Faixa `.faixa`

| Estado | Gatilho | Visual |
|---|---|---|
| Oculta | `[hidden]` | `display: none` |
| Visível | Forja termina com `ok` nesta página | texto `faixa-text` sobre `band`, animação `acende` 2.8s; o JS põe `hidden` de novo em 2900ms |
| Movimento reduzido | `prefers-reduced-motion: reduce` | aparece parada até o `hidden` |

`pointer-events: none`: a faixa não bloqueia clique. Sem `role` nem `aria-live`; o título da Forja anuncia o fim.

## Barra de atributo `.bar`

| Estado | Visual | ARIA |
|---|---|---|
| Atual | `.now` em `link`, largura `min(valor, 99) / 99` | `role="img"`, `aria-label="VGR: 9 de 99, alvo 20"` |
| Alvo maior que o atual | marca `.goal` em `pos`, `bar-goal-width` 2px, passa 5px para fora; texto "→ 20" em `.pos` | o `aria-label` sempre cita o alvo |
| Alvo igual ou menor | só a barra e o número | — |

## Nó `.node`

| Estado | Gatilho | Visual |
|---|---|---|
| Com link | `<a class="node">` | nome em `link` |
| Sem link, ou link que não é http(s) | `<span class="node">` | nome em `head` |
| Hover com link | `a.node:hover .nm` | sublinha só o nome |
| Foco com link | `a:focus-visible` | anel `focus-width` em `link` |
| Sem `sub` | `.node.solo` | uma linha só |
| Sem ícone ou ícone quebrado | `.ini` | inicial Marcellus em `head` sobre `th` |
| Dentro de `td` | `td .node` | compacto, sem fundo e sem borda, ícone `icon-node-table` |

## Slots selecionados `.slots`

O número usado vai em `.pos` quando cabe no total e em `.neg` quando passa ("5 de 6" em `pos`). Antes do `applyState()` mostra "—".

## Carregando, vazio e erro

| Estado | Classe | Texto | Visual |
|---|---|---|---|
| Carregando | `.empty` | Carregando o plano… | `text`, itálico |
| Vazio | `.empty` | uma frase por seção, ex.: "Nenhum item pendente." | `text`, itálico |
| Valor ausente em célula | — | "—" | texto da célula |
| Erro de leitura | `.error` | Não consegui ler o plano.json publicado junto com a página. Rode o /buildsmith:build de novo para republicar. | padding 16px, borda `border-hair` em `neg`, texto `neg` (6.69:1 sobre `panel`) |
| Revelar mais | `details.mais` | Ver todas as fontes (N) | resumo em `link`, Marcellus 13px; aberto ganha `margin-bottom: 6px` |
