# EstadoVazio

Frase curta em itálico (`.empty`) no lugar de uma lista ou tabela sem dados, e a caixa `.error` que troca a página inteira quando o plano não carrega.

## Quando usar

- Use `.empty` quando uma seção, subseção ou lista não tem dado: uma frase por caso, no lugar exato da tabela ou da lista.
- Use `.empty` para a casca estática "Carregando o plano…", antes do `plano.json` chegar (`skills/build-page/template/index.html` L233).
- Use `.error` só quando o `plano.json` não pode ser lido. Ele troca todo o conteúdo do `#app` (L871).

## Quando não usar

- Não use `.empty` para valor ausente dentro de célula. Célula sem dado leva "—".
- Não use `.error` para falha da skill. Falha da skill é `.forja.erro` (ver Forja) e a linha `.linha-erro` do microtexto.
- Não esconda a seção vazia. Mantenha o título e ponha a frase embaixo.

## O que entra

O texto é fixo no template. A condição é a falta do dado no `plano.json` ou no banco:

| Onde | Texto | Linha | Condição |
|---|---|---|---|
| `#app`, antes do plano | Carregando o plano… | L233 | casca estática |
| Ficha, Desde a última vez | Primeira leitura do save. | L310 | `mudancas` vazia |
| Passos | Nenhum passo pendente. | L315 | nenhum grupo com passo |
| Fases | Sem fases planejadas. | L341 | `fases` vazia |
| Onde pegar | Nenhum item pendente. | L379 | `itens` vazia |
| Builds | Nenhuma comparação ainda. | L388 | `comparacao` vazia |
| Progresso | Este plano não tem dados de progresso. | L402 | sem `progresso` |
| Progresso, Chefes | Nenhum chefe listado. | L404 | `chefes` vazia |
| Progresso, Compras | Nenhuma compra registrada. | L405 | `compras` vazia |
| Progresso, Eventos | Nenhum evento aprendido. Rode /buildsmith:build ds2 antes e depois do evento, contando o que aconteceu. | L408 | `eventos` ausente ou vazia (como no exemplo) |
| Dano | Este plano não tem cálculo de dano. | L416 | `dano` ausente ou vazia |
| Feitiços | Este plano não tem feitiços. | L443 | sem `feiticos` |
| Fila | Nenhum pedido ainda. | L469 | nenhum pedido no banco |
| Fontes | Sem fontes. | L474 | `fontes` vazia |
| `#app`, erro | Não consegui ler o plano.json publicado junto com a página. Rode o /buildsmith:build de novo para republicar. | L871 | `fetch` falhou, resposta não OK, JSON inválido ou exceção no render |

## Anatomia

```html
<section><h2>Onde pegar<small>mais cedo e mais rentável a partir de onde você está</small></h2><p class="empty">Nenhum item pendente.</p></section>
```

```html
<div class="panel" id="app"><p class="error">Não consegui ler o plano.json publicado junto com a página. Rode o /buildsmith:build de novo para republicar.</p></div>
```

| Parte | Regra |
|---|---|
| `.empty` | `p` em `text`, itálico, estilo `vazio` (14px/1.6 `body`) (L102). `margin: 0` vem de `p` (L36). |
| `.error` | `p` com padding 16px, borda `border-hair` em `neg`, texto `neg` (L103; o padding não tem token). |
| Posição | Dentro da `section`, depois do `h2`, com o `gap` `section-gap` da seção. O `.error` fica direto no `.panel`. |

## Estados e variantes

| Caso | Resultado |
|---|---|
| Seção inteira sem dado | `h2` e `.empty` (Onde pegar, Fases, Builds, Dano, Feitiços, Fontes) |
| Subseção sem dado | só a subseção vira `.empty`; as outras seguem (Progresso, Ficha) |
| Plano sem o bloco opcional | seção com o nome da aba e a frase "Este plano não tem…" |
| Carregando | `.empty` sozinho no `.panel` |
| Erro de leitura | `.error` sozinho no `.panel`; sem abas, sem cabeçalho |

## Regras de conteúdo

- Escreva uma frase curta, com ponto final, que diz o que falta: "Nenhum item pendente.", "Sem fontes.".
- Use "Este plano não tem <coisa>." quando o bloco opcional não veio no plano.
- Só a mensagem de erro e a de Eventos trazem instrução, porque o jogador precisa agir: rodar o `/buildsmith:build`.
- Sem exclamação e sem emoji. Termo do jogo e comando ficam como são: "/buildsmith:build", "plano.json".

## Acessibilidade

- Contraste sobre `panel`: `.empty` (`text`) 8.40:1; `.error` (`neg`) 6.69:1 no texto e na borda.
- O erro não tem `role="alert"`: o leitor de tela não anuncia a troca da página.
- "Carregando o plano…" não tem `aria-busy` nem região viva. A troca pelo conteúdo é silenciosa.

## Tokens usados

Cor: `text`, `neg`, `panel`. Espaço: `section-gap`, `title-small-gap`. Borda: `border-hair`. Tipo: `vazio`, `corpo`, `titulo-secao`, `subtitulo-secao`.

## Problemas conhecidos

- `.error` sem `role="alert"` (L871).
- A lista da Fila não volta ao vazio: se os pedidos chegarem a zero, "Nenhum pedido ainda." não volta e a tabela antiga fica (L556).
