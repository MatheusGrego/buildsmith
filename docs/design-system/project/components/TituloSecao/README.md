# TituloSecao

O `h2` abre cada seção com um título em Marcellus e uma linha fina embaixo, com um `<small>` opcional para contagem ou contexto; o `h3` de `.grupo` divide a aba Passos por tipo de passo.

## Quando usar

- Use um `h2` como primeiro filho de cada `<section>`.
- Use `<small>` dentro do `h2` para um número ("10"), uma razão ("5 de 41 derrotados") ou uma nota curta de método ("AR físico pelas regras do jogo").
- Use `.grupo > h3`, com a contagem em `<small>`, para cada grupo de passos.

## Quando não usar

- Não use `h2` para o nome do personagem. Isso é o `h1` do Cabecalho.
- Não use `h3` fora de `.grupo`: o estilo só existe em `.grupo h3`.
- Para rótulo de bloco sem hierarquia ("Ajuste sugerido", na aba Builds) use `.label`, não um título.

## O que entra

| Título | `<small>` | Exemplo real |
|---|---|---|
| Chefes | `${derrotados} de ${total} derrotados` | "5 de 41 derrotados" |
| Compras | `progresso.compras.length` | "10" |
| Dano | texto fixo | "AR físico pelas regras do jogo" |
| Feitiços | texto fixo | "AR calculado pelas regras do jogo" |
| Onde pegar | texto fixo | "mais cedo e mais rentável a partir de onde você está" |
| Fila de pesquisa | depende do servidor | "respondida no próximo /buildsmith:build" ou "o botão Responder fila (no topo) responde agora" |
| `h3` de grupo | número de passos do tipo | Equipar 1, Explorar 2, Chefes 1, Compras 3, Upgrades 2, Farms 1, Nível 1 |

Sem `<small>`: Agora, Ficha, Desde a última vez, Próximos passos, Eventos, Atributos, Fases de nível, Outras builds, Fontes; e Progresso, Dano e Feitiços quando a seção está vazia.

Os grupos seguem a ordem de `GRUPOS` (`skills/build-page/template/index.html` L239–L240): Equipar, Explorar, Chefes, Trocas de alma, Compras, Upgrades, Farms, Nível. Grupo sem passo não aparece (L314).

## Anatomia

```html
<section><h2>Chefes<small>5 de 41 derrotados</small></h2>…</section>

<div class="grupo">
  <h3>Equipar<small>1</small></h3>
  <ol class="steps">…</ol>
</div>
```

- `h2` (L33, L35): estilo `titulo-secao`, Marcellus `clamp(22px, 3.4vw, 30px)`, `line-height: 1.3`, cor `head`, `margin: 0`, `text-wrap: balance`, `padding-bottom` `title-rule-gap`, borda inferior `border-hair` em `line`.
- `h2 small` (L114): estilo `subtitulo-secao` (14px `body`, `letter-spacing: 0`), cor `text`, `margin-left` `title-small-gap`.
- `section` (L39): grid com `gap` `section-gap`. Seções da mesma aba ficam a `tab-panel-gap` uma da outra (L112).
- `.grupo` (L127): grid com `gap` `group-gap`.
- `.grupo h3` (L128): estilo `titulo-grupo` (Marcellus 20px), cor `head`, `margin: 0`, flex com `align-items: baseline` e `gap` `group-title-gap`.
- `.grupo h3 small` (L129): estilo `subtitulo-grupo` (13px `body`), cor `text`.
- O preview mostra os grupos sem os passos, só para ver os títulos.

## Estados e variantes

| Variante | Visual |
|---|---|
| `h2` | Marcellus, linha `line` embaixo |
| `h2` com `<small>` | contexto em `body` 14px na mesma linha; quebra junto quando falta largura |
| `h2` do Agora | `.agora h2` (L147): 22px (`titulo-agora`), sem linha e sem padding |
| `h3` de grupo | Marcellus 20px, contagem alinhada pela linha de base |

## Regras de conteúdo

- Escreva o título curto, caixa normal, como substantivo: "Chefes", "Fases de nível". A Marcellus SC desenha o versalete; não use `text-transform`.
- Escreva o `<small>` em minúsculas, sem ponto final: um número, uma razão ou uma frase curta.

## Acessibilidade

- Hierarquia: `h1` no Cabecalho, `h2` por seção, `h3` por grupo de passos.
- Contraste sobre `panel`: título `head` 17.76:1; `<small>` em `text` 8.40:1. No Agora, `head` sobre `th`: 18.88:1.
- A linha embaixo do `h2` (`line`, 1.41:1) é decorativa.

## Tokens usados

- Cor: `head`, `text`, `line`.
- Espaço: `title-rule-gap`, `title-small-gap`, `section-gap`, `tab-panel-gap`, `group-gap`, `group-title-gap`.
- Borda: `border-hair`.
- Tipo: `titulo-secao`, `subtitulo-secao`, `titulo-grupo`, `subtitulo-grupo`, `titulo-agora`.

## Problemas conhecidos

- O `<small>` fica colado ao título no texto do heading. O leitor de tela lê "Chefes5 de 41 derrotados" e "Equipar1" (L409, L317); o espaço é só `margin-left`.
- O rótulo da aba e o `h2` nem sempre batem: "Fases" e "Fases de nível", "Builds" e "Outras builds", "Passos" e "Próximos passos", "Fila" e "Fila de pesquisa", "Progresso" e as seções Chefes, Compras e Eventos.
