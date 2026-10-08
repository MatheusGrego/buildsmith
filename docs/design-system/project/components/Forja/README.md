# Forja

Caixa do cabeçalho que acompanha a skill rodando pelo servidor local, com título, etapa atual, relógio, barra de 8 etapas, microtexto do que o Claude está fazendo e a mensagem final.

## Quando usar

- Use uma vez por página, dentro de `.top`, logo depois do grupo `.acoes` (`skills/build-page/template/index.html` L296).
- Mostre só na página servida pelo servidor local com runner (`GET /api/ping` com `rodar`, L823). No Artifact a caixa nunca aparece.
- Mostre do clique em Atualizar plano ou Responder fila até o jogador fechar. Ao abrir a página com uma execução rodando, a caixa aparece sozinha (`iniciarForja()`, L726–L737).

## Quando não usar

- Não use para outro progresso. A barra e o microtexto são da skill.
- Não use para o aviso de fim no meio da tela. Isso é a Faixa.
- Não escreva a resposta da skill fora da `.forja-msg`.

## O que entra

O status de `GET /api/<jogo>/<personagem>/execucao?desde=N`, pedido a cada 700ms enquanto roda (L671–L679). Formato em `app/runner.py` L382–L390:

```json
{"estado": "rodando", "modo": "plano", "alvo": {"jogo": "ds2", "personagem": "melatonina-vorcaro"},
 "etapa": "pesquisa",
 "etapas": [{"id": "fila", "nome": "Fila", "estado": "feita"}, {"id": "save", "nome": "Save", "estado": "feita"},
            {"id": "perfil", "nome": "Perfil", "estado": "pulada"}, {"id": "pesquisa", "nome": "Pesquisa", "estado": "atual"},
            {"id": "calculos", "nome": "Cálculos", "estado": "pendente"}, "… página, resposta, fim: pendente"],
 "eventos": [{"i": 4, "tipo": "etapa", "texto": "Pesquisa", "t": 41.8}, {"i": 5, "tipo": "acao", "texto": "Wiki: Bonfire Ascetic", "t": 41.8}],
 "ultimo": 6, "segundos": 83.4, "custo_usd": null, "mensagem": "", "resposta": ""}
```

- `estado`: `rodando`, `ok`, `erro`, `cancelado` (e `parado`, que não mostra a caixa).
- `modo`: `plano` ou `fila`. Escolhe o título.
- `etapas`: sempre as 8 de `app/runner.py` L22–L31, nesta ordem: Fila, Save, Perfil, Pesquisa, Cálculos, Página, Fila respondida, Concluído. O estado de cada uma sai de `status()` (L368–L381).
- `eventos[].tipo`: `acao`, `texto`, `pensamento`, `etapa`, `erro`.

Os textos do preview vêm do teste do runner (`tests/test_runner.py` L11–L22 e L28–L31): "Lendo a fila da página", "Lê o save", "Wiki: Bonfire Ascetic", "python prepare_page.py plano.json saida", resposta "Plano atualizado", custo 0.42 e o erro de login. A linha de pensamento é de demonstração.

## Anatomia

Montada na primeira pintura (L606–L609), com uma `.linha` por evento (L590–L595) e os botões reescritos a cada troca de estado (L643–L644):

```html
<div class="forja" id="forja" data-estado="rodando">
  <div class="forja-head" aria-live="polite"><span class="forja-titulo">Forjando o plano</span><span class="forja-etapa">Pesquisa · 4 de 8</span><span class="forja-tempo">1:23</span><span class="forja-botoes"><button class="pesq" type="button" data-forja="cancelar">Cancelar</button></span></div>
  <ol class="etapas" style="--n:8"><li class="etapa feita" data-etapa="fila"><span class="seg"></span><span class="rotulo">Fila</span></li>…<li class="etapa atual" data-etapa="pesquisa" aria-current="step"><span class="seg"></span><span class="rotulo">Pesquisa</span></li>…</ol>
  <div class="microtexto" role="log" aria-live="off" aria-label="O que o Claude está fazendo" tabindex="0">
    <div class="linha linha-acao"><span class="t">0:41</span><span class="x">Wiki: Bonfire Ascetic</span></div>
  </div>
  <p class="forja-msg" hidden></p>
</div>
```

| Parte | Regra |
|---|---|
| `.forja` | Grade com `gap` `forja-gap`; padding `box-pad-y` `box-pad-x` e 12px embaixo; borda `border-hair` em `line`; fundo `th`; `min-width: 0` (L183). `[hidden]` vira `display: none` (L184). |
| `.forja-head` | Flex com `flex-wrap: wrap`, `align-items: baseline`, `gap: 4px 14px` (L185; sem token). |
| `.forja-titulo` | `titulo-passo` (Marcellus 18px) em `head`; `neg` com `.forja.erro` (L186–L187). |
| `.forja-etapa` | `selo` (Marcellus 13px, `letter-spacing: 0.04em`) em `ember` (L188). |
| `.forja-tempo` | `subtitulo-grupo` (13px `body`) em `text`, `tabular-nums` (L189). |
| `.forja-botoes` | `margin-left: auto`, flex com `gap: 6px`; o `.pesq` perde a margem (L190–L191). |
| `.etapas` | `ol` sem marcador, grade de `--n` colunas iguais (o JS escreve `--n` com o número de etapas), `gap: 4px` (L192). |
| `.etapa` | Grade com `gap: 6px` (L193). `.seg` com `segment-height`, fundo `track`, borda `border-hair` em `line` (L194). `.rotulo` em `rotulo-etapa` (Marcellus 11px) e `dim`, uma linha com reticências (L195). |
| `.microtexto` | Altura de 6 linhas (`calc(6 * 1.55em)`), rolagem sem barra, `texto-log` (12px/1.55) em `text`, `padding-top: 1.2em`, máscara de `transparent` até `microtexto-mask` em 40% (L202–L203). Foco 1px em `line` (`focus-width-log`, L204). |
| `.linha` | Grade de `log-time-col` mais o resto, `gap: 8px` (L205). `.t` em `dim`, à direita, `tabular-nums` (L206). `.x` com `overflow-wrap: anywhere` (L207). |
| `.forja-msg` | `pequeno` em `text`, `white-space: pre-line`; `neg` com `.forja.erro` (L215–L217). |

## Estados e variantes

Caixa (L630–L648):

| `estado` | Título | Classe | Botões | `.forja-msg` |
|---|---|---|---|---|
| `rodando` | Forjando o plano / Respondendo a fila | nenhuma | Cancelar | oculta |
| `rodando`, outro personagem | "Rodando para <personagem>", com hífen virando espaço (L634) | nenhuma | Cancelar | oculta |
| `ok` | Plano forjado / Fila respondida | nenhuma | Fechar | `resposta` |
| `erro` | A forja apagou | `.forja.erro` | Tentar de novo, Fechar | `mensagem` |
| `cancelado` | Cancelado | `.forja.erro` | Tentar de novo, Fechar | `mensagem` (vazia no cancelamento) |
| Servidor não respondeu | A forja apagou | `.forja.erro` | Tentar de novo, Fechar | "O servidor local não respondeu. Abra pelo atalho Forja de Build." com uma etapa só, Concluído (L690) |

- Rodando, `.forja-etapa` mostra "<etapa> · <n> de 8" (L639). Nos outros estados fica vazia.
- O relógio é `M:SS` (L573). Rodando, conta a cada 1000ms (L667). No fim, soma o custo: "2:11 · US$ 0,42" (L657, `Intl` pt-BR em USD, L574).
- Cancelar fica `disabled` depois do clique (L795). Fechar esconde a caixa (L797). Tentar de novo roda o mesmo modo (L796).
- Com `ok` nesta página, a Faixa mostra o título e o plano recarrega sozinho (`terminou()`, L696–L711).

Etapa (classe = `estado` do servidor, L627):

| Classe | Segmento | Rótulo |
|---|---|---|
| `.etapa.pendente` (sem regra própria) | `track`, borda `line` | `dim` |
| `.etapa.feita` | `link`, borda `link` (L196) | `link` (L197) |
| `.etapa.pulada` | listra `line` de 3px e vazio de 4px (L198) | `dim` |
| `.etapa.atual` | degradê `ember-deep`, `ember`, `ember-core`, `ember`, `ember-deep` com a animação `brasa` 1.6s linear infinite; borda `ember`; `box-shadow: 0 0 8px` em `ember-glow` (L199) | `head` (L200); `aria-current="step"` |

Linha do microtexto:

| Classe | Texto |
|---|---|
| `.linha-acao` | prefixo "› " em `link`, texto `text` (L208) |
| `.linha-texto` | `head` (L209) |
| `.linha-pensamento` | `pensamento-log`, `dim` itálico (L210) |
| `.linha-etapa` | `etapa-log` (Marcellus 12px, `letter-spacing: 0.08em`) em `ember` (L211) |
| `.linha-erro` | `neg` (L212) |
| `.linha.nova` | entra com `surge` 0.35s ease-out (L213–L214) |

- O log segue o fim enquanto o jogador não rola (L615–L618, L622) e guarda no máximo 200 linhas (L621, L663). O preview repete isso com uma linha de script (`scrollTop = scrollHeight`).
- Abaixo de `breakpoint-narrow` (560px) os rótulos das etapas somem (L218–L220).
- Com `prefers-reduced-motion: reduce`, `brasa` e `surge` param (L228).

## Regras de conteúdo

- Use só estes títulos: Forjando o plano, Respondendo a fila, Plano forjado, Fila respondida, A forja apagou, Cancelado (L572, L634–L637). Caixa normal: a Marcellus SC já desenha versalete.
- Use os nomes de etapa do runner, sem trocar: Fila, Save, Perfil, Pesquisa, Cálculos, Página, Fila respondida, Concluído.
- O servidor corta em 180 caracteres as linhas de texto e de pensamento, os comandos, as páginas da wiki, as buscas e os padrões (`app/runner.py` L36, L132, L176–L193, L248). Corta a resposta em 600 (L389) e a mensagem de erro em 300 (L285, L350).
- Escreva a ação como o runner resume a ferramenta: "Wiki: <página>", "Busca: <termo>", "Lendo <arquivo>", "Gravando <arquivo>", "Procurando <padrão>", ou a descrição do comando (`describe_tool()`, L176–L193).

## Acessibilidade

- `.forja-head` é `aria-live="polite"`: título, etapa e botões são anunciados.
- O microtexto é `role="log"` com `aria-live="off"` (não anuncia cada linha), `aria-label` "O que o Claude está fazendo" e `tabindex="0"` para rolar pelo teclado.
- A etapa atual leva `aria-current="step"`.
- Contraste sobre `th`: título `head` 18.88:1; erro `neg` 7.11:1; etapa `ember` 8.81:1; tempo e mensagem `text` 8.93:1; rótulo feito `link` 6.59:1.
- `dim` sobre `th` dá 4.29:1 e falha 4.5:1 no rótulo pendente e pulado (11px), no tempo do log e no pensamento (12px).

## Tokens usados

Cor: `th`, `line`, `head`, `text`, `dim`, `link`, `neg`, `track`, `ember`, `ember-deep`, `ember-core`, `ember-glow`, `microtexto-mask`. Espaço: `box-pad-y`, `box-pad-x`, `forja-gap`. Borda: `border-hair`, `focus-width-log`. Layout: `segment-height`, `log-time-col`, `breakpoint-narrow`. Tipo: `titulo-passo`, `selo`, `subtitulo-grupo`, `rotulo-etapa`, `texto-log`, `pensamento-log`, `etapa-log`, `pequeno`, `botao-pequeno`.

## Problemas conhecidos

- A brasa continua acesa depois de erro e de cancelamento. O servidor manda a última etapa como `atual` em qualquer estado (`app/runner.py` L373–L374), e `.etapa.atual .seg` anima sem olhar `.forja.erro` (L199). O preview "Cancelado" mostra isso. Contraria o princípio de que a brasa só existe enquanto a skill roda.
- O relógio fica dentro da região `aria-live` e muda a cada segundo (L606, L667). O leitor de tela pode anunciar o tempo sem parar.
- O foco do microtexto é 1px em `line`, 1.49:1 sobre `th` (L204). O resto da página usa 2px em `link`.
- A listra da etapa pulada (`line` sobre `th`) dá 1.49:1 e o rótulo é o mesmo `dim` da pendente. Abaixo de 560px, sem rótulo, pulada e pendente se distinguem só pela listra.
- O `dim` falha 4.5:1 nos textos citados em Acessibilidade.
