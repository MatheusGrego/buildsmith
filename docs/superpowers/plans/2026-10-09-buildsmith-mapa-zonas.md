# Mapa: zonas de fogueira, chefes e NPCs — plano

- Status: concluído
- Data: 2026-10-09
- Decisor: Matheus (aprovado no chat: zonas por distância a pé desde a entrada, chefes e NPCs do jogo com retrato da wiki, destaque do plano, painel Rota da área)
- Continua: `2026-10-09-buildsmith-mapa-geral.md`

## Contexto

- O mapa geral (0.10.0) mostra chão por andar, itens e fogueiras, mas não diz **por onde seguir**: não há zonas, chefes nem NPCs.
- Verificado nos arquivos do jogo (Lost Bastille, 2026-10-09):
  - `generatorparam_<mapa>.param`: personagem de cada gerador em +8 (ex.: gerador 145 = 76800000 → NPC 7680); a posição está em `generatorlocation_<mapa>.param`.
  - `menu/text/english/npcmenu.fmg`: 7680 = Straid of Olaphis, 7520 = Lucatiel of Mirrah, 7643 = Steady Hand McDuff.
  - `BossBattleParam` (regulation): linhas 1016000/1016010/1016020 = mapa 10_16; flag 100962/100963/101001 (Ruin Sentinels, The Lost Sinner, Belfry Gargoyles em `games/ds2/bosses.json`); personagens do chefe em +44/+48/+52 (3251…, 6260, 3240) batem com os geradores do mapa (família 325×3, 626×1, 324×10).
  - MSB `POINT_PARAM_ST`: o ponto `マップ開始地点` (início do mapa) tem posição no mesmo lugar das partes (+0x10).

## Decisão

1. **Atores do jogo** (`ds2mapa`): NPCs (nome do `npcmenu.fmg`) e chefes (linha do `BossBattleParam` do mapa → nome e wiki em `bosses.json`; posição = média dos geradores da família do personagem) com andar.
2. **Zonas de fogueira**: cada triângulo do navmesh vai para a fogueira mais perto andando (Dijkstra com várias origens). Ordem das zonas = distância a pé desde o início do mapa; sem ponto de início, a primeira fogueira pelo ID. Contorno de cada zona por andar com o mesmo raster da planta. Cada ponto (item, NPC, chefe) ganha a zona.
3. **Página**: chão pintado pela zona (escala sequencial dourado → brasa), rótulo "1 · nome da fogueira"; chefe com retrato em moldura cor de brasa (apagado se derrotado no save), NPC com retrato redondo, item quadrado; NPC e item do plano com anel âmbar; popover por tipo (NPC: o que o plano precisa dele; chefe: estado e wiki); filtros novos (Zonas, NPCs, Chefes); painel **Rota da área** com as zonas em ordem e o que há em cada uma, clique centraliza.
4. Retratos de NPC e chefe pela página da wiki (`icones_wiki`, mesmo cache).

## Opções consideradas

1. **Ordem das zonas pela wiki** — descartado por agora: gasta token por área; a ordem a pé desde a entrada é um fato do jogo e a legenda diz como foi calculada.
2. **Zona por distância em linha reta (Voronoi)** — descartado: atravessa paredes e andares; a distância a pé respeita o chão.
3. **Nome de chefe pelo texto japonês do MSB** — descartado: exigiria tradução; a flag do `BossBattleParam` já liga ao nome em inglês.

## Consequências

- (+) Mapa responde "para onde vou agora": zona 1 → 2 → … → chefe, com o que tem em cada zona.
- (+) Tudo por script e cache; nenhum token por área.
- (−) Ordem a pé pode não ser a do jogo quando há porta trancada ou atalho (avisado na legenda).
- (−) Chefe que aparece só em evento (sem gerador no mapa) fica fora do mapa.

## Critério de aceite

- Lost Bastille: NPCs incluem Straid of Olaphis a < 5 m da fogueira Straid's Cell; chefes incluem Ruin Sentinels e Belfry Gargoyles com posição; 7 zonas, uma por fogueira, com ordem 1..7 sem repetir; todo item com zona.
- Malha sintética com duas fogueiras: cada metade vai para a fogueira do seu lado; a mais perto do início é a zona 1.
- Página: zonas coloridas e numeradas, Straid com anel âmbar (plano tem Ring of Knowledge dele), chefes com moldura de brasa, painel Rota da área centraliza a zona clicada; desktop e 375 px.
- `python -m pytest -q` verde.

## Tarefas

- [x] **1. Atores do jogo**: NPCs e chefes com nome, posição e andar no `extrair` (cache com versão). *Pronto quando:* teste sintético de montagem e teste da Lost Bastille passam.
- [x] **2. Zonas de fogueira**: Dijkstra com várias origens, ordem pelo início do mapa, contorno por zona e andar, zona de cada ponto. *Pronto quando:* teste sintético de duas fogueiras e teste da Lost Bastille passam.
- [x] **3. Dados da página**: zonas, NPCs (marca do plano e o que o plano precisa dele), chefes (estado pelo save), retratos da wiki. *Pronto quando:* testes do `prepare_page` cobrem NPC do plano, chefe derrotado e zonas no JSON.
- [x] **4. Mapa na página**: cores por zona, rótulos, marcadores por tipo, popovers, filtros novos, painel Rota da área. *Pronto quando:* funções puras testadas no node e conferido no navegador em desktop e 375 px.
- [x] **5. Docs, versão 0.11.0 e publicação**: skills, design system, README, página real refeita, push, plugin atualizado.

## Glossário

- **Gerador:** ponto do mapa onde o jogo faz nascer um personagem (inimigo, NPC ou chefe).
- **Dijkstra com várias origens:** caminho mais curto partindo de todas as fogueiras ao mesmo tempo; cada pedaço de chão fica com a fogueira que chega primeiro.
- **Escala sequencial:** cores em degraus de claro para escuro que indicam ordem (1, 2, 3…), não categoria.
