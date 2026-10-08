# TabelaDano

Tabela da aba Dano que mostra o AR físico de cada arma agora e depois de uma mudança do plano, com a diferença calculada pela página e o fluxo do que causa a mudança.

## Quando usar

- Use uma linha por mudança que altera o AR da arma da mão direita: fase de DEX ou STR, próximo upgrade, upgrade até +10 (`skills/build/SKILL.md`, item `dano`).
- Use só na aba Dano, numa seção com o título "Dano" e o subtítulo "AR físico pelas regras do jogo".

## Quando não usar

- Não use para o efeito de um passo. O passo leva a própria tabela Dado | Agora | Depois | Efeito (ver Passo).
- Não use para feitiço com dano calculado. Feitiço vai na aba Feitiços; aqui catalisador e feitiço levam "—".

## O que entra

`dano[]`: `{"arma": Nó, "agora": inteiro ou "—", "depois": inteiro ou "—", "detalhe": texto, "por_causa": [Nó]}` (`validate_plano.py` L294–L299). Exemplo real do `example/plano.json` (L2055 em diante):

```json
{"arma": {"tipo": "item", "nome": "Uchigatana", "link": "https://darksouls2.wiki.fextralife.com/Uchigatana", "sub": "+5 · FOR 10", "tem": true},
 "agora": 218, "depois": 226, "detalhe": "DES 18 → 25",
 "por_causa": [{"tipo": "almas", "nome": "99.790 almas", "link": "https://darksouls2.wiki.fextralife.com/Level", "sub": "nível 99 → 106"},
               {"tipo": "atributo", "nome": "Dexterity", "link": "https://darksouls2.wiki.fextralife.com/Dexterity", "sub": "18 → 25"}]}
```

(Os campos `icone` foram omitidos aqui; no plano eles existem.)

A coluna Diferença não vem do plano. A página calcula `depois − agora` quando os dois são números (`damage()`, L414–L424).

## Anatomia

```js
const value = (v) => typeof v === "number" ? fmt.format(v) : "—";
const diff = typeof d.agora === "number" && typeof d.depois === "number" ? d.depois - d.agora : null;
const shown = diff === null ? "—" : `<span class="${diff > 0 ? "pos" : diff < 0 ? "neg" : ""}">${diff > 0 ? "+" : ""}${fmt.format(diff)}</span>`;
return [node(d.arma), value(d.agora), value(d.depois), shown, esc(d.detalhe || ""), flow(d.por_causa) || "—"];
```

A tabela sai de `grid(["Arma", "Agora", "Depois", "Diferença", "Mudança", "Por causa de"], lines, [1, 2, 3])`. Uma linha real:

```html
<tr><td><a class="node" href="https://darksouls2.wiki.fextralife.com/Uchigatana" target="_blank" rel="noopener noreferrer"><span class="ini" aria-hidden="true">U</span><span class="nm">Uchigatana</span><span class="sub">+5 · FOR 10</span></a></td><td class="r">218</td><td class="r">226</td><td class="r"><span class="pos">+8</span></td><td>DES 18 → 25</td><td><div class="flow"><a class="node" …><span class="ini" aria-hidden="true">9</span><span class="nm">99.790 almas</span><span class="sub">nível 99 → 106</span></a><span class="arrow" aria-hidden="true">&#10142;</span><a class="node" …><span class="ini" aria-hidden="true">D</span><span class="nm">Dexterity</span><span class="sub">18 → 25</span></a></div></td></tr>
```

| Coluna | Conteúdo | Visual |
|---|---|---|
| Arma | nó compacto (`td .node`) | ícone `icon-node-table`, nome em `link` |
| Agora, Depois | número com `fmt` ou "—" | `td.r`, `head`, `tabular-nums` |
| Diferença | `span.pos`, `span.neg` ou `span` sem cor | `td.r` |
| Mudança | `detalhe` escapado | `corpo` em `head` |
| Por causa de | fluxo compacto (`td .flow`) ou "—" | seta `seta-tabela` em `link` |

O resto da anatomia (`.tw`, `table`, `th`, `td`) é a TabelaWiki.

## Estados e variantes

| Caso | Diferença |
|---|---|
| `depois` maior que `agora` | `<span class="pos">+13</span>`: o "+" vem do código |
| `depois` menor que `agora` | `<span class="neg">-N</span>`: o sinal vem do `Intl`, hífen ASCII |
| iguais | `<span class="">0</span>` |
| algum valor "—" | "—" sem `span`, também em Agora e Depois |
| `por_causa` vazio | "—" na última coluna |
| sem `dano` ou lista vazia | `<section><h2>Dano</h2><p class="empty">Este plano não tem cálculo de dano.</p></section>`, sem subtítulo |

A aba mostra o contador com `dano.length` e some com o número quando a lista está vazia (L485).

## Regras de conteúdo

- Escreva `agora` e `depois` como inteiros, sem milhar. A página formata. Sem cálculo, escreva "—".
- Escreva `detalhe` curto, no padrão "DES 18 → 25", "upgrade +5 → +6", "upgrade +5 → +10".
- Ponha no `sub` da arma o upgrade que vale na linha, como no exemplo ("+5 → +6", "+5 → +10").
- Monte `por_causa` com o que paga a mudança: almas e atributo, ou materiais e o ferreiro ("Large Titanite Shard" `×3` ➞ "Steady Hand McDuff" `1.320 almas`).
- Tire o AR das tabelas do jogo (`ds2calc.py ar`), nunca de cabeça.
- Todo nó `item` em `arma` e `por_causa` precisa de entrada em `itens` ou de `"tem": true` (`validate_plano.py` L246–L266).

## Acessibilidade

- A Diferença leva o sinal escrito além da cor: `pos` 7.80:1 e `neg` 5.40:1 sobre a célula.
- Seta e inicial ficam com `aria-hidden="true"`. O leitor de tela lê os nomes dos nós em ordem.
- Os nós da coluna Arma e Por causa de são links da wiki e abrem em outra aba (`target="_blank"`); o foco é o anel `focus-width` em `link` do `a`.

## Tokens usados

Os da TabelaWiki e mais: `pos`, `neg`, `link`, `node-pad-table`, `node-pad-right-table`, `node-icon-gap-table`, `icon-node-table`, `flow-gap-y-table`, `flow-gap-x-table`. Tipo: `inicial-no-tabela`, `nome-no`, `legenda-no`, `seta-tabela`, `subtitulo-secao` (o `h2 small`), `titulo-secao`.

## Problemas conhecidos

- A coluna Arma encolhe até quebrar o nome no meio: "Uchigat" / "ana" e "+5 · FOR" / "10" a 1280px (`aba-dano-desktop.png`); no celular o nome desce uma letra por linha (`aba-dano-celular.png`). Causa: `overflow-wrap: anywhere` no `.nm` (L70) e o fluxo longo de Por causa de.
- O menos da Diferença sai com hífen ASCII (`-`) pelo `Intl`; o texto escrito no plano usa "−" (U+2212).
- O exemplo mistura siglas: "+5 · FOR 10" e "DES 18 → 25" (`example/plano.json` L2062, L2067), enquanto a aba Atributos usa STR e DEX.
- A spec `2026-10-06-buildsmith-progresso-dano-design.md` (L71) lista Arma | Agora | Depois | Diferença | Por causa de; o código acrescenta a coluna Mudança (L423).
- Sem `<caption>` e sem `scope` nos `<th>`.
