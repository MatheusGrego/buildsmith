# Fila

Aba Fila com o formulário de pergunta livre para a skill e a lista de pedidos, cada um com origem, selo Na fila ou Respondido e o link para a resposta em Onde pegar.

## Quando usar

- Use uma vez por página, no painel da aba `fila` (`skills/build-page/template/index.html` L491).
- Use para a pergunta que não cabe em um requisito da tabela: "Onde farmar Bonfire Ascetic".

## Quando não usar

- Não use para perguntar sobre um requisito que já está na tabela de fontes. Use o botão Pesquisar da linha: o pedido entra na mesma fila, com o nome do item como origem.
- Não mostre a resposta por extenso na lista. A skill responde criando ou atualizando a entrada em `itens`; a lista só leva o link "ver em Onde pegar".

## O que entra

Nada do `plano.json`. A página lê a coleção `pedidos` do banco (Artifact ou servidor local):

| Campo | Valor | Quem grava |
|---|---|---|
| `texto` | pergunta já limpa por `limpaPedido()`, até 120 caracteres | página (L763) |
| `origem` | `"fila"` no formulário; nome do item no Pesquisar; até 80 | página |
| `estado` | `"na_fila"` ou `"respondido"` | página cria; a skill responde (`app/serve.py` L342) |
| `criado_em` | ISO-8601; ordena a lista, mais novo primeiro (L554) | página |
| `item_id` | `itens[].id` da resposta | skill |

O servidor diz se há runner (`GET /api/ping`, `rodar`, L823). Isso troca o subtítulo.

O preview usa quatro pedidos de demonstração montados com textos do exemplo: o placeholder "Onde farmar Bonfire Ascetic", dois requisitos do Large Titanite Shard ("Lost Bastille", "1ª caverna após a fogueira") e o item "Lizard Staff". O `plano.json` não guarda pedidos.

## Anatomia

`queue()` (L462–L471) e a lista de `applyState()` (L554–L562):

```html
<section><h2>Fila de pesquisa<small>respondida no próximo /buildsmith:build</small></h2>
  <form class="fila-form" id="fila-form">
    <label class="sr-only" for="fila-texto">O que você quer saber</label>
    <input id="fila-texto" type="text" maxlength="120" placeholder="Onde farmar Bonfire Ascetic" autocomplete="off">
    <button type="submit">Pesquisar</button>
  </form>
  <div id="fila-lista"><div class="tw"><table><thead><tr><th>Pedido</th><th>De onde</th><th>Estado</th><th>Resposta</th></tr></thead><tbody>
    <tr><td>Lost Bastille</td><td>Large Titanite Shard</td><td class="selos"><span class="estado">Na fila</span></td><td>—</td></tr>
    <tr><td>Lizard Staff</td><td>fila</td><td class="selos"><span class="estado feito">Respondido</span></td><td><a class="req-link" href="#item-lizard-staff" data-goto-item="lizard-staff">ver em Onde pegar</a></td></tr>
  </tbody></table></div></div>
</section>
```

| Parte | Regra |
|---|---|
| `.fila-form` | `display: flex`, `flex-wrap: wrap`, `gap: 8px` (L158; sem token). |
| `.fila-form input` | `flex: 1 1` `fila-input-basis`, `min-width: 0`, fundo `td`, borda `border-hair` em `line`, texto `head`, padding `control-pad-y` 10px, estilo `campo` (L159). |
| `.fila-form input:focus-visible` | Anel `focus-width` em `link`, `outline-offset: 1px` (L160). |
| `.fila-form button` | Estilo `botao-fila` (Marcellus 14px), padding `control-pad-y` 14px, borda `border-hair` em `link`, fundo `th`, texto `head` (L161). |
| `.sr-only` | Rótulo só para leitor de tela (L165). |
| Lista | Tabela wiki (ver TabelaWiki) com Pedido, De onde, Estado, Resposta. Selo em `td.selos` (ver Selo). Resposta em `.req-link` ou "—". |
| `.copiado` | Nota depois do formulário quando não há banco (ver Pesquisar). |

## Estados e variantes

| Estado | Gatilho | Resultado |
|---|---|---|
| Sem pedidos | coleção vazia | `<p class="empty">Nenhum pedido ainda.</p>` (L469) |
| Com pedidos | ao menos um pedido | tabela no lugar do vazio, mais novo primeiro |
| Na fila | `estado` diferente de `respondido` | selo `.estado` neutro, resposta "—" |
| Respondido | `estado: "respondido"` | selo `.estado.feito`; com `item_id`, link "ver em Onde pegar" que abre a aba `onde` no item (L802–L803) |
| Subtítulo sem runner | página no Artifact, ou servidor sem runner | "respondida no próximo /buildsmith:build" (L463) |
| Subtítulo com runner | `forja.rodar` verdadeiro | "o botão Responder fila (no topo) responde agora"; `connect()` troca o texto depois do ping (L857–L859) |
| Envio com banco | Enter ou botão | grava `pedidos/<slug>` e limpa o campo (L807–L812) |
| Envio sem banco | Enter ou botão | copia `/buildsmith:build ds2 onde pegar: <texto>` e põe a nota `.copiado` depois do formulário; a lista fica vazia |
| Contador da aba | pedidos abertos | `<span class="count">` com o número; some com zero (L563–L565) |

## Regras de conteúdo

- Mantenha o placeholder "Onde farmar Bonfire Ascetic" e o rótulo "O que você quer saber".
- Limite o campo a 120 caracteres (`maxlength`, L466). O texto gravado é o limpo: sem caractere de controle e sem símbolos fora de letras, números, espaço e `' & + , . ( ) -` (L742–L745).
- Use só os selos Na fila e Respondido, e "ver em Onde pegar" como texto do link.
- Escreva "—" na resposta e na origem ausentes (L558, L560).

## Acessibilidade

- O campo tem rótulo real (`label` com `for`). Enter envia, pelo `form` nativo. `autocomplete="off"`.
- O campo tem anel de foco `link` de 2px. O botão não tem regra de foco e usa o anel do navegador.
- Contraste do texto digitado: `head` sobre `#2a2a2a` (`td` sobre `panel`), 14.35:1. A cor do placeholder vem do navegador e não foi medida.
- O contorno do campo falha 3:1: borda `line` 1.41:1 e fundo 1.24:1 contra `panel`. A borda `link` do botão dá 6.19:1.
- Pedido novo não é anunciado: a lista não tem `aria-live`.

## Tokens usados

Cor: `td`, `line`, `head`, `link`, `th`, `text`, `panel`. Espaço: `control-pad-y`, `inline-offset`, `section-gap`, `title-small-gap`. Borda: `border-hair`, `focus-width`. Layout: `fila-input-basis`. Tipo: `titulo-secao`, `subtitulo-secao`, `campo`, `botao-fila`, `contador`, `vazio`, `selo`. Mais os tokens de TabelaWiki.

## Problemas conhecidos

- O contorno do campo falha 3:1 (L159; ver Problemas conhecidos, item 9).
- O botão do formulário não tem `:hover`, `:focus-visible` nem `:disabled` (L161).
- A lista não volta ao vazio: se os pedidos chegarem a zero, `if (box && list.length)` (L556) não repõe "Nenhum pedido ainda." e a tabela antiga fica.
- Falha ao gravar é silenciosa e o campo limpa mesmo assim (L764–L766, L811). O servidor recusa com 400 "documento invalido" e com 409 "fila cheia" depois de 50 pedidos abertos (`app/serve.py` L228, L233–L234).
- Sem banco, cada envio acrescenta outra `.copiado` depois do formulário (L756).
