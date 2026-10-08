# Wiki e fidelidade

A página imita a wiki Fextralife do Dark Souls II e alguns sinais da interface do jogo. Esta seção diz o que foi conferido, o que não foi e onde a página difere. `T:<linha>` é `skills/build-page/template/index.html`.

## Confiança

| Marca | Quer dizer |
|---|---|
| lido | visto num arquivo, com linha citada |
| registro do projeto | escrito no repositório como "extraído da wiki em 2026-10-06" (spec `docs/superpowers/specs/2026-10-06-buildsmith-pagina-v2-design.md`, L11–L27); não conferido de novo |
| não verificado | ninguém confirmou |

## O que foi lido

- Cinco páginas da wiki do DS2 salvas em HTML no fim de 2022, num repositório público do GitHub (`ephemer1s/Dark-Souls-Items-Dataset`, pasta `experiments/wikiReader/ds2/`): Life Ring (LR), Mace (MC), Scimitar (SC), Chaos Set (CS) e Bat Staff (BS). Elas mostram a estrutura (infobox, `wiki_table`, `h3.bonfire`, breadcrumbs) e os estilos inline. O CSS do site fica em arquivos externos (`styles-global-min.css`, `theme-general.css`, `styles.css`) que não foram lidos.
- Dois scrapers de terceiros que leem a wiki do DS2 (`breno-hof/soulsle-scrapers`, `JoseRuizLopez/Darksouls-character-network`): colunas da lista de chefes e o infobox de NPC e chefe (`HP | Souls | Location | Drops`).

## O que não foi verificado

- A wiki ao vivo (2026). O domínio, o CSS, as imagens e o Wayback Machine foram recusados pela rede de saída. As cores e fontes da wiki atual vêm só do registro do projeto.
- A fonte dos títulos. A página usa Marcellus SC; não há evidência lida de que a wiki use essa fonte.
- Zebra nas linhas, cor do `h2` e do `h3.bonfire`, hover de link, padding e borda reais das células.
- Toda a interface do jogo: fonte dos menus, cores da faixa "BONFIRE LIT", cores de status e de comparação de equipamento.

## A wiki mudou entre 2022 e 2026

| Sinal | 2022 (lido) | 2026 (registro do projeto) |
|---|---|---|
| Caminho de imagem | `/file/Dark-Souls-2/Mace.png` (MC:971) | `static0.fextralifeimages.com/file/darksouls2/…`, com pasta em hash e `thumb/NNNpx-` |
| Fundo | `#111` no `body` (LR:93) | `#101013` |
| Texto | `#fff` no `body` (LR:93) | `#b4b2b0` |
| Painel | layout Bootstrap, sem painel arredondado | `#181818`, borda `#333` 1px, raio 12px |

Use o HTML de 2022 como referência de estrutura (o que existe e em que ordem), não de pixel.

## Wiki × página × diferença

| # | Elemento | Wiki | Página | Diferença |
|---|---|---|---|---|
| 1 | Fundo | 2022: `#111` (LR:93). 2026: `#101013` (registro) | `bg` #101013 (T:8) | igual ao registro de 2026 |
| 2 | Texto | 2022: `#fff`. 2026: `#b4b2b0` (registro) | `text` #b4b2b0 (T:11) | igual ao registro de 2026 |
| 3 | Corpo | 14px (LR:93), família não lida | `font: 14px/1.6 var(--body)` (T:30) | tamanho igual; altura de linha e família não verificadas |
| 4 | Fonte de título | não verificada | Marcellus SC, peso 400 (T:4, T:25, T:33) | registro do projeto, sem prova lida |
| 5 | Dourado | `#AB966F` no botão do Discord (MC:1821) | `link` #ab966f (T:13) | coerente; a cor do `a.wiki_link` não foi lida |
| 6 | Painel | 2022: sem painel. 2026: `#181818`, 1px `#333`, raio 12px (registro) | `.panel` (T:32) | igual ao registro |
| 7 | Largura | não lida | `page-max-width` 64rem, `gutter` 16px (T:31) | não comparável |
| 8 | Título da página | `h1 > a#page-title`, "Nome \| Dark Souls 2 Wiki" (LR:889–892) | `h1` com o nome do personagem (T:34, T:290) | sem sufixo de site |
| 9 | Breadcrumbs | "Equipment & Magic / Rings" (LR:941–942) | não existe; `.meta` mostra "jogo · atualizado <data>" (T:289) | falta |
| 10 | Data de revisão | `time[itemprop=dateModified]` à direita (LR:945) | "atualizado" + data pt-BR à esquerda (T:260, T:289) | posição e formato diferentes |
| 11 | Navegação | barra superior e menu lateral com 8 seções (LR:154, LR:354) | abas fixas no topo, Marcellus 15px, borda dourada de 2px na ativa (T:106–111) | diferente de propósito: app, não wiki |
| 12 | Título de seção | `h3.bonfire` ou `h3.titlearea` (LR:986, MC:1072) | `h2` com linha embaixo (T:35); `h3` de grupo 20px (T:128) | a wiki usa `h3` com classe `bonfire` (provável ícone de fogueira, não verificado) |
| 13 | Infobox | tabela no topo com nome, imagem de 50px, pares ícone/valor 20×20 (MC:964–1049) | não existe; a Ficha é uma tabela de 1 linha mais os nós equipados (T:300–306) | falta |
| 14 | Contorno da tabela | não lido; `#d9d9d9` 3px (registro) | `border-table` em `edge` (T:55) | igual ao registro |
| 15 | `th` | não lido; fundo `#111111` (registro). Cabeçalho de grupo centralizado (MC:1078–1081) | `th` à esquerda, Marcellus 14px, `letter-spacing: 0.02em` (T:56) | a wiki centraliza |
| 16 | `td` | `rgba(45,45,45,.85)`, borda `#333` (registro); valores centralizados inline (MC:1164) | `td` à esquerda, número à direita com `.r` (T:57–58) | alinhamento diferente |
| 17 | Zebra | não verificada | não tem (T:57) | lacuna nos dois lados |
| 18 | Rótulo de linha | `<th>` na 1ª coluna (MC:1163) | 1ª coluna é `td` (T:282, T:393) | a wiki destaca o rótulo com estilo de cabeçalho |
| 19 | Cabeçalho agrupado | `colspan` 6/6/2/5 (MC:1078–1081) | não existe | falta |
| 20 | Ícone no cabeçalho | 22px por coluna (MC:1087) | só texto (T:392) | falta |
| 21 | Tabela de dano | linhas = variantes (Regular, +10, infusões), colunas = tipos de dano com ícone | linhas = armas; Agora, Depois, Diferença, Mudança, Por causa de (T:414–424) | estrutura diferente de propósito (antes × depois) |
| 22 | Valor vazio | `-` (MC:1165) e `–` (MC:1016) | `—` (T:249, T:417, T:421) | caractere diferente |
| 23 | Cor de ganho e perda | não existe; só ícones `_green` para bônus (MC:1020) | `pos` e `neg` com legenda (T:17–18, T:291) | do buildsmith, não da wiki |
| 24 | Ícone de célula | 20×20, 22px, 27–28px, 50px | 22, 24, 26, 28 e 40px (T:61, T:68, T:88, T:118, T:135) | a wiki não usa 40px |
| 25 | Rótulo pequeno | `#a78d80` 11.2px sob o ícone (MC:1609) | `.label` 13px, `.node .sub` 12px em `text` (T:72, T:100) | o tom `#a78d80` não existe na página |
| 26 | Lore | `blockquote` (LR:976, MC:1054) | não existe | fora do escopo |
| 27 | Escalonamento | "12<br> A (*B)" na mesma célula (MC:1014) | requisito em texto, `neg` se faltar (T:453) | sem letra de escalonamento |
| 28 | Páginas da mesma tag | caixa com links separados por ♦ (LR:1037–1040) | aba Fontes é uma `ul` (T:474) | opcional |
| 29 | Onde encontrar | `ul` com links sob `h3.bonfire` (LR:1013, MC:1057) | tabela # · Como · Requisito · Acesso · Rendimento · Destaque (T:355–380) | ganho do buildsmith |
| 30 | Link | `a.wiki_link` | `a`, `.req-link`, `a.node` em `link` (T:37, T:66, T:164) | equivalente |
| 31 | Faixa "BONFIRE LIT" | jogo: não verificado | `faixa-text` sobre `band`, Marcellus `clamp(24px, 6vw, 46px)`, `letter-spacing: 0.18em`, 2.8s (T:225–226) | suposição; conferir com print |
| 32 | Página inicial do servidor | — | `app/serve.py` L281–L282: `font:15px Helvetica,Arial,sans-serif`, `h1` em `Georgia,serif` | incoerente com o template |

## Como fechar as lacunas

1. Abra https://darksouls2.wiki.fextralife.com/Mace num navegador.
2. No console, rode o script abaixo. Ele devolve os estilos computados de cada seletor; um seletor que não existe mais volta `null`, e isso também é informação.

```js
JSON.stringify(Object.fromEntries([
  "body", "#wiki-content-block", ".infobox", ".infobox th", ".infobox td", ".infobox h2",
  ".wiki_table", ".wiki_table th", ".wiki_table td", ".wiki_table tr:nth-child(2) td", ".wiki_table tr:nth-child(3) td",
  "h1", "h3.bonfire", "h3.titlearea", "a.wiki_link", ".breadcrumbs", ".breadcrumbs a", "blockquote", ".revisiondate"
].map((s) => {
  const el = document.querySelector(s);
  if (!el) return [s, null];
  const cs = getComputedStyle(el);
  return [s, Object.fromEntries(["color", "background-color", "background-image", "font-family", "font-size",
    "font-weight", "line-height", "letter-spacing", "text-transform", "text-align", "padding", "border",
    "border-radius"].map((p) => [p, cs.getPropertyValue(p)]))];
})), null, 2);
```

3. Repita em `/Life+Ring`, `/Chaos+Set`, `/Pursuer`, `/Majula` e `/Stats`. As três últimas cobrem chefe, lugar e a tabela de atributos, que não estão no HTML de 2022.
4. Compare `tr:nth-child(2) td` com `tr:nth-child(3) td` para saber se há zebra.
5. Em `h3.bonfire`, olhe `background-image` (deve apontar para `bonfire-background.png`, o mesmo arquivo que `games/ds2/icons.json` usa como ícone da fogueira) e `padding-left`.
6. Para o jogo, capture em 1920×1080: a faixa "BONFIRE LIT" (cor do texto, cor e opacidade da faixa, largura do degradê, espaçamento), a tela de level up com um atributo subindo, a comparação de arma no inventário, o HUD (PV, vigor, acúmulo de status) e um menu de lista.
7. Troque nesta tabela cada "registro do projeto" e "não verificado" pelo valor medido, e atualize o token correspondente em `tokens.json` se ele mudar.
