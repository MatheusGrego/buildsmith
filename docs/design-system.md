# Design system do buildsmith (estilo wiki do DS2)

Base: a wiki do Dark Souls II (Fextralife) e a interface do jogo. Tudo em `skills/build-page/template/index.html`.

## Regras

1. **Dados, não frases.** Passo = fluxo de nós + tabela. Texto corrido só em mensagem de erro e na resposta da forja.
2. **Cor tem significado fixo.** Âmbar = ganho, azul-aço = perda ou falta, dourado = link e "feito". Nada de verde, nada de check.
3. **Feito = fogo aceso.** Estado concluído é a fogueira acesa ou a borda dourada. Pendente é cinza/apagado.
4. **Movimento só com função.** Brasa na etapa atual, linha nova surgindo, faixa de aviso. Tudo desliga com `prefers-reduced-motion`.
5. **Celular primeiro.** Gutter de 16px, nada de rolagem horizontal da página (tabelas rolam dentro de `.tw`).

## Tokens (`:root`)

| Token | Valor | Uso |
|---|---|---|
| `--bg` | `#101013` | fundo da página |
| `--panel` | `#181818` | painel principal, menu |
| `--th` | `#111111` | cabeçalho de tabela, caixas (Agora, Forja, selos) |
| `--td` | `rgba(45,45,45,.85)` | célula, nó |
| `--line` | `#333333` | bordas finas |
| `--edge` | `#d9d9d9` | borda grossa da tabela wiki |
| `--track` | `#2b2b2b` | trilho de barra vazia |
| `--text` | `#b4b2b0` | texto comum |
| `--head` | `#ffffff` | títulos, valores |
| `--dim` | `#8a8885` | apagado, tempo, rótulo pendente (v2: passa 4,5:1) |
| `--link` | `#ab966f` | link, feito, etapa concluída |
| `--pos` | `#f0b54a` | ganho, destaque |
| `--neg` | `#6fa3d8` | perda, falta, erro |
| `--ember` / `--ember-deep` / `--ember-glow` | `#f0a03c` / `#7a3d12` / `rgba(240,160,60,.55)` | brasa: etapa atual, fogueira acesa |
| `--band` | `rgba(0,0,0,.78)` | faixa de aviso |

## Tipografia

- `--display`: **Marcellus SC** (Google Fonts), fallback Palatino/Georgia. Títulos, abas, cabeçalho de tabela, selos, botões, rótulos de etapa.
- `--body`: Helvetica Neue/Arial. Valores, células, microtexto. Números com `tabular-nums`.

## Componentes

| Componente | Classe | Quando usar |
|---|---|---|
| Nó | `.node` (`.ic` ícone 40px ou `.ini` inicial) | item, chefe, NPC, local; link da wiki em dourado |
| Fluxo | `.flow` + `.arrow` (➞) | sequência de nós de um passo ou fonte |
| Tabela wiki | `.tw > table` | dados; borda `--edge` 3px, cabeçalho Marcellus |
| Selo | `.estado` (`.feito`, `.destaque`, `.apagado`) | estado curto: Derrotado, Agora, Mais cedo |
| Fogueira | `.fogueira[aria-pressed]` | marcar feito / selecionar feitiço |
| Pesquisar | `.pesq` | ação pequena em linha (Pesquisar, Cancelar, Fechar) |
| Ação | `.acao` | ação grande de menu: faixa dourada à esquerda + fogueira que acende no hover |
| Forja | `.forja` | progresso da skill rodando sem janela |
| Barra de etapas | `.etapas > .etapa` (`.feita`, `.atual`, `.pulada`) | segmentos; atual = brasa animada |
| Microtexto | `.microtexto > .linha-<tipo>` | 6 linhas rolando: `acao` (›), `texto`, `pensamento` (itálico), `etapa` (Marcellus âmbar), `erro` |
| Faixa | `.faixa` | aviso de fim no estilo "BONFIRE LIT": texto dourado sobre faixa escura, some em 2,8 s |
| Cabeçalho | `.topo` (`.retrato`, `.topo-meta`, `.acoes`) | retrato 56×72 (foto, ou `.mosaico` 2×2 com o equipamento), nome, Trocar personagem, nível/almas/soul memory |
| Menu lateral | `.menu > .menu-g > .menu-i[aria-current]` | uma seção por vez, agrupada (Plano · Coletar · Combate · Registro); vira faixa horizontal abaixo de 760px |
| Lista + detalhe | `.md` (`.md-lista > .md-i[aria-current]`, `.md-det > .md-pane`) | Passos e Onde pegar; empilha abaixo de 1180px |
| Fonte | `.fonte-v[aria-current]` | uma fonte de item, clicável (escolhe a rota do mapa) |
| Nó em linha | `.ni` (`.ni-ic` 20px) + `.fi` | nó dentro de lista, fonte e Agora |
| Dano em barras | `.dano-l` (`.dano-bar .now/.ganho`) | AR agora → depois; ganho em âmbar |
| Seleção | `.sel-fundo > .sel` (`.sel-c[aria-current]`, `.sel-ret`) | diálogo de personagens do save; Esc fecha |
| Mapa | `.mp` (`.mp-tela`, `.mp-andar.mp-atual/.mp-baixo`, `.mp-item.mp-do-plano`, `.mp-fog`, `.mp-rota`, `.mp-passo`, `.mp-andares`, `.mp-filtro[aria-pressed]`, `.mp-regua`, `.mp-pop`) | vista de cima: andar escolhido sólido com parede clara, andares de baixo apagados, grade 10/50 m, régua, ícones com moldura (âmbar = item do plano), fogueira com nome, rota tracejada `--ember` com passos numerados; seletor de andar à direita (chips no celular); legenda com "rota pelo chão; portas e alavancas não aparecem" |
| Agora | `.agora2` | até 3 ações imediatas |

## Textos da forja

| Estado | Título |
|---|---|
| rodando | Forjando o plano / Respondendo a fila |
| ok | Plano forjado / Fila respondida (+ faixa) |
| erro | A forja apagou |
| cancelado | Cancelado |
