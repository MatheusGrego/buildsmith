# buildsmith — companion com ≥ 90% sem IA

Data: 2026-10-11
Status: proposta (pedido: "antes de documentar a final, pensar em como tirar a dependência de IA em pelo menos 90%")

## Por quê

Hoje quase tudo que o jogador vê **depende de um plano escrito pelo Claude** (`/buildsmith:build`, ou o botão
Atualizar plano, que roda `claude -p`): a lista de itens, o "onde pegar" de cada um, os passos, as rotas. Sem o `claude`
instalado e logado, o executável abre só o que é lido do save e do jogo. Isso trava quem baixa o `Buildsmith.exe`, custa
tokens a cada atualização e faz o jogador esperar minutos por coisas que o jogo já responde.

A meta: o companion funcionar inteiro sem IA. A IA fica só para o que é **opinião** (qual build seguir e por quê).

## O que já roda sem IA (base)

| Parte | Fonte | Onde |
|---|---|---|
| Personagem ao vivo: nível, almas, atributos, inventário, equipado, chefes, fogueiras | save | `ds2save`, `vivo.js` |
| Equipamento atual, AR, escala, sintonia | save + params + escala da wiki (cache) | `ds2equip`, `ds2calc` |
| Mapa 2D/3D com cenário, itens, inimigos (pose de espera), NPCs, portas, chaves, rota | arquivos do jogo | `ds2mapa`, `ds2cena`, `ds2anim`, `ds2esd` |
| Estado do mundo: porta aberta, baú aberto, item já pego | save | `ds2save.estado_mundo` |
| Quem vende cada item, preço, estoque; troca de alma de chefe | `ShopLineupParam`, `lojas.json` | `ds2data onde-comprar`, `trocas` |
| Todo item no chão, baú ou cadáver, por área | `ItemLotParam2_Other` + MSB | `ds2mapa onde` |
| Drop de inimigo (quais itens) | `EnemyParam` + `ItemLotParam2_Chr` | `ds2mapa.tipos_inimigo` |
| Melhor perto (arma, catalisador, armadura, feitiço) com AR nos atributos atuais | params + mapas | `ds2perto` |

## O que a IA faz hoje e quem passa a fazer

| Hoje (IA) | Proposta | IA? |
|---|---|---|
| Escolher quais itens entram em "Onde pegar" | **Catálogo** na página: o jogador marca o que quer (armas, escudos, catalisadores, feitiços, milagres, hexes, piromancias, armaduras, anéis) | não |
| Montar as fontes de cada item (loja, troca, chão/baú, drop) | **Fontes por código** juntando `ds2data` + `ds2mapa onde` + drops, com o NPC/chefe/área de cada uma | não |
| Ordenar agora / em breve / tarde, "mais cedo", "mais rentável" | **Regras**: área liberada pelas fogueiras do save → agora; próxima na rota de progressão (`rota.json`) → em breve; resto → tarde. Mais cedo = a primeira fonte em área liberada mais perto da fogueira acesa; mais rentável = loja de estoque ilimitado ou drop repetível | não |
| Fluxo do passo (fogueira → caminho → item) e ponto no mapa | **Rota pelo chão** da fogueira acesa mais perto até o ponto do item, com portas e chaves (Tasks 4–6) | não |
| Requisito do item × atributos atuais, almas para chegar | `ds2calc` + `level_costs.json`: "faltam 6 INT: 4 níveis, 23.410 almas" | não |
| Passos "equipar", "upar", "comprar", "trocar" para os itens marcados | Gerados dos itens marcados + estado do save (o que falta e onde) | não |
| Condições que só a wiki diz (libertar o Straid antes, questline do Benhart, drop raro) | Continuam com a fonte da wiki, **sob demanda**: cache da wiki por item (já existe `wiki-cache`), lido por código, não pela IA, quando a página tem; senão "ver na wiki" | não (cache) |
| Qual build seguir, objetivo, comparação com builds da comunidade, "por quê" | **Plano** (o que fica com a IA) | **sim** |

Contando pelo que aparece na página (seções Agora, Passos, Onde pegar, Equipamento, Mapa, Atributos, Ficha), só o
**objetivo** e a **comparação** ficam dependentes de IA: o resto passa a ser preenchido por código.

## Arquitetura

```
save + arquivos do jogo ─▶ índice de itens (cache) ─▶ /api/ds2/catalogo, /api/ds2/fontes?item= ─▶ página
                                      ▲
               marcados pelo jogador (servidor local, por personagem)
```

1. **Índice de itens** (`ds2itens.py`, cache `~/.buildsmith/cache/ds2/itens.json`, refeito quando o jogo muda):
   por item do jogo (IDs de `games/ds2/ids/*`): nome, categoria, requisitos, escala, ícone (cache da wiki), e as fontes:
   lojas (NPC, preço, estoque, área do NPC), trocas (NPC, alma, chefe e área dele), pontos no mapa (área, lote, baú ou
   cadáver, chave se for), drops (tipo de inimigo, área, quantos).
2. **Marcados**: coleção nova `quero` no banco local (o mesmo de fila/fogueiras): `{item_id, desde}` por personagem.
3. **Fontes ordenadas por código** (`ds2fontes.py`): recebe o item, o save (fogueiras acesas, área atual, inventário,
   atributos) e devolve as fontes ordenadas com `acesso`, `mais_cedo`, `mais_rentavel`, rota resumida (metros, portas e
   chaves) e o que falta (requisito, almas, chave, alma de chefe).
4. **Página**: aba **Catálogo** (filtros por categoria, busca, "melhor perto" do `ds2perto` em destaque, ★ para marcar);
   **Onde pegar** e **Passos** passam a mostrar os marcados (com as fontes por código) **e** os do plano da IA, se houver;
   "Ver rota no mapa" usa a rota calculada na hora.
5. **Plano (IA)**: continua opcional. Quando existe, sugere itens para marcar (com o porquê) e escreve objetivo e
   comparação; os itens que ele sugere usam as mesmas fontes por código (a IA para de escrever fontes e fluxos à mão:
   menos tokens e nada de fonte inventada).

## Limites e riscos

- **Condições de evento** (loja que só abre depois de libertar o NPC, item que só aparece no NG+, drop raro) não estão
  nas tabelas lidas hoje. Primeira versão: mostra a fonte com "pode ter condição — ver na wiki" quando a wiki-cache tem
  algo; depois, por flags de evento do save (como as portas).
- **Chance de drop**: o lote do inimigo é lido, a chance ainda não; até conferir no `ItemLotParam2_Chr`, o drop aparece
  sem porcentagem.
- **NG+**: lotes do NG+ (`…1` no fim, como na Bonfire Ascetic) precisam do ciclo do save.
- **Página publicada (celular, sem servidor)**: o catálogo precisa do servidor local; publicado, mostra só o que estava
  marcado quando foi publicado.

## Ordem de entrega (proposta)

1. `ds2itens` (índice) + `ds2fontes` (ordem por código) com testes; CLI `fontes --item`.
2. Rotas do servidor `/api/ds2/catalogo`, `/api/ds2/<personagem>/fontes?item=` e a coleção `quero`.
3. Aba Catálogo e Onde pegar com os marcados; passos gerados (equipar/upar/comprar/trocar).
4. Skill `build` passa a usar as fontes por código (só escolhe itens, objetivo e comparação).
5. Docs (README, skills, LEIA-ME do executável) e versão.
