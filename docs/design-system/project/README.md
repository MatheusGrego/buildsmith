A Forja de Build é a página do plano de build do buildsmith para Dark Souls II: Scholar of the First Sin. O jogador abre a página entre uma sessão e outra para ver o que fazer agora, onde pegar cada item e quanto cada mudança rende. O visual imita a wiki Fextralife do DS2: painel escuro, tabelas com contorno claro, títulos em Marcellus SC, links em dourado. Do jogo vêm dois sinais: a fogueira acesa marca o que está feito e a brasa marca o que está rodando. A página é uma coluna só, em tema escuro, montada por JavaScript a partir de um `plano.json`.

## Princípios

### 1. Dados, não frases

Todo passo é um fluxo de nós (`.flow` com `.node`) mais uma tabela Dado | Agora | Depois | Efeito. Texto corrido só aparece em mensagem de erro (`.error`, `.forja-msg`) e na resposta da Forja.

- Faça: o passo "Trocar anel" com o fluxo Old Leo Ring (sai) ➞ Ring of Binding (entra) e a linha "PV máx. em Hollow · 50% · 75% · +25 p.p.".
- Não faça: um parágrafo explicando por que vale trocar o anel.

### 2. Cor tem significado fixo

`pos` é ganho, `neg` é perda ou falta, `link` é link da wiki e feito. A legenda do cabeçalho (`.legend`) escreve isso na página: "ganho", "perda / falta", "link da wiki". Nada de verde, nada de check.

- Faça: "faltam 2.500" em `.neg` na coluna Efeito; "+13" em `.pos` na Diferença da aba Dano.
- Não faça: pintar um título de `pos` para enfeitar, ou usar verde para "ok".

### 3. Feito = fogo aceso

Concluído é a fogueira acesa (`.fogueira[aria-pressed="true"]`: borda `pos` e brilho `fogueira-glow`) ou a borda dourada do selo (`.estado.feito`: borda `link`, texto `head`). Pendente é cinza: a fogueira apagada leva `filter: grayscale(1) brightness(0.55)` e o selo neutro fica em `text` sobre `th`.

- Faça: chefe derrotado como o selo "Derrotado" em `.estado.feito`; passo feito como a fogueira acesa ao lado do número.
- Não faça: ícone de check, texto riscado ou linha verde.

### 4. Movimento só com função

Há três animações, cada uma com um trabalho: `brasa` mostra a etapa que está rodando, `surge` mostra a linha nova do microtexto, `acende` mostra a faixa de fim. Tudo desliga com `prefers-reduced-motion: reduce`.

- Faça: animar o segmento `.etapa.atual` enquanto a skill roda.
- Não faça: animar troca de aba, hover de linha de tabela ou contador.

### 5. Celular primeiro

Margem lateral `gutter` (16px) e nenhuma rolagem horizontal da página. Tabela larga rola dentro do próprio `.tw`. Fluxo e cabeçalho quebram linha com `flex-wrap`.

- Faça: envolver toda `table` em `.tw`; deixar o fluxo quebrar em várias linhas.
- Não faça: largura fixa maior que a tela, ou tabela fora de `.tw`.

## Voz e conteúdo

- Escreva em português do Brasil. Termos do jogo ficam em inglês, como no jogo e na wiki: Soul memory, AR, Estus Flask, Hollow, Large Titanite Shard, Bonfire Ascetic. Nome de item, chefe, NPC e área nunca é traduzido.
- Use as siglas de atributo do jogo: VGR, END, VIT, ATN, STR, DEX, INT, FTH, ADP. Não misture com FOR ou DES.
- Formate número com `Intl.NumberFormat("pt-BR")`: milhar com ponto (221.118), decimal com vírgula (12,5%). Texto escrito no plano segue o mesmo padrão ("2.500 almas", "+12,5%"). O sinal de menos escrito é "−" (U+2212).
- Dado sem fonte é "—". Nunca complete com o que "deve ser".
- Prefira dado a frase. Título de passo tem até 40 caracteres ("Queimar Sublime Bone Dust"); a segunda linha do nó tem até 30 ("R1 · +5", "×1", "2.500 almas", "sai", "entra", "Lost Bastille").
- Separe campos no mesmo texto com "·", transição com "→" ("VGR 9 → 20", "nível 65 → 76") e quantidade com "×". A seta "➞" (`.arrow`) só aparece entre nós de um fluxo.
- Rótulos são curtos e diretos. Abas: Ficha, Passos, Progresso, Dano, Feitiços, Atributos, Fases, Onde pegar, Builds, Fila, Fontes. Botões: Atualizar plano, Responder fila, Pesquisar, Cancelar, Tentar de novo, Fechar. Selos: Agora, Em breve, Tarde, Mais cedo, Mais rentável, Equipado, Tem, Sugerido, Derrotado, Vivo, Feito, Pendente, Na fila, Respondido.
- Estado vazio é uma frase curta com ponto final, em `.empty`: "Primeira leitura do save.", "Nenhum passo pendente.", "Este plano não tem cálculo de dano.".
- Títulos da Forja: Forjando o plano, Plano forjado, Respondendo a fila, Fila respondida, A forja apagou, Cancelado.
- Escreva em caixa normal ("Plano forjado"). A Marcellus SC já desenha versalete; não use `text-transform`.
- Sem exclamação, sem emoji, voz ativa.

## Fundações visuais

### Cor

| Papel | Token | Valor |
|---|---|---|
| Fundo da página | `bg` | #101013 |
| Painel único e barra de abas | `panel` | #181818 |
| Cabeçalho de tabela, caixas, selos, botões | `th` | #111111 |
| Célula e nó (translúcido) | `td` | rgba(45, 45, 45, 0.85) |
| Borda fina | `line` | #333333 |
| Contorno da tabela | `edge` | #d9d9d9 |
| Título e valor | `head` | #ffffff |
| Texto comum | `text` | #b4b2b0 |
| Apagado | `dim` | #7a7875 |
| Link da wiki e feito | `link` | #ab966f |
| Ganho e destaque | `pos` | #f0b54a |
| Perda, falta e erro | `neg` | #6fa3d8 |
| Trilho vazio | `track` | #2b2b2b |
| Brasa | `ember`, `ember-deep`, `ember-core`, `ember-glow`, `fogueira-glow` | #f0a03c, #7a3d12, #ffd27a, rgba(240, 160, 60, 0.55), rgba(240, 160, 60, 0.75) |
| Faixa de aviso | `band`, `faixa-text`, `faixa-glow` | rgba(0, 0, 0, 0.78), #e9d3a0, rgba(240, 180, 74, 0.55) |
| Degradê da ação | `acao-tint` | rgba(171, 150, 111, 0.16) |

- Empilhe as superfícies assim: `bg` (página), `panel` (painel), `th` ou `td` por cima. `th` é mais escuro que `panel`: as caixas `.agora` e `.forja` se separam pela borda `line`, não pelo tom.
- Ponha título e valor em `head` e o resto em `text`. `.muted` é `text` em 13px, não um cinza mais fraco.
- Guarde `dim` para o que está apagado de propósito: selo Tarde, etapa pendente, tempo e pensamento do microtexto, ação desativada. Ele falha 4.5:1 (ver Acessibilidade).
- `pos` também marca destaque (Mais cedo, Mais rentável, Sugerido), a borda da fogueira acesa e o "confirmado pelo save". `link` também marca feito (selo, etapa, aba ativa).
- Use a família brasa só em coisa acesa ou rodando: etapa atual, fogueira acesa, hover da `.acao`. `band`, `faixa-text` e `faixa-glow` são só da faixa de aviso. `edge` é só o contorno da tabela.
- Não use cor fora dos tokens.

### Tipografia

- `display` (Marcellus SC, só peso 400, do Google Fonts) vai em tudo que é título ou rótulo: `titulo-pagina` (`h1`), `titulo-secao` (`h2`), `titulo-grupo` (`.grupo h3`), `titulo-passo`, `cabecalho-tabela` (`th`), `aba` (`.tab`, `.acao`), `selo` (`.estado`, `.label`), `botao-pequeno` (`.pesq`), `botao-fila`, `rodape-tabela` (`tfoot td`), `inicial-no` e `faixa-aviso`.
- `body` (Helvetica Neue, Helvetica, Arial, do sistema) vai em valor e leitura: `corpo` (14px/1.6, `body` e `td`), `nome-no` (peso 500), `legenda-no` (`.node .sub`, 12px), `pequeno` (13px/1.6), `contador` (`.count`), `texto-log` (microtexto, 12px/1.55).
- Alinhe número em coluna à direita com `.r` e use `font-variant-numeric: tabular-nums` (já está em `td`, `.stat .val`, `.forja-tempo`, `.linha .t`).
- Ganho e perda (`.pos`, `.neg`) sobem o peso para 500 sobre o tamanho herdado.
- `h1` e `h2` usam `clamp()` e `text-wrap: balance`: `h1` vai de 28px a 40px, `h2` de 22px a 30px, a faixa de 24px a 46px. Os estilos guardam o máximo.
- Itálico só em `vazio` (`.empty`) e `pensamento-log` (`.linha-pensamento`).
- O atalho `font:` deixa quase todo texto `display` com `line-height: normal`; o texto `body` fica em 1.6 ou 1.55.

### Espaçamento e layout

- Coluna única: `.page` com largura máxima `page-max-width` (64rem), `gutter` (16px) nas laterais, `page-pad-top` (24px) e `page-pad-bottom` (48px).
- Painel único: `.panel` com fundo `panel`, borda `border-hair` em `line`, raio `radius-panel`, padding `panel-pad-top` (20px), `panel-pad-x` (`clamp(14px, 3vw, 28px)`) e `panel-pad-bottom` (28px).
- Ritmo vertical, do maior para o menor: `panel-gap` 34px (cabeçalho, Agora, abas, painel da aba), `tab-panel-gap` 28px (seções da mesma aba), `section-gap` 14px (título e conteúdo), `header-gap` 12px, passo (`step-gap` 12px e `step-pad-y` 18px), bloco (`block-gap` 10px e `block-pad-y` 16px), `group-gap` 4px.
- Célula de tabela: `cell-pad-y` 6px e `cell-pad-x` 10px. Nó: `node-pad` 6px, `node-pad-right` 12px, `node-icon-gap` 10px. Dentro de `td` o nó fica compacto: `node-pad-table` 2px, `icon-node-table` 28px, sem fundo e sem borda.
- A escala não é de 4 nem de 8: 6, 8 e 10px dominam. Use o token do papel. Não arredonde.
- Um breakpoint só, `breakpoint-narrow` (560px): abaixo dele `.etapa .rotulo` some. O resto responde com `clamp()`, `auto-fill` (`.stats`, coluna mínima `stats-col-min`), `flex-wrap` e rolagem dentro de `.tw`.
- Toda tabela tem `min-width` `table-min-width` (30rem) e fica dentro de `.tw` (`overflow-x: auto`): a tabela rola, a página não.
- A barra `.tabs` gruda no topo (`position: sticky`, `z-tabs`) e encosta nas bordas do painel com margem negativa igual a `panel-pad-x`. Uma aba aparece por vez.

### Bordas e raio

- Só o painel tem raio (`radius-panel`, 12px). Nó, selo, botão, tabela e as caixas Agora e Forja têm canto reto, como na wiki.
- Tabela wiki: contorno `border-table` (3px) em `edge`, célula com `border-hair` em `line`, `th` sem borda própria.
- Divisória: `border-hair` em `line` no topo de `.step` e `.block` (o primeiro da lista não tem) e embaixo do `h2`.
- Borda colorida marca estado: `link` no selo feito, na aba ativa (`border-tab`, 2px), na etapa feita e no hover da `.acao`; `pos` no selo destaque e na fogueira acesa; `neg` no `.error`.
- Não há sombra de elevação. Todo brilho é brasa com deslocamento 0 0: `drop-shadow(0 0 5px)` em `fogueira-glow` ou `ember-glow`, `box-shadow: 0 0 8px` em `ember-glow`, `text-shadow: 0 0 18px` em `faixa-glow`.

### Movimento

| Efeito | Onde | Duração e curva | O que faz |
|---|---|---|---|
| `brasa` | `.etapa.atual .seg` | 1.6s linear infinite | Degradê `ember-deep`, `ember`, `ember-core`, `ember`, `ember-deep` com `background-size: 200% 100%` corre de `background-position: 200% 0` até `0 0`. |
| `surge` | `.linha.nova` | 0.35s ease-out | A linha nova entra de `opacity: 0` e `translateY(6px)`. |
| `acende` | `.faixa span` | 2.8s ease-out both | Opacidade 0 até 1 em 20%, fica até 75%, some em 100%; `letter-spacing` vai de 0.3em a 0.18em. O JS esconde a faixa em 2900ms. |
| Filtro | `.fogueira img`, `.acao img` | 0.2s ease-out | A fogueira acende ou apaga sem salto. |

Com `prefers-reduced-motion: reduce`, as três animações e as duas transições viram `none`. Movimento não tem token: os valores ficam no CSS.

## Iconografia

- Ícones são PNG da wiki Fextralife. O `skills/build-page/scripts/prepare_page.py` baixa cada um (só `https`, só de `fextralifeimages.com` ou `fextralife.com`) para `icons/` ao lado da página. A página só aceita `icons/<arquivo>` (regex `^icons\/[A-Za-z0-9._-]+$`); um ícone com URL externa vira inicial. Nunca carregue ícone de fora: o pedido avisaria um terceiro de que a página abriu.
- Tamanhos: `icon-node` 40px (nó), `icon-node-table` 28px (nó em tabela), `icon-stat` 26px (atributo), `icon-fogueira` 24px (dentro do botão de `fogueira-size`, 34px), `icon-small` 22px (célula com ícone e `.acao`). Sempre `object-fit: contain`.
- Ícones fixos de toda página do DS2, de `games/ds2/icons.json`: `icons/fogueira.png` (fogueira e `.acao`), `icons/almas.png` (coluna Nível da Ficha), `icons/stat-<ATR>.png` (Atributos e Fases).
- Sem ícone, ou se a imagem falha, o nó mostra a inicial do nome em `.ini`: Marcellus 20px (`inicial-no`) em `head` sobre `th`, 15px dentro de tabela, sem o "The " do começo ("The Tower Apart" vira "T"), com `aria-hidden`. Ícone de atributo que falha fica invisível e guarda o espaço; ícone da Ficha e das Fases que falha some.
- Imagem é decorativa (`alt=""`): o nome está sempre escrito ao lado.
- Glifos de texto: a seta ➞ (U+279E, `seta`) em `link`, o quadrado "■ " da legenda e o "› " da linha de ação do microtexto.
- Os arquivos de ícone não estão neste sistema. São imagens de terceiros (Fextralife) e cada plano baixa os seus. Por isso os previews mostram a inicial.

## Estados

Cada componente troca de estado por classe ou atributo ARIA, nunca por estilo inline:

- Selo `.estado`: neutro, `.feito` (borda `link`), `.destaque` (borda e texto `pos`), `.apagado` (texto `dim`).
- Fogueira: `[hidden]` sem banco, apagada, hover, acesa com `aria-pressed="true"`, `:disabled` enquanto grava.
- Aba: `aria-selected="true"` com borda inferior `link`.
- Etapa da Forja: pendente, `.feita`, `.pulada` (listra), `.atual` (brasa e `aria-current="step"`).
- Ação, Pesquisar, linhas do microtexto, Forja, vazio, erro e carregando têm a matriz completa na seção [Estados](estados.md).

## Acessibilidade

- Foco: anel `focus-width` (2px) `solid` em `link` com `focus-offset` (2px) em `a`, `.fogueira`, `.pesq` e `.acao`. A `.tab` usa offset -2px porque a barra rola; o campo da fila usa 1px. `link` dá 6.19:1 sobre `panel`, 6.59:1 sobre `th` e 5.01:1 sobre célula. A exceção é o `.microtexto`: 1px em `line` (`focus-width-log`), só 1.49:1.
- Contraste de texto (WCAG 2, 4.5:1):

| Texto | Fundo | Razão | Resultado |
|---|---|---|---|
| `head` | `panel` / `th` / célula #2a2a2a | 17.76 / 18.88 / 14.35 | passa |
| `text` | `panel` / `th` / célula | 8.40 / 8.93 / 6.79 | passa |
| `link` | `panel` / `th` / célula | 6.19 / 6.59 / 5.01 | passa |
| `pos` | `panel` / `th` / célula | 9.65 / 10.26 / 7.80 | passa |
| `neg` | `panel` / `th` / célula | 6.69 / 7.11 / 5.40 | passa |
| `ember` | `th` | 8.81 | passa |
| `faixa-text` | `band` sobre `panel` / sobre título branco | 13.87 / 7.98 | passa |
| `dim` | `th` | 4.29 | FALHA: selo Tarde (13px), rótulo de etapa (11px), tempo e pensamento do log (12px) |
| `dim` | `panel` / célula | 4.03 / 3.26 | FALHA (par não usado hoje) |

- Contraste de borda e marca (3:1): `edge` 12.58:1 sobre `panel` passa; `line` 1.41:1 é decorativa e nunca é o único sinal; o campo da fila falha (borda 1.41:1, fundo 1.24:1); `track` 1.25:1 é o vazio, e o valor e o alvo da barra passam (4.94:1 e 7.70:1 sobre `track`).
- Cor nunca vai sozinha. A Diferença do Dano leva "+"; o efeito traz a palavra ("faltam 2.500", "economia 16.840", "ok"); a legenda nomeia cada cor; a etapa pulada tem listra; o selo tem texto. `pos` e `neg` são âmbar e azul, fora do eixo vermelho-verde, mas a diferença de luminância entre eles é só 1.44:1: mantenha o sinal e a palavra.
- Estado vai no ARIA: `aria-pressed` na fogueira, `role="tab"` e `aria-selected` na aba, `aria-current="step"` na etapa atual, `role="img"` com `aria-label` na barra de atributo ("VGR: 9 de 99, alvo 20"), `role="log"` no microtexto, `aria-live="polite"` no cabeçalho da Forja.
- Esconda o decorativo: seta e inicial com `aria-hidden="true"`, imagens com `alt=""`. Rótulo só para leitor de tela usa `.sr-only`.

## Componentes que parecem clichê, mas imitam o jogo

- `.acao`: borda esquerda de 2px em `link` (`border-acao`) e degradê de `acao-tint` até `th` em 75%. É o botão de menu do DS2: faixa dourada à esquerda e uma fogueira apagada que acende no hover. É intencional. Não remova a borda esquerda nem o degradê sem decidir de novo.
- `.faixa`: texto dourado centralizado, letras espaçadas, numa faixa escura que some nas pontas. Imita o aviso "BONFIRE LIT" do jogo. É intencional; a cor foi suposta e não conferida (ver [Wiki e fidelidade](wiki-fidelidade.md)).
- `.fogueira` no lugar do checkbox: é o princípio 3. Não troque por check.
- Brasa animada contínua (`brasa`): é a única animação sem fim, e só existe enquanto a skill roda.
- Ouro sobre preto e tabela com contorno claro de 3px: é a wiki Fextralife, não decoração.

## Não sincronizado

Ficaram fora deste sistema: os ícones da wiki Fextralife (imagens de terceiros, baixadas por plano para `icons/`); a fonte do jogo (desconhecida, sem arquivo); o arquivo da Marcellus SC (vem do Google Fonts, `type.fonts` vazio); a página inicial do servidor (`app/serve.py`), que não usa estes tokens. Os previews são estáticos, sem `components/bundle.js`: a página real é montada por JavaScript a partir do `plano.json`. No CSS continuam literais `transparent` (o formato não aceita cor por nome), o `560px` da media query, o `calc(6 * 1.55em)` do microtexto e os números que aparecem com papéis diferentes.
