# Fluxo

Sequência de nós ligados pela seta ➞ que mostra a ordem de uma ação: de onde algo sai e para onde vai, no formato [entrada] ➞ [saída].

## Quando usar

- Use no passo (`passos[].fluxo`), na coluna Como das fontes de item (`itens[].fontes[].fluxo`), no ajuste de build (`comparacao[].ajuste`), na coluna Por causa de do Dano (`dano[].por_causa`) e no painel Agora (ações e Faltam).
- Use quando a ordem importa: chegar à fogueira, abrir o baú, pegar o item; ou o anel que sai e o que entra.

## Quando não usar

- Não use para uma lista sem ordem. Equipamento vai em `.equipped` (ver Ficha).
- Não use a seta ➞ dentro de texto. Transição de valor no texto usa "→" ("VGR 9 → 20", "nível 65 → 76").
- Não use para explicar. O fluxo substitui a frase; não ponha frase ao lado dele.

## O que entra

Uma lista de Nós. Exemplo real, passo "Trocar anel" do `example/plano.json` (L87 em diante, `icone` omitido aqui):

```json
"fluxo": [
  {"tipo": "item", "nome": "Old Leo Ring", "link": "https://darksouls2.wiki.fextralife.com/Old+Leo+Ring", "sub": "sai", "tem": true},
  {"tipo": "item", "nome": "Ring of Binding", "link": "https://darksouls2.wiki.fextralife.com/Ring+of+Binding", "sub": "entra", "tem": true}
]
```

## Anatomia

`flow()` (`skills/build-page/template/index.html` L278):

```js
const flow = (nodes) => (nodes && nodes.length) ? `<div class="flow">${nodes.map(node).join('<span class="arrow" aria-hidden="true">&#10142;</span>')}</div>` : "";
```

HTML real do exemplo:

```html
<div class="flow"><a class="node" href="https://darksouls2.wiki.fextralife.com/Old+Leo+Ring" target="_blank" rel="noopener noreferrer"><span class="ini" aria-hidden="true">O</span><span class="nm">Old Leo Ring</span><span class="sub">sai</span></a><span class="arrow" aria-hidden="true">&#10142;</span><a class="node" href="https://darksouls2.wiki.fextralife.com/Ring+of+Binding" target="_blank" rel="noopener noreferrer"><span class="ini" aria-hidden="true">R</span><span class="nm">Ring of Binding</span><span class="sub">entra</span></a></div>
```

| Parte | Regra |
|---|---|
| `.flow` | `display: flex`, `flex-wrap: wrap`, `align-items: center`, `gap` `flow-gap-y` `flow-gap-x` (L64). |
| `.arrow` | ➞ (U+279E, `&#10142;`) em `link`, estilo `seta` (20px, `line-height: 1`) (L65). |
| `.node` | ver No. |
| `td .flow` | `gap` `flow-gap-y-table` `flow-gap-x-table` (L119). |
| `td .arrow` | estilo `seta-tabela` (16px) (L120). |

## Estados e variantes

- Lista vazia ou ausente: `flow()` devolve nada. Na coluna Por causa de do Dano o lugar vira "—" (L421).
- Um nó: sem seta (`agora.faltam` com "Large Titanite Shard" `1 pro +6`).
- Vários nós: uma seta entre cada par. O fluxo mais longo do exemplo tem 4 nós, a fonte da Dull Ember: The Pursuer ➞ Ninho ➞ The Tower Apart ➞ Baú de ferro.
- Sem espaço: o fluxo quebra linha (`flex-wrap`).
- Dentro de tabela: espaços menores, seta de 16px e nós compactos.
- Com o rótulo "Ajuste sugerido" (`.label`) antes, na aba Builds (ver Comparacao).

## Regras de conteúdo

- Ponha os nós na ordem em que o jogador age.
- Diga o papel de cada nó no `sub` ("sai", "entra", "agora", "depois", "fogueira", "2.500 almas").
- Mantenha a seta ➞ só entre nós. No `sub`, transição de valor usa "→" ("tem 2 → 3").
- Dê pelo menos um nó a cada fonte de item: o validador recusa fluxo vazio em `itens[].fontes[]` (`validate_plano.py` L230–L231).

## Acessibilidade

- A seta tem `aria-hidden="true"`. O leitor de tela lê os nomes dos nós em ordem, sem palavra de ligação.
- A seta em `link` dá 6.19:1 sobre `panel`, 6.59:1 sobre `th` (painel Agora) e 5.01:1 sobre a célula de tabela.

## Tokens usados

Cor: `link`. Espaço: `flow-gap-y`, `flow-gap-x`, `flow-gap-y-table`, `flow-gap-x-table`. Tipo: `seta`, `seta-tabela`. Mais os tokens do No.

## Problemas conhecidos

- Seta pendurada no fim da linha: a seta é um item próprio do `.flow` e fica com o nó da esquerda quando a linha quebra. "Old Leo Ring ➞" fica numa linha e "Ring of Binding" desce para a outra no painel Agora a 400px (`topo-celular.png`).
- Na coluna Como das fontes de item, a 400px, o nome dos nós desce uma letra por linha (`recorte-onde-celular.png`). A causa é a do No.
- A spec `2026-10-06-buildsmith-pagina-v2-design.md` desenha a seta como ➜ (U+279C, L9 e L41); o código usa ➞ (U+279E).
