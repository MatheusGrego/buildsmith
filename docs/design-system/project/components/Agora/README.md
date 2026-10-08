# Agora

Caixa entre o cabeçalho e as abas que mostra até três próximas ações, cada uma com fogueira, título que leva ao passo e fluxo de nós, mais as almas que essas ações custam e o que ainda falta.

## Quando usar

- Use uma por página, logo depois do `header.top`, quando o plano tem `agora`.
- Ponha as ações que o jogador pode fazer já, na ordem em que deve fazê-las.

## Quando não usar

- Não repita a lista de passos. O Agora aponta para a aba Passos.
- Não ponha tabela de dados no Agora. Os dados ficam no Passo.
- Não use a caixa `.agora` para outro conteúdo. A outra caixa sobre `th` é a da Forja.

## O que entra

| Campo | Uso | Exemplo real (`example/plano.json` L2172–L2188) |
|---|---|---|
| `agora.acoes` | ids de `passos`, até 3 | `["equipar-trocar-anel", "upgrade-queimar-sublime-bone-dust", "explorar-libertar-o-straid"]` |
| título e fluxo de cada ação | vêm do passo (`titulo`, `fluxo`) | "Trocar anel": Old Leo Ring (sai) ➞ Ring of Binding (entra) |
| `agora.almas` | inteiro; a linha só aparece se for número | `0` |
| `agora.faltam` | lista de nós; "Faltam:" só aparece se tiver itens | Large Titanite Shard, `sub` "1 pro +6" |

## Anatomia

HTML de `nowPanel(p)` (`skills/build-page/template/index.html` L430–L438), com uma ação:

```html
<section class="agora" aria-label="Próximas ações"><h2>Agora</h2><div class="agora-acao">
    <button class="fogueira" type="button" data-passo="equipar-trocar-anel" aria-pressed="false" aria-label="Marcar como feito" title="Marcar como feito" hidden><img src="icons/fogueira.png" alt=""></button>
    <a class="step-title" href="#passo-equipar-trocar-anel" data-goto-passo="equipar-trocar-anel">Trocar anel</a>
    <div class="flow">…</div>
  </div>
  <div class="agora-resumo"><span>Almas pra essas ações: <span class="neg">0</span></span><span>Faltam:</span><div class="flow">…</div></div>
</section>
```

- `.agora` (L146): grid com `gap` `agora-gap`, padding `box-pad-y` `box-pad-x`, borda `border-hair` em `line`, fundo `th`, canto reto.
- `.agora h2` (L147): estilo `titulo-agora` (22px), sem borda e sem padding.
- `.agora-acao` (L148): flex com `flex-wrap: wrap`, `align-items: center` e `gap: 10px 12px`.
- `.agora-acao .step-title` (L149 sobre L82): estilo `titulo-acao-agora` (Marcellus 16px), cor `head`, `text-decoration: none`.
- `.agora-resumo` (L150): flex com `flex-wrap: wrap`, `gap: 8px 18px`, `align-items: center`, 13px, cor `text`. O número das almas vai em `.neg`.
- Dentro: Fogueira, Fluxo e No. Sobre `th`, o nó fica com fundo #292929 (`td` composto sobre `th`).
- A imagem `icons/fogueira.png` não está neste sistema; o preview mostra a fogueira sem ela. Os nós mostram a inicial (`.ini`), como a página faz sem os ícones da wiki.

## Estados e variantes

| Estado | Visual |
|---|---|
| Sem `agora` no plano | a caixa não existe (L428) |
| Sem banco | fogueiras com `hidden`; título e fluxo continuam |
| Com banco | fogueiras visíveis, apagadas ou acesas conforme `feitos/<id>` |
| Id de passo que não existe | a ação some sem aviso (`.filter(Boolean)`, L430) |
| `faltam` vazio ou ausente | sem "Faltam:" |
| `almas` não numérico | sem a linha das almas |

O título é link real (`href="#passo-<id>"`). O clique troca para a aba Passos e rola até o passo (L804–L805).

## Regras de conteúdo

- Ponha no máximo 3 ações, todas com id de passo que existe. O validador recusa mais de 3 e id inexistente (`skills/build-page/scripts/validate_plano.py` L184–L195); o template não corta.
- O título é o do passo: até 40 caracteres (`validate_plano.py` L85–L86). Escreva verbo no infinitivo ou o nome do alvo: "Trocar anel", "Libertar o Straid".
- A segunda linha do nó (`sub`) tem até 30 caracteres: "1 pro +6", "×1", "fogueira de Majula".
- `almas` é inteiro e sai com `Intl.NumberFormat("pt-BR")` (milhar com ponto).
- Os rótulos são fixos: "Agora", "Almas pra essas ações:", "Faltam:".

## Acessibilidade

- `<section aria-label="Próximas ações">` com `h2` "Agora".
- O título é `<a>` com `href`: funciona sem JS e recebe o anel de foco padrão (`focus-width` em `link`).
- A fogueira é botão de alternância com `aria-pressed` (ver Fogueira).
- Contraste sobre `th`: título `head` 18.88:1, resumo `text` 8.93:1, almas `neg` 7.11:1. Nó com link sobre #292929: 5.07:1; `sub` 6.88:1.
- A caixa se separa do painel pela borda `line`, não pelo tom (`th` sobre `panel` dá 1.06:1).

## Tokens usados

- Cor: `th`, `line`, `head`, `text`, `neg`, `td`.
- Espaço: `agora-gap`, `box-pad-y`, `box-pad-x`.
- Borda: `border-hair`.
- Tipo: `titulo-agora`, `titulo-acao-agora`, `pequeno`.

## Problemas conhecidos

- O 0 das almas sai em `neg`, como se fosse perda: "Almas pra essas ações: 0" em azul (`topo-desktop.png`). O número sempre entra em `.neg` (L437; ver Problemas conhecidos, item 10).
- No celular a seta do fluxo fica no fim da linha e o nó seguinte desce: "Old Leo Ring ➞" numa linha, "Ring of Binding" na outra (`topo-celular.png`; item 4).
- A imagem da fogueira não tem fallback (L246) e aparece quebrada (`topo-desktop.png`; item 7).
- O Agora não tem `.confirmado`: depois de marcar, o texto de confirmação só aparece na aba Passos.
