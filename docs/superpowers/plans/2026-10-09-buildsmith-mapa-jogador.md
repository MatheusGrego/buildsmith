# Mapa: jogador, rota até o alvo e inimigos com nome — plano

- Status: concluído
- Data: 2026-10-09
- Decisor: Matheus (pedido no chat: clicar no inimigo e ver qual é, mostrar o jogador em vermelho, caminho até a zona ou o item; escolheu "Investigar mais (HP/drops)" para o nome dos inimigos)
- Continua: `2026-10-09-buildsmith-mapa-zonas.md`

## Contexto

- O mapa (0.11.0) mostra zonas, chefes, NPCs e itens, mas os inimigos são pontos sem nome, o jogador não aparece e só há rota onde o plano tem `ponto`.
- Verificado no save real (2026-10-09, dois personagens):
  - Slot do personagem (`USER_DATA00N`): posição em +0x3A0 (3 floats) e mapa em +0x3C0 (bytes `cc dd BB AA` = `mAA_BB_dd_cc`).
  - Melatonina Vorcaro: `0000040a` = m10_04 (Majula), posição cai no chão de Majula (diferença de altura 0,12 m).
  - Melatonina (teste): `0000100a` = m10_16 (Lost Bastille), posição cai no chão da Bastille (0,18 m).
- Verificado nos arquivos do jogo:
  - Nenhum dos 769 textos (FMG) dos pacotes tem nome de inimigo comum; há nomes de chefe e de NPC.
  - A wiki não publica ID de inimigo; a página da área lista os inimigos e a de cada inimigo tem HP (NG, NG+, NG+7).
  - `EnemyParam` (regulation), HP em +0x28: linha 325000 = 2330 (Ruin Sentinel na wiki: 2330) e 227001 = 190 (Stray Hound: 190). Royal Swordsman (400) não apareceu em +0x28 nas famílias do mapa: a ligação personagem → linha ainda não está certa.
  - Cada mapa tem `generatorregistparam_<mapa>.param` (ainda não lido).

## Decisão

1. **Posição do jogador** (`ds2save`): mapa e posição do slot; o servidor local devolve ao vivo (relê o save), a página atualiza o marcador enquanto o Mapa está aberto.
2. **Inimigos com nome só com fonte**: ligar gerador → linha do `EnemyParam` (pelo `generatorregistparam` ou pelo campo certo do gerador), ler HP e drops (`ItemLotParam2_Chr`), cruzar com a lista de inimigos da área na wiki (HP NG e drops). Nome só quando um único inimigo da wiki bate; senão "nome não confirmado" com HP e drops do jogo.
3. **Rota até o alvo**: botão "Rota até aqui" no popover de item, NPC, chefe e zona. Jogador na mesma área: caminho pelo chão a partir dele (servidor calcula com o navmesh). Em outra área: caminho a partir da fogueira da zona do alvo, com aviso "viaje até a fogueira X".
4. **Página**: jogador como marcador vermelho pulsante com "Você", área do jogador sempre no mapa, inimigos clicáveis (popover com nome ou tipo, HP, drops, quantos iguais e destaque dos iguais).

## Opções consideradas

1. **Nome dado pelo jogador** — descartado pelo Matheus: preferiu investigar a fonte no jogo e na wiki.
2. **Rota calculada no navegador** — descartado: exigiria mandar o navmesh inteiro na página; o servidor já tem o navmesh em cache e o `ds2mapa.rota`.
3. **Posição só na hora de montar a página** — descartado: o jogador anda; o servidor relê o save.

## Consequências

- (+) Mapa mostra onde você está e o caminho até o que o plano pede.
- (+) Nome de inimigo com fonte (jogo + wiki) ou dito claramente que não está confirmado.
- (−) Posição só atualiza quando o jogo grava o save.
- (−) Rota pelo chão não conhece portas, alavancas e quedas (aviso continua).
- (−) Parte dos inimigos pode ficar sem nome confirmado.

## Critério de aceite

- `ds2save` lê mapa e posição dos dois personagens do save real e o ponto cai no chão do mapa (< 1 m); teste sintético do offset.
- Inimigos da Lost Bastille: Ruin Sentinel e Stray Hound com nome e HP batendo com a wiki; os sem confirmação dizem "nome não confirmado"; nenhum nome sem fonte.
  - **Mudou na investigação:** o HP da wiki não bate sempre com o do jogo (Royal Swordsman: wiki 400, jogo 450/390; Stray Hound: wiki 190, jogo 210), e Ruin Sentinel é chefe (aparece como chefe, não como inimigo). O que bate são **drops e almas**: o critério virou "nome com prova de drops + almas ou lista da área, vencedor único".
- Servidor: `posicao` e `rota` respondem só a pedido local; rota da posição do (teste) até a fogueira Straid's Cell sai com metros.
- Página: marcador vermelho no lugar certo, "Rota até aqui" desenha o caminho, popover de inimigo; desktop e 375 px.
- `python -m pytest -q` verde.

## Tarefas

- [x] **1. Inimigos: ligação, HP e drops**: gerador → `EnemyParam`, HP e drops do jogo, nome pela wiki só quando bate. *Pronto quando:* Ruin Sentinel e Stray Hound saem com nome e HP da wiki na Lost Bastille e o teste cobre "não confirmado".
- [x] **2. Posição do jogador no save**: mapa e posição por slot, CLI. *Pronto quando:* teste sintético e teste do save real (pulado sem save) passam.
- [x] **3. Servidor: posição e rota ao vivo**: endpoints locais, rota de posição para posição. *Pronto quando:* testes do `serve` cobrem posição, rota e pedido de fora recusado.
- [x] **4. Página**: jogador vermelho, área dele no mapa, inimigos clicáveis, "Rota até aqui". *Pronto quando:* funções puras testadas no node e conferido no navegador em desktop e 375 px.
- [x] **5. Docs, versão 0.12.0 e publicação**: skills, design system, README, página real refeita, push, plugin atualizado.

## Resultado (2026-10-09)

- Ligação: `generatorregistparam_<mapa>` (linha = personagem do gerador) → 1º int = linha do EnemyParam; HP +0x28, almas +0xD0 (Royal Swordsman 180 = wiki), drops +0x4C/+0x134 (set Royal Swordsman, set Varangian).
- Lost Bastille: 15 de 24 tipos com nome e prova (Royal Swordsman, Hollow Varangian, Gaoler, Rupturing Hollow, Stray Hound, Nimble Shadow, Undead Aberration); o resto "nome não confirmado". Fantasmas de NPC (EnemyParam do próprio NPC, ex. 813001 → Felicia the Brave) saem da lista de inimigos.
- Posição: Vorcaro em Majula (ao lado da The Far Fire), (teste) na Lost Bastille; rota real do (teste) até Straid's Cell: 351 m em 0,05 s.
- Navegador: "Você" vermelho, Onde estou, popover de inimigo com destaque dos 17 iguais, Rota até aqui (21 m em Majula; 133 m da The Tower Apart quando você está em outra área); 375 px sem rolagem lateral.
