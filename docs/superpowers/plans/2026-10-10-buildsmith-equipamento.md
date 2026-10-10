# Equipamento: agora × plano, estilo inventário do DS2, com escala de atributo — plano

- Status: em andamento
- Data: 2026-10-10
- Decisor: Matheus (pedido no chat: "SCALING, muito importante", "não vi o drip de armadura", "PLANO (equipamento): todo meu equipamento, melhor do plano, pra ver como ficaria, tipo o inventário do DS2")
- Continua: `2026-10-09-buildsmith-mapa-jogador.md`

## Contexto

- O plano sugere trocas (cajado, chama, armadura, feitiços) espalhadas em passos e itens; não existe uma visão do conjunto equipado, nem antes × depois.
- A recomendação da Dark Pyromancy Flame (corrigida em 2af6b07) mostrou o risco de comparar fora do equipado: a skill agora parte do save (`ds2calc sintonia`, `ds2perto`).
- Escala de atributo, verificado em 2026-10-10:
  - O jogo guarda um coeficiente por atributo (WeaponStatsAffectParam), mas a letra do menu não sai dele por limiar simples: coeficiente 0,45 dá C na FOR do Longsword e 0,35 dá B na DES do Rapier (letras da wiki).
  - A wiki publica as letras por item e por upgrade (tabela "Upgrades": Regular, +N, infusões). Ex.: Uchigatana FOR E / DES B no +0, DES A no +10; Lizard Staff INT A; Pyromancy Flame fogo A no +0, S no +5.
  - O quanto o atributo soma no AR sai do jogo (ds2calc: base + escala × bônus do atributo).
- Slots vazios no save: mão vazia = 3400000 (punho, AR 49 conferido no menu); cabeça/mãos/pernas vazias = 21001100/21001102/21001103 (não existem no `itemname.fmg`; apareceram quando o set Tseldora saiu).

## Decisão

1. **Tela Equipamento** (grupo Plano, ao lado de Agora): grade como o menu de equipamento do DS2 — mão direita R1–R3, mão esquerda L1–L3, cabeça/peito/mãos/pernas, 4 anéis e os slots de sintonia. Alterna **Agora** (save), **Plano** (melhor do plano) e **Comparar** (os dois, com a diferença). Clique no slot: nome, upgrade, AR por elemento, letras de escala, quanto cada atributo soma, e de onde vem a peça (link para Onde pegar e o passo).
2. **Bloco `equipamento` no plano, gerado por script** (`ds2equip.py`): lê o snapshot (agora) e as trocas que o plano decide (`--troca L1="Lizard Staff:0"`, `--troca peito="Black Witch Robe"`, `--sintonia ...`) e calcula os números das duas colunas. O modelo só escolhe as trocas.
3. **Letras de escala pela wiki** (`escala_wiki.py`, cache 30 dias, como os ícones): tabela de upgrade do item → letras por nível; o `prepare_page` completa os slots.
4. Armadura do plano inclui o visual (drip) escolhido pelo jogador quando ele pedir; o slot mostra a peça e de onde vem.

## Opções consideradas

1. **Letra calculada do coeficiente do jogo** — descartado: não reproduz as letras da wiki (ver Contexto).
2. **Letras escritas à mão no plano** — descartado: é o trabalho manual que o jogador reclamou.
3. **Mostrar só o plano** — descartado: o pedido é ver como ficaria comparado ao que ele usa.

## Consequências

- (+) Uma tela responde "como fico com o melhor do plano" e "quanto ganho".
- (+) Números do jogo, letras com fonte, nada montado à mão.
- (−) Item sem tabela de upgrade na wiki fica sem letra ("—").
- (−) Armadura sem defesa/peso por enquanto (o leitor do ArmorParam ainda não existe).

## Critério de aceite

- `ds2equip` com o snapshot do Vorcaro: R1 Uchigatana +5 AR 218, L1 Sorcerer's Staff +2 mágico 205, R2 Pyromancy Flame +0 fogo 223, cabeça/mãos/pernas vazias, 6 feitiços na sintonia; com as trocas do plano, L1 Lizard Staff +0 mágico 240 e Great Soul Arrow 184 → 215.
- Letras: Uchigatana +5 FOR E / DES B, Lizard Staff INT A, Pyromancy Flame +2 fogo A (tabela da wiki) com teste de parser em HTML de exemplo.
- Página: seção Equipamento com Agora/Plano/Comparar, popover com AR, escala e fonte; desktop e 375 px.
- `python -m pytest -q` verde.

## Tarefas

- [x] **1. Slots vazios e equipado do save**: punho e armadura vazia com nome, upgrade do item equipado. *Pronto quando:* teste com o layout do save e o snapshot real mostram "vazio" nesses slots.
- [x] **2. `ds2equip.py`**: bloco `equipamento` (agora × plano) com AR, bônus por atributo e sintonia, a partir do snapshot e das trocas. *Pronto quando:* critério de aceite do ds2equip passa em teste (jogo real, pulado sem jogo) e em teste sintético.
- [x] **3. Escala pela wiki**: parser da tabela de upgrade, cache, `prepare_page` completa as letras. *Pronto quando:* testes do parser e do cache passam.
- [x] **4. Página**: seção Equipamento estilo inventário, Agora/Plano/Comparar, popover. *Pronto quando:* funções puras testadas no node e conferido no navegador em desktop e 375 px.
- [ ] **5. Plano real, skill, docs, versão 0.13.0 e publicação**: skill build gera o bloco com `ds2equip`; página do Vorcaro refeita com o visual Black Witch e o Lizard Staff; push; plugin atualizado.
