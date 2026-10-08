# Dados do plano

A página não guarda conteúdo: o JavaScript do template lê `plano.json` (versão 2) e monta tudo. Este é o contrato entre o campo do plano, o componente que ele vira e a aba onde aparece. Os limites vêm de `skills/build-page/scripts/validate_plano.py` (citado como `V:<linha>`); o template é `skills/build-page/template/index.html` (`T:<linha>`); o exemplo completo é `skills/build-page/example/plano.json`.

## Regras gerais

| Regra | Valor | Fonte |
|---|---|---|
| Versão | `versao` = 2 | V:68–69 |
| Campos obrigatórios no topo | `versao`, `gerado_em`, `jogo`, `objetivo`, `personagem`, `alvo_stats`, `mudancas`, `passos`, `fases`, `itens`, `comparacao`, `fontes` | V:24–25 |
| Campos opcionais no topo | `progresso`, `dano`, `agora`, `feiticos` | V:106–113 |
| Uma linha só | nenhum texto do plano tem quebra de linha ou caractere de controle (`[\x00-\x1f\x7f-\x9f  ]`) | V:22, V:153–163 |
| Links | `link`, `fonte` e `url` só `http(s)://`; na página, outra coisa vira texto sem link | V:19, V:136–150; T:257–258 |
| Ícone | `icone` = `https://` (da wiki) ou `icons/<arquivo>`; a página só mostra `^icons/[A-Za-z0-9._-]+$` | V:23, V:143–145; T:264 |
| Ids | `passos[].id` e `itens[].id` são texto único | V:80–81, V:125–133 |
| Fechamento | todo nó `tipo: "item"` citado em passo, dano, ajuste, `agora.faltam` ou feitiço sugerido precisa de entrada em `itens`, salvo `"tem": true` | V:246–266 |
| Valor sem fonte | `"—"` | `skills/build-page/SKILL.md` L16, L25 |

## Nó

Objeto usado em todo fluxo, equipamento, item, chefe, loja, arma e feitiço. Vira `.node` (T:273–277).

| Campo | Regra | Vira |
|---|---|---|
| `tipo` | um de `item`, `chefe`, `inimigo`, `npc`, `local`, `bau`, `almas`, `atributo` (V:15, V:32–33) | nada visível; só validação e fechamento |
| `nome` | obrigatório (V:34–35); sem limite de tamanho | `.nm`, peso 500; inicial em `.ini` quando falta ícone |
| `sub` | opcional, até 30 caracteres (V:36–37) | `.sub`, 12px, segunda linha; sem `sub` o nó é `.solo` |
| `link` | opcional, http(s) | com link: `<a class="node">` em `link`; sem: `<span class="node">` em `head` |
| `icone` | opcional | `img.ic` em `icon-node` (40px) ou `icon-node-table` (28px) dentro de tabela |
| `tem` | opcional, `true` se o jogador já tem | nada visível; libera o fechamento |

## Linha de dados

Objeto das tabelas Dado | Agora | Depois | Efeito, montadas por `rows()` (T:280–284).

| Campo | Regra | Vira |
|---|---|---|
| `dado` | obrigatório (V:53–54) | 1ª coluna |
| `agora` | texto já formatado | 2ª coluna |
| `depois` | texto já formatado | 3ª coluna |
| `efeito` | texto já formatado | 4ª coluna, com a cor do sinal |
| `sinal` | `"+"`, `"-"` ou `""` (V:16, V:55–56) | `td.pos` (`pos`), `td.neg` (`neg`) ou neutro (`head`) |

A página só escapa esse texto: o plano escreve "2.500", "+12,5%", "−1.320" já no formato pt-BR.

## Cabeçalho (fora das abas)

| Campo | Componente | Detalhe |
|---|---|---|
| `jogo` + `gerado_em` | `.meta` | "Dark Souls II: Scholar of the First Sin · atualizado 06/10/2026, 17:26"; data com `toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" })`, texto cru se a data for inválida (T:260, T:289) |
| `personagem.name` | `h1` | 1 a 32 caracteres (V:20, V:117–119) |
| `agora.acoes` | `.agora` > `.agora-acao` | até 3 ids de passo que existam (V:187–192); cada um vira fogueira + título-link + fluxo do passo (T:426–439). O template não corta: o limite é do validador |
| `agora.almas` | `.agora-resumo` | inteiro (V:193–194); "Almas pra essas ações: N" em `.neg` |
| `agora.faltam` | `.agora-resumo` | lista de nós; "Faltam:" + fluxo, só se tiver itens |

Sem `agora`, o painel não existe.

## Abas

| Aba | Contador na aba | Campo | Componente | Limites |
|---|---|---|---|---|
| Ficha | `mudancas.length` (sem número se 0) | `personagem.level`, `souls`, `soul_memory` | tabela Nível · Almas em mãos · Soul memory · Objetivo, números com `Intl` pt-BR (T:300–307) | `personagem` precisa de `name`, `level`, `souls`, `soul_memory`, `stats`, `equipado` (V:71–73) |
| Ficha | | `objetivo` | 4ª coluna da mesma tabela | texto |
| Ficha | | `personagem.equipado` | `.equipped`: nós de 40px fora de tabela | lista de nós (V:74) |
| Ficha | | `mudancas` | "Desde a última vez": tabela Dado · Antes · Agora · Efeito; `agora` é a leitura anterior, `depois` a atual (T:309–311) | lista de linhas (V:79); vazia mostra "Primeira leitura do save." |
| Passos | `passos.length` | `passos[]` | grupos `.grupo` na ordem Equipar, Explorar, Chefes, Trocas de alma, Compras, Upgrades, Farms, Nível; cada passo `.step` com fogueira, número, título, fluxo e tabela Dado · Agora · Depois · Efeito (T:313–324) | `titulo` até 40 (V:83–86); `tipo` um dos 8 grupos (V:9, V:87–88); `fluxo` lista de nós; `dados` lista de linhas |
| Progresso | chefes derrotados | `progresso.chefes[]` | tabela Chefe · Estado: nó + selo Derrotado (`.feito`) ou Vivo; título "Chefes · N de M derrotados" (T:400–412) | `estado` em `derrotado`, `vivo` (V:17, V:273–276) |
| Progresso | | `progresso.compras[]` | tabela Loja · Item · Qtd (Qtd à direita) | `loja` e `item` nós, `qtd` inteiro (V:277–281) |
| Progresso | | `progresso.eventos[]` | tabela Evento · Estado: selo Feito (`.feito`) ou Pendente | `nome` e `estado` em `feito`, `pendente` (V:18, V:282–286) |
| Dano | `dano.length` (sem número se 0) | `dano[]` | tabela Arma · Agora · Depois · Diferença · Mudança · Por causa de; colunas 2 a 4 à direita; Diferença calculada pela página, com "+" e `.pos`/`.neg` (T:414–424) | `arma` nó; `agora` e `depois` inteiro ou `"—"` (V:289–299); `detalhe` texto; `por_causa` fluxo |
| Feitiços | `feiticos.lista.length` | `feiticos.catalisador`, `feiticos.ar` | `.block-head`: nó + "AR do catalisador: magico 190 · sombrio 166" (a chave sai como está no JSON) (T:441–460) | `catalisador` nó (V:202) |
| Feitiços | | `feiticos.slots.total` | `.slots`: "Slots selecionados: N de total" | inteiro (V:203–204) |
| Feitiços | | `feiticos.lista[]` | tabela com fogueira · Feitiço · Estado · Elemento · AR · Usos · Slots · Requisito; AR, Usos e Slots à direita | `no` nó; `estado` em `equipado`, `tem`, `sugerido` (V:14, V:208–209); `ar` inteiro ou `"—"`; `usos`, `slots` inteiros; `requisito_ok` booleano (V:205–216). `requisito_ok: false` pinta o requisito de `neg` |
| Atributos | sem contador | `personagem.stats`, `alvo_stats` | `.stats` > `.stat`: ícone, sigla, barra 0 a 99 (`link`), marca do alvo (`pos`), valor (T:326–338) | os 9 atributos `VGR END VIT ATN STR DEX INT FTH ADP` como inteiros (V:7, V:75–78) |
| Fases | `fases.length` | `fases[]` | tabela Fase · Nível · Custo (almas) · Acumulado, custo em `.neg`, rodapé "Total até o nível N" em Marcellus (T:340–353) | `de`, `ate`, `almas` inteiros; `atributo` um dos 9 (V:91–96) |
| Onde pegar | `itens.length` | `itens[].item` | `.block` com o nó do item e o link "fonte" (`it.fonte`) em `.muted` (T:355–380) | `item` nó (V:98) |
| Onde pegar | | `itens[].fontes[]` | tabela # · Como · Requisito · Acesso · Rendimento · Destaque; as fontes sem destaque vão para `details.mais` "Ver todas as fontes (N)" | pelo menos 1 fonte (V:220–221); `tipo` em `compra`, `troca`, `drop`, `bau`, `farm`, `recompensa` (não aparece); `acesso` em `agora`, `em_breve`, `tarde`, nessa ordem (V:228–229, V:241–243); `fluxo` não vazio (V:230–232); `destaques` em `mais_cedo`, `mais_rentavel`: exatamente 1 `mais_cedo` e no máximo 1 `mais_rentavel` por item (V:233–240) |
| Onde pegar | | `fontes[].requisito` | texto + botão `.pesq` "Pesquisar"; `{texto, item}` vira `.req-link` para o item; ausente vira "—" (T:248–253) | até 80 caracteres (V:21, V:172–173); `item` precisa existir em `itens` (V:177–178) |
| Onde pegar | | `fontes[].acesso` | selo Agora (`.feito`), Em breve (neutro), Tarde (`.apagado`) | |
| Onde pegar | | `fontes[].rendimento` | texto; vazio vira "—" | |
| Onde pegar | | `itens[].dados` | tabela Dado · Agora · Com o item · Efeito | lista de linhas (V:100) |
| Builds | `comparacao.length` | `comparacao[]` | `.block`: nome da build em `titulo-passo` (link se `link`), tabela Dado · Você · Build · Diferença, rótulo "Ajuste sugerido" + fluxo (T:382–389) | `build` obrigatório; `dados` linhas; `ajuste` fluxo (V:101–105) |
| Fila | pedidos abertos | nada do plano | formulário e lista de pedidos do banco (T:462–471) | campo com `maxlength="120"` (T:466); texto limpo por `limpaPedido` até 120 caracteres e origem até 80 (T:742–745, T:763); servidor aceita texto até 160 e no máximo 50 pedidos abertos (`app/serve.py` L40–L41) |
| Fontes | `fontes.length` | `fontes[]` | `ul.sources`: título (link se `url`) + " · data" em `.muted`; a data sai como está (T:473–475) | lista (V:24–25); `url` vazio ou http(s) |

## Campos que a página não lê

- `passos[].tipo` só agrupa; `itens[].fontes[].tipo` e `nó.tipo` só validam.
- `feiticos.slots.faixa` existe no exemplo e o template não usa.
- `nó.tem` só serve ao fechamento.

## Estado que não vem do plano

A página grava e lê três coleções no banco (Artifact ou servidor local): `feitos/<id do passo>` (`marcado`, `em`, `confirmado`), `pedidos/<slug>` (`texto`, `origem`, `estado` `na_fila` ou `respondido`, `criado_em`, `item_id`) e `config/feiticos` (`selecionados`). Sem banco, fogueiras ficam ocultas e Pesquisar copia o comando.
