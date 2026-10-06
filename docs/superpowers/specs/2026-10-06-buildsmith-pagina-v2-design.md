# buildsmith — página v2 (estilo wiki, dados no lugar de texto)

Data: 2026-10-06
Status: aprovado em conversa (mockup `Próximos passos` aprovado; estilo vale para a página inteira)
Substitui: seção "Página" e o formato de `plano.json` de `2026-10-06-buildsmith-design.md`

## Objetivo

A página mostra **dados, não frases**. Todo passo, item e comparação vira um fluxo de nós com ícone e link (`[entrada] ➜ [saída]`) e uma tabela de números. O visual copia a wiki do DS2 (Fextralife).

## Visual (tokens extraídos da wiki em 2026-10-06)

| Token | Valor | Uso |
|---|---|---|
| `--bg` | `#101013` | fundo da página |
| `--panel` | `#181818`, borda `#333` 1px, raio 12px | bloco principal |
| `--text` | `#b4b2b0` | texto comum |
| `--head` | `#ffffff` | títulos, cabeçalhos de tabela, valores |
| `--link` | `#ab966f` | links e setas do fluxo |
| `--th` | `#111111` | fundo de cabeçalho de tabela e de selo |
| `--td` | `rgba(45,45,45,.85)`, borda `#333` | células e nós |
| `--table-edge` | `#d9d9d9` 3px | contorno de tabela |
| `--pos` | `#f0b54a` (âmbar) | ganho |
| `--neg` | `#6fa3d8` (azul-aço, oposto do âmbar) | perda ou falta |

- Fontes: títulos, cabeçalhos de tabela e selos em **Marcellus SC** (Google Fonts); corpo em `"Helvetica Neue", Helvetica, Arial, sans-serif`, 14px.
- Só tema escuro, como a wiki (`color-scheme: dark` no `:root`).
- Legenda fixa no topo: âmbar = ganho, azul = perda/falta, dourado = link da wiki.

## Blocos de construção

**Nó** — um elemento do jogo:

```json
{"tipo": "item", "nome": "Ring of Binding", "link": "https://darksouls2.wiki.fextralife.com/Ring+of+Binding",
 "icone": "https://static0.fextralifeimages.com/file/darksouls2/4/46/Ring_of_binding.png", "sub": "entra"}
```

`tipo` ∈ `item, chefe, npc, local, bau, almas, atributo`. `link`, `icone` e `sub` são opcionais. Sem ícone, a página mostra a inicial do nome num quadrado.

**Fluxo** — lista de nós, desenhada com `➜` entre eles.

**Linha** — uma linha de tabela:

```json
{"dado": "PV máx. em Hollow", "agora": "50%", "depois": "75%", "efeito": "+25 p.p.", "sinal": "+"}
```

`sinal` ∈ `"+"` (âmbar), `"-"` (azul), `""` (neutro). Valor sem fonte = `"—"`.

## Formato do `plano.json` v2

```json
{
  "versao": 2,
  "gerado_em": "2026-10-06T19:30",
  "jogo": "Dark Souls II: Scholar of the First Sin",
  "objetivo": "Mago INT + Uchigatana DEX · piro secundária · sem migrar",
  "personagem": {"name": "...", "level": 65, "souls": 0, "soul_memory": 221118,
                  "stats": {"VGR": 9, "...": 0}, "equipado": [Nó]},
  "alvo_stats": {"VGR": 20, "...": 0},
  "mudancas": [Linha],
  "passos": [{"titulo": "Trocar anel", "tipo": "equipar", "fluxo": [Nó], "dados": [Linha]}],
  "fases": [{"nome": "VGR 9 → 20", "atributo": "VGR", "de": 65, "ate": 76, "almas": 82736}],
  "itens": [{"item": Nó, "onde": [Nó], "dados": [Linha], "fonte": "url"}],
  "comparacao": [{"build": "Moonlight Battlemage", "link": "url", "dados": [Linha], "ajuste": [Nó]}],
  "fontes": [{"titulo": "...", "url": "...", "data": "2026-10-06"}]
}
```

- `passos[].tipo` ∈ `nivel, item, chefe, compra, equipar` (vira selo no título).
- Em `mudancas`, `agora` = leitura anterior e `depois` = leitura atual. Lista vazia na primeira leitura.
- Em `comparacao[].dados`, `agora` = você e `depois` = a build comparada; `ajuste` é um fluxo opcional (ex.: `Uchigatana ➜ Moonlight Greatsword`).
- Nenhum campo de texto livre longo: `titulo` ≤ 40 caracteres, `sub` ≤ 30.

## Seções da página (todas no estilo acima)

1. **Ficha** — nome em Marcellus SC; nível, almas em mãos e soul memory em tabela de uma linha; equipado como nós com ícone.
2. **Desde a última vez** — tabela de `mudancas` (Dado | Antes | Agora | Efeito).
3. **Próximos passos** — número + selo do tipo + título, fluxo, tabela (Dado | Agora | Depois | Efeito). Igual ao mockup aprovado.
4. **Atributos** — ícone da wiki de cada atributo, barra 0–99 com o valor atual e marcador do alvo; alvo maior que o atual em âmbar.
5. **Fases de nível** — tabela da wiki: ícone do atributo, Fase | Nível | Custo | Acumulado, com total.
6. **Onde pegar** — por item: nó do item, fluxo `onde` (ex.: The Tower Apart ➜ Baú de ferro ➜ Dull Ember ➜ McDuff) e tabela de dados.
7. **Outras builds** — tabela Você | Build | Diferença e o fluxo de ajuste.
8. **Fontes** — lista com data.

## Ícones

- A página publicada não carrega imagem de outro site, então os ícones são publicados junto com ela.
- `skills/build-page/scripts/prepare_page.py <plano.json> <pasta_saida> --jogo ds2`:
  1. valida o plano;
  2. para cada nó com `icone` em URL `https://`, baixa para `~/.buildsmith/cache/<jogo>/icons/<nome-do-arquivo>` (só se ainda não existir) e troca `icone` por `icons/<nome-do-arquivo>`;
  3. inclui os ícones de atributo e de almas de `games/<jogo>/icons.json` como `icons/stat-<ATR>.png` e `icons/almas.png`;
  4. copia `template/index.html` e grava o `plano.json` final na pasta de saída;
  5. imprime JSON `{"index": caminho, "files": {"plano.json": caminho, "icons/x.png": caminho, ...}}` para usar direto no `files` do Artifact.
- Download que falhar: o nó fica sem ícone (inicial do nome) e o problema aparece em `avisos` na saída; a página ainda é publicada.
- `wiki-cache` passa a gravar `icone: <url>` no cabeçalho de cada arquivo de cache e dados numéricos em vez de frases.

## Testes

- `validate_plano`: exemplo v2 válido; tipo de nó inválido, `sinal` inválido, linha sem `dado` e `versao` diferente de 2 são rejeitados.
- `prepare_page` (download falso injetado): baixa uma vez e reaproveita o cache; reescreve `icone` para `icons/…`; inclui os ícones de atributo; falha de download vira aviso sem quebrar; `files` lista tudo que a página referencia.
- Manual: republicar a página da Melatonina no mesmo link e conferir as 8 seções.
