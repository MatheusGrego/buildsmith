# buildsmith — mapa isométrico com o cenário real do jogo

Data: 2026-10-10
Status: aprovado em conversa ("tá certo sim... faz um arquivo com o MD disso"; "pode começar a implementar sem me perguntar")
Complementa: `docs/superpowers/plans/2026-10-09-buildsmith-mapa-geral.md` (seção Mapa 2D)

## Por quê

O mapa de hoje é o **navmesh** (chão por onde a IA anda) rasterizado e contornado por andar (`ds2planta.py`), desenhado em 2D de cima (`mapa.js`). Com "Todos" os andares ligados, tudo se sobrepõe (print de Majula, 2026-10-10); sem parede, teto, escada ou textura, um lugar escuro (área das tochas) não é reconhecível. O que faz alguém bater o olho e pensar "tô aqui" é **a estrutura do lugar com a cara do jogo, com profundidade**.

## Objetivo

1. Vista **isométrica interativa** da área com o **cenário 3D real** (peças de mapa e objetos) e **texturas do jogo**.
2. Câmera de ângulo fixo: zoom, arrastar, girar em passos de 90°, **corte de altura** que esconde o que está acima do andar escolhido (estilo The Sims/Diablo).
3. Botão **2D / Isométrico** na seção Mapa: os mesmos ícones, filtros, rota e "Você" nas duas vistas. O 2D continua sendo o padrão quando a área não tem cena extraída, na página publicada (celular) e sem WebGL.
4. Objetos do jogo (portas, baús, alavancas, elevadores, tochas/sconces, névoas) em 3D com rótulo clicável; tochas com destaque e filtro próprio.

## Fatos descobertos (2026-10-10, Majula `m10_04_00_00`)

- Os pacotes `GameData*` trazem, por área:
  - `/model/map/m10_04_00_00.mapbhd` + `.mapbdt` (22 MB): binder dividido **BHF4/BDF4** com 369 arquivos — `mXXXX.flv.dcx` (modelos **FLVER**), `mXXXX.mte.dcx` e um `.acb`.
  - `/model/map/t10_04_00_00.tpfbhd` + `.tpfbdt` (128 MB): 260 `*.tpf.dcx` (ex.: `B_floor_00_d`, `_n`, `_s`); cada TPF tem DDS (ex.: DXT5 1024×512).
  - `/model/map/h10_04_00_00.hkxbhd/.hkxbdt` (colisão alta) e `l10_...` (baixa) — não usados aqui.
- BHF4 com entradas de 0x24 bytes: tamanho em +0x08, offset no `.bdt` em +0x18, nome (UTF-16) pelo offset em +0x20.
- `ds2arquivos.dcx` já abre os modelos: o FLVER sai com cabeçalho `FLVER\0L\0` (little endian), versão 0x2000x.
- Hoje o MSB já é lido (`ds2mapa.partes_msb`): nome, tipo e posição. Falta rotação, escala e o nome do modelo de cada parte.

## Arquitetura

```
arquivos do jogo ──ds2cena.py extrair──▶ ~/.buildsmith/cache/ds2/cena/<area>/ ──serve.py──▶ página (mapa.js + iso.js + three.js)
```

### 1. Extração (Python, cache)

Novo `skills/ds2-save/scripts/ds2cena.py`, com leitores pequenos e testáveis, um por formato:

| Unidade | Lê | Devolve |
|---|---|---|
| `binder` | BHF4/BDF4 | `{nome: bytes}` dos arquivos internos (com DCX aberto) |
| `flver` | FLVER2 do DS2 | malhas: posições, normais, UV, índices; material → nome da textura difusa |
| `tpf` / `dds` | TPF com DDS | DDS **sem os mipmaps maiores** (teto `TEX_MAX` = 512 px), ainda comprimido |
| `msb` (estende `ds2mapa`) | partes "peça de mapa" e "objeto" | modelo, posição, rotação (graus, XYZ), escala |

Saída em `~/.buildsmith/cache/ds2/cena/<area>/`:

- `cena.json`: `versao`, `assinatura`, `area`, `caixa` (min/max), `cortes` e `andares` (os mesmos de `ds2planta`), `modelos` (nome → faixas no `geo.bin` por submalha + textura), `instancias` (modelo, matriz 4×4, tipo `mapa`/`objeto`, `rotulo` quando for objeto conhecido), `texturas` (nome → arquivo, formato, largura, altura).
- `geo.bin`: por submalha, posições `float32` (no espaço do modelo), normais `int8×3`, UV `float16×2` (ou `float32` se o spike mostrar UV fora de faixa), índices `uint16`/`uint32`.
- `tex/<nome>.dds`: só as difusas usadas, DDS reescrito com cabeçalho do mip escolhido.
- Regras do cache atual: `assinatura` do jogo + `CENA_VERSAO` (refaz se mudar), gravação atômica (pasta temporária + `os.replace`), extração **sob demanda por área**.
- CLI: `python ds2cena.py extrair --area m10_04_00_00` → resumo JSON (modelos, instâncias, texturas, MB, segundos).
- Fora do escopo: colisão `.hkx`, normal/specular, LOD, iluminação do jogo, vegetação animada, personagens.

### 2. Servidor

`app/serve.py`, nova rota só leitura:

- `GET /api/ds2/cena/<area>/cena.json` e `.../geo.bin` e `.../tex/<nome>.dds` — área validada por `AREA_OK`, nome de textura por `SEGMENT`, só arquivos dentro de `cache/ds2/cena/<area>/`.
- Se a área ainda não foi extraída, `cena.json` responde `404 {"erro": "cena não extraída", "comando": "ds2cena.py extrair --area ..."}`; extração **não** roda dentro do GET (pode levar dezenas de segundos). `POST /api/ds2/cena/<area>/extrair` (mesma regra `_trusted` dos outros POST) dispara a extração numa thread e o GET devolve `202 {"estado": "extraindo"}` até terminar.

### 3. Visualizador (página)

- `skills/build-page/template/vendor/three.module.min.js` (three.js r16x, licença MIT, arquivo único, sem build) + `DDSLoader` mínimo próprio (só DXT1/DXT3/DXT5/BC7 que aparecerem no spike).
- Novo `skills/build-page/template/iso.js` (módulo ES), separado de `mapa.js` (que já tem ~36 KB):
  - Câmera **ortográfica** em ângulo isométrico (elevação ~35°, azimute 45° + k·90°); zoom (roda/pinça/botões), arrastar, girar ⟲ ⟳.
  - **Corte de altura**: plano de recorte em `y = topo do andar escolhido + 2,5 m`; o seletor de andar do 2D passa a mover o corte; "Todos" = sem corte.
  - Material **sem a luz do jogo**: textura difusa × sombreamento simples por normal (hemisférica + direcional fixa da câmera), para área escura ficar legível; geometria abaixo do andar atual levemente escurecida.
  - Ícones/rótulos (fogueiras, itens, NPCs, chefes, inimigos, "Você", rota) **reaproveitam os dados e filtros do `mapa.js`**, projetados do 3D para a tela numa camada HTML/SVG por cima do canvas — mesma aparência e mesmos popovers do 2D.
  - Objetos: clique num objeto 3D (raycast) abre popover com o rótulo; filtro "Tochas" destaca sconces (contorno/realce).
- `mapa.js`: botão `2D | Isométrico` na barra; troca de vista mantém área, andar, filtros e o ponto central; Isométrico desabilitado com dica quando: sem WebGL, página publicada (sem `/api`), ou cena não extraída (botão "Extrair cena desta área" → POST).

### 4. Tochas (etapa própria, depois)

Estado aceso/apagado depende de achar a flag de cada sconce no save (`flags-diff` entre snapshot antes e depois de acender uma). Só entra se a flag for confirmada em pelo menos duas tochas; até lá, tochas aparecem sem estado.

## Erros e limites

- Jogo ausente / área sem `.mapbhd` → cena indisponível, 2D segue normal.
- Formato inesperado (FLVER, TPF, DDS) → modelo/textura pulados com aviso no `cena.json` (`avisos`), nunca derruba a área inteira; textura ausente vira cinza.
- Orçamento por área: **≤ 30 MB** em disco e **≤ 60 s** de extração em Majula; acima disso, baixar `TEX_MAX` para 256.
- Navegador sem `WEBGL_compressed_texture_s3tc` → Isométrico desabilitado com dica (fica no 2D).

## Testes

- Python (pytest, dados sintéticos como os de hoje): BHF4 mínimo; FLVER mínimo com 1 malha/1 material; TPF/DDS com mips (corte do mip certo e cabeçalho reescrito); matriz de instância a partir de posição/rotação/escala; `cena.json` + `geo.bin` coerentes (faixas dentro do arquivo); cache refeito quando versão/assinatura mudam; rotas do servidor (404/202/200, caminho inválido recusado).
- Teste com o jogo instalado (pulado sem o jogo, como `test_injection_live`): Majula extrai, ≥ 100 instâncias, ≥ 50 texturas, dentro do orçamento.
- JS (node, funções puras): matriz da câmera isométrica por giro, projeção 3D → tela, altura do corte por andar.
- Navegador: Majula no Isométrico com textura, giro 90°, corte por andar, ícones alinhados com o 2D, "Você" no lugar certo, troca 2D ↔ Iso mantendo o centro.

## Ordem de entrega

1. **Spike Majula** (descartável): ler FLVER + MSB + DDS e renderizar o cenário isométrico com textura numa página de teste. Mata os riscos: layout de vértice do FLVER2 do DS2, rotação/escala do MSB, tamanho e tempo.
2. Extração definitiva (`ds2cena.py`) com testes.
3. Rotas do servidor.
4. `iso.js` + botão 2D/Iso + ícones/rota/"Você".
5. Objetos com rótulo + filtro Tochas.
6. Docs (skills, design system, README), versão do plugin.
7. (Depois) Estado das tochas pelo save.

## Ajustes depois do primeiro teste (2026-10-10)

Prints do Huntsman's Copse mostraram cenário cinza e lavado, manchas pretas, peças gigantes cobrindo tudo e o arrasto
"girando" a vista. Causas e o que mudou:

- **Cor:** a textura não era marcada como sRGB (cor lavada) e o tone mapping ACES tirava o resto da cor; o servidor também
  recusava nome de textura com maiúscula. Agora: textura sRGB (ou conversão no shader sem a extensão), sem tone mapping,
  luz hemisférica + direcional que segue a câmera, leve saturação e um "ombro" nas luzes altas; o extrator grava os nomes
  em minúsculas.
- **Textura torta:** a UV do FLVER2 do DS2 é int16 ÷ 2048 (tipo 0x15), não float16; normais por tipo (Byte4B); strips e
  LOD tratados.
- **Manchas pretas e peças gigantes:** materiais SkyDome e NoLit (céu de 10 km, cartões pretos de neblina/escuridão nas
  entradas de caverna) e caixas de textura `dummy` ficam de fora; o que passa da área jogável some aos poucos no shader.
  Folhagem `_Alp_1bit` usa recorte (DXT1 com alfa), decal é translúcido, água semitransparente.
- **Câmera:** em vez de giro em passos de 90°, câmera de espectador livre: arrastar agarra o chão (o ponto fica sob o
  cursor), botão direito/Alt gira e inclina (15°–89,5°), roda dá zoom no cursor, WASD/setas andam, Q/E giram, R/F
  inclinam, Shift acelera; botões ⟲ ⟳ (45°), bússola (norte para cima), De cima, Interior e Foco. O alvo desliza pelo
  raio da vista até o chão sob o centro (a imagem não pula).
- **Interior:** o corte deixa de ser um plano só: é a altura do navmesh do andar (grade de 1,5 m, alargada para pegar as
  paredes) + 3,2 m, com a linha do corte cor de osso. No 3D, clicar num andar liga o corte; "Todos" desliga; I liga no
  andar do centro da vista (ou no seu, se estiver perto); PgUp/PgDn trocam. Cada área abre inteira.
- **Foco:** o que está longe do centro da vista escurece e perde a cor (raio proporcional ao zoom), com vinheta leve;
  marcadores fora do foco ficam apagados.
- **Rota:** era Dijkstra pelos centróides dos triângulos (zigue-zague). Agora o caminho é o funil (string pulling) pelas
  arestas atravessadas, com a altura do chão em cada travessia; a linha tem gradiente da 1ª à última parada e traços que
  andam no sentido da rota; paradas são pinos numerados na escala das zonas (dourado → brasa).
- **Cache:** `CENA_VERSAO` 2 (o cache da versão 1 é refeito), gravação atômica, `geo.bin` em gzip (~3× menor, vai com
  `Content-Encoding: gzip`), o GET nunca extrai: a página faz `POST .../extrair` e consulta até ficar pronto (202 enquanto
  extrai). As 28 áreas extraem em até ~14 s; Drangleic Castle (1393 peças) desenha em ~5 ms por quadro.
- Objetos do MSB (portas, baús, alavancas, tochas) continuam para a etapa 5.

## Entidades em escala, nomes pelo jogo e câmera livre (2026-10-11)

Pedido: inimigos (e portas, alavancas, pontes, baús, chaves) desenhados **na escala do mapa**, ligando e desligando pelos
filtros; para chegar num item, mostrar **por onde passar e qual chave abre**; descobrir por que o Pursuer perto do McDuff
(Lost Bastille) aparecia como "não identificado" e identificar todos os inimigos. Anotado em conversa: além da câmera
fixa, uma **câmera livre de espectador** (WASD, segurar um botão para olhar, entrar nos lugares).

### Por que o Pursuer não tinha nome

O jogo não guarda nome de inimigo comum. O nome vinha só da wiki (`inimigos_wiki.py`): almas e drops do EnemyParam
contra as páginas da lista "Enemies". O Pursuer da Lost Bastille é a linha `318030` do EnemyParam: um **chefe** de outra
área (Forest of Fallen Giants) usado como inimigo comum. Ele não é chefe do BossBattleParam da Lost Bastille (então vira
inimigo), não está na lista de inimigos da wiki (está na de chefes) e não dropa nada: nenhum ponto bate.

### Fatos descobertos

- `GeneratorParam` +0x08 é a linha do `GeneratorRegistParam` (o "personagem" do código), e o 1º int dela é a linha do
  `EnemyParam` (o `tipo`). Definições no Paramdex (soulsmods), `DS2S/Defs`.
- **A linha do EnemyParam // 100 é o modelo do personagem** `cXXXX`: 102000 → c1020 Hollow Soldier, 318030 → c3180 The
  Pursuer; conferido em 624 linhas com nome nas duas tabelas (as 69 diferentes são sinônimos: "Forest Grotesque" usa o
  modelo "Goblin").
- O Smithbox (MIT) tem nome para 894 linhas do EnemyParam (vindas do Paramdex), 204 modelos de personagem e 1300 modelos
  de objeto. Viraram `games/ds2/nomes_smithbox.json` (licença em `games/ds2/LICENSE-SMITHBOX`, commit da fonte no arquivo).
- `MapObjectInstanceParam` (por mapa): param do objeto em +0x00 (fogueira, porta, baú), **tipo da instância** em +0x14
  (`MapObjectInstanceTypeParam`, cujas linhas o jogo nomeia em japonês: 120–123 baú, 130 cadáver, 170/180/190 alavanca e
  interruptor, 195 escada, 200–240 porta, 110 névoa, 540 ponte que quebra) e lote de item em +0x24.
- MSB, parte de objeto: o modelo (índice em `MODEL_PARAM_ST`, +0x0C) e a rotação (+0x1C) seguem o mesmo layout das peças
  de mapa. Os nomes dos modelos dizem o que é: `o00_0300` Wooden Door, `o00_0500` Fog Gate, `o00_0600` Vertical Lever,
  `o16_9005` Elevator, `o00_0200` Wooden Treasure Chest. Alguns dizem a chave: `o04_0470` "Large Stone Door (Forgotten
  Key)", `o14_0371` "(Den Key)" (Tseldora Den Key), `o21_9075` "(Key to King's Passage)", `o00_0317` House Key, `o00_0318`
  King's Ring.

### O que mudou

- `ds2nomes.py`: nome do inimigo pela linha do EnemyParam, senão pelo modelo; categoria do objeto pelo nome do modelo
  (ordem importa: "Lever Door" é porta, "Drawbridge Lever" é alavanca), senão pelo tipo da instância; chave da porta pelo
  nome do modelo, só se existir com esse nome entre os itens do jogo.
- `ds2mapa.py` (`EXTRACAO_VERSAO` 5): `objetos` por área (categoria, nome do modelo, posição, rotação, chave, lote), itens
  marcados com `no` (baú/cadáver) e `chave`; CLI `inimigos` lista os tipos de cada área e os que ficam `sem_nome`.
- `mapas_pagina.py`: nome do inimigo pelo jogo primeiro (com a prova); a wiki só é consultada para o tipo que o jogo não
  nomeia (poupa centenas de páginas); retrato e link pela página da wiki do nome base; `chefe` marca chefe de outra área
  visto como inimigo; objetos com a chave, o ícone dela e onde ela está no chão das áreas da página.
- Página: filtros **Chaves** (ligado: itens que são chave e portas com chave), **Baús**, **Portas e alavancas** e
  **Inimigos**. No 2D a forma tem tamanho em metros e cresce com o zoom (porta como barra girada pela rotação do jogo,
  baú, alavanca, elevador; inimigo com retrato quando bem perto). No 3D viram formas na escala do cenário
  (`iso.setEntidades`: cápsula com a altura do inimigo, ~1,8 m para Hollow, ~3 m para Ruin Sentinel, 3,4 m para chefe;
  porta 2,2–4,4 m; névoa translúcida; baú; alavanca; elevador), com o mesmo corte de interior e foco do cenário; o clique
  abre o popover. Popover da porta com chave: "Abre com", onde pegar a chave ("ver no mapa" abre a área e o item) e a wiki.
- Câmera **Livre** (botão ou V): perspectiva, WASD voa para onde olha, segurar e arrastar olha em volta, E/Espaço sobe,
  Q/C desce, roda avança para o cursor, Shift acelera; sair volta a câmera fixa para onde a livre olhava.
- Bug achado no caminho: duas chamadas de `iniciar()` ao mesmo tempo criavam dois renderers (tela preta); agora é uma só.

### Limites (o que não dá para afirmar daqui)

- Esta sessão não tinha os arquivos do jogo: tudo foi testado com dados sintéticos (pytest, node e Chromium com uma cena
  feita à mão). Os testes com o jogo instalado (`test_real_lost_bastille_objects_and_the_pursuer`) rodam na sua máquina.
- As formas 3D são **substitutas** (caixa, cápsula, disco), não os modelos do jogo. O eixo da largura da porta (x local)
  e o centro do modelo (no meio ou na dobradiça) não foram conferidos: uma porta pode sair girada 90° ou meio vão de lado.
- Porta genérica (a maioria, como as celas da Lost Bastille) não diz no modelo qual chave abre; isso está nos scripts de
  evento do jogo (Lua compilado), que não são lidos. A rota pelo chão continua sem saber se a porta está trancada.

### Próximos passos

1. Modelos reais de objetos e inimigos no 3D (FLVER de `model/obj/` e `model/chr/`; o leitor de FLVER2 já existe; falta
   conferir o caminho e o pacote das texturas no jogo). As substitutas ficam como reserva.
2. Chave ↔ porta genérica: pelos scripts de evento, ou o plano diz (o nó do fluxo aponta a porta e a chave, com a wiki
   como fonte) e o mapa desenha a porta na rota.
3. Estado pelo save: porta aberta, alavanca puxada, baú aberto, chefe morto (flags de evento, como já é feito com as
   fogueiras).
4. Detectar sozinho o que mudou no save (como a posição já é relida): item do plano pego (inventário), nível e atributos
   subindo, e atualizar a página.

## Modelos reais de objetos e inimigos no 3D (2026-10-11, depois)

As formas (caixa, cápsula) eram só reserva. Agora a cena traz os modelos do jogo:

- **Onde estão** (lista de arquivos do DS2 SotFS do Smithbox): objetos em `/model/obj/<oXX_XXXX>.bnd`, personagens em
  `/model/chr/<cXXXX>.bnd` e as texturas deles em `/model/chr/<cXXXX>.texbnd`. São binders BND4; os pacotes do jogo são
  vários (`*Ebl.bhd`), então `ds2cena.Pacotes` procura em todos (GameData primeiro, os de baixa qualidade por último).
- **Ossos**: malha rígida do FLVER fica no espaço do osso. Como o Smithbox faz: com normal UByte4/Byte4E, o 4º byte da
  normal é o osso de cada vértice (índice na lista de ossos da malha); senão, a malha toda vai pelo osso dela. Osso local
  = T · Ry · Rz · Rx · S (radianos), mundo = pai · local. Só nos modelos novos: as peças de mapa seguem como estavam.
- **Objetos** (MSB tipo 1: portas, baús, alavancas, elevadores, estátuas, barris...) entram no cenário como as peças de
  mapa, sempre visíveis (estão no mundo). O filtro do objeto (Portas e alavancas, Baús, Chaves) **realça** a peça com cor
  (porta com chave em ouro); objeto sem modelo legível continua com a forma de reserva, ligada pelo filtro.
- **Inimigos**: modelo = linha do EnemyParam // 100, virado pela rotação do gerador (`generatorlocation` +0x0C, graus);
  aparecem e somem pelo filtro Inimigos, na pose de referência do modelo (sem animação). Tipo destacado fica dourado.
- Cache: `CENA_VERSAO` 3 (a cena 3D de cada área é refeita na primeira vez que abrir) e `EXTRACAO_VERSAO` 6.

Não conferido daqui (sem o jogo): o formato exato dos binders de `chr`/`obj` (o leitor aceita os layouts de BND4 e BND3 do
SoulsFormats), se as texturas dos personagens são DXT (as que não forem ficam cinza, com aviso no `cena.json`) e se a
rotação do gerador é em graus. Os avisos da extração (`cena.json` → `avisos`) dizem quais modelos ficaram de fora.

## Save ao vivo na página (2026-10-11)

Pedido: "identificar quando pegamos os itens do plano automaticamente, igual ele atualiza o mapa, ou subimos de
nível/atributos". O servidor já relia o save para a posição; agora também para o resto:

- `ds2save.ao_vivo(save)`: por personagem, nível, almas, soul memory, atributos, inventário (nome, quantidade, reforço,
  categoria), equipado e chefes derrotados (flags do `bosses.json`). `GET /api/ds2/<personagem>/save` (relê só quando
  o arquivo muda; 404 se o personagem não está no save, 503 se o save não abre).
- `vivo.js` (funções puras, testadas no node): o que o save diz de cada passo do plano. `equipar`: o que "entra" está
  equipado e o que "sai" não; `chefe`: chefe derrotado; `compra`/`troca`: o item entregue no inventário (com a quantidade
  do "→ N" do `sub`); `upgrade`: o item do nó "+N" no reforço N; `nivel`: o atributo do nó `atributo` "a → b" chegou em b.
  O que avançou sem fechar vira texto ("VGR 14 de 20", "Dull Ember no inventário": pegar não é entregar).
- Página (a cada 6 s com a aba visível, só pelo servidor local): nível com "+N desde o plano" e almas no topo, selo
  "ao vivo", atributos e ficha com os valores do save, "✓ você tem ×N" nos itens do plano, selo no passo, "N de M
  feitos" contando o que o jogo mostra, e no mapa o item do plano que você já tem ganha um ✓.
- Nada é gravado no estado da página: a marca sai sozinha se o save voltar atrás. A fogueira (marcar feito à mão)
  continua igual.

## Retorno do primeiro teste no jogo e realce (2026-10-11)

- **Baú virava a caixa de reserva:** bug no leitor de FLVER com ossos: a lista de matrizes de osso de uma malha rígida
  sobrescrevia a lista de materiais, e a malha seguinte quebrava o modelo inteiro (baú tem tampa e caixa). Corrigido,
  com teste; `CENA_VERSAO` 4. O leitor também tenta índices de 16 bits quando os de 32 saem fora dos vértices.
- **Motivo da forma de reserva:** `cena.json` → `sem_modelo` (modelo → motivo); o popover do objeto no 3D mostra;
  `ds2cena.py modelo --modelo <m>` dá o diagnóstico completo.
- **NPC virava lápide:** a lápide `o00_9050` é um objeto de evento (aparece quando o NPC morre) e entrava no cenário com
  os outros objetos. Fica fora, junto dos ajudantes "Dummy" (`ds2nomes.fora_da_cena`), até o estado vir do save. O NPC
  com modelo próprio no jogo (linha do EnemyParam // 100: Straid `c7680`, McDuff `c7643`, Lucatiel `c7520`) aparece com
  ele no 3D (`EXTRACAO_VERSAO` 7: `npcs[].modelo` e `rot`).
- **Realçar inimigos** (botão ou H): inimigos em vermelho forte com anel pulsando (2D e 3D), o resto dos marcadores
  apagado, e no 3D uma segunda passada em cor chapada que ignora a profundidade (dá para ver através das paredes),
  menos para o que está acima do corte de Interior.
- **Pose T:** os modelos vêm sem animação; plano em `docs/superpowers/plans/2026-10-11-buildsmith-mapa-estado-chaves-animacao.md`
  (Parte C), junto com o estado do mundo pelo save (Parte A) e a chave das portas comuns (Parte B).

## Estado do mundo no save — fatos descobertos (2026-10-11, spike do Task 1)

Fonte: 16 cópias do save do mesmo personagem (os backups automáticos `*.co2.bak` e os nomeados `antes-do-*`), de
2026-10-06 a 2026-10-11, comparadas em pares com `ds2save.py blocos-diff` e com o inventário de cada uma. Nenhum valor
vem de outro programa; o que está abaixo foi conferido nessas cópias.

- **Onde**: no bloco de mundo do slot (`USER_DATA0(10+slot)`, 501.936 bytes), uma **tabela de eventos por área**: 28
  registros seguidos de `0xC08` bytes, na mesma ordem (Majula, Forest of Fallen Giants, Heide's, Lost Bastille...).
  A posição da tabela **muda** entre gravações (0x2EF2C, 0x34F34, 0x3AF3C nas cópias): é achada procurando 3 registros
  seguidos com o ID do mapa no cabeçalho.
- **Registro** (`0xC08`): `u32` mapa (`0x0A110000` = m10_17), `u32` n, **192 pares** `(u32 evento, u32 estado)` (os n
  primeiros valem), **192 `u32` de lote** em `+0x608` e **192 `u32` de estado do lote** em `+0x908` (paralelo ao de lote).
- **Evento = `ref` da parte do MSB** (a linha do `mapobjectinstanceparam`): baú `ref` = o lote (10045000), porta, alavanca,
  elevador, Pharros com `ref` 8 dígitos do mapa (10160432). 315 dos 768 objetos das áreas extraídas estão na tabela.
- **Estados dos objetos** (só os que se repetiram com a ação certa no intervalo):
  - Porta: `10` fechada (como no começo); `20` ou `30` aberta. Nunca volta. Prison Door da Lost Bastille 10→30 no mesmo
    intervalo em que a Bastille Key entrou no inventário; Arch Gate do Executioner's Chariot 10→20 no intervalo da alma do
    chefe; Iron Door de Huntsman's Copse e três Iron Gates de m10_29 10→30. Outros valores (21, 32, 40, 50: portas
    giratórias e as de madeira de Heide) ficam **sem estado**.
  - Alavanca: `10` não puxada; `20`/`30` puxada (13 transições 10→20/30 só quando o personagem estava na área).
  - Baú: `≥ 80` aberto (`80`, `84`, `100`); `10`, `20`, `21`, `24` fechado. Fire Seed, Poison Stone, Heavy Crossbow
    (Harvest Valley) e Ricard's Rapier, Sublime Bone Dust (Huntsman's Copse): 20/10 → 80 no intervalo em que o item
    entrou. A Bonfire Ascetic fecha de novo (80 → 20 e 100 → 20).
- **Item pego (baú e cadáver/chão)**: o lote aparece no vetor de lotes da área quando o jogo carrega aquele trecho (antes
  de pegar) e o estado paralelo tem o bit `0x1000000` **ligado quando foi pego** (`0x100c03` → `0x1100003`; os bits
  `0x3FF << 10` são os itens que ainda estão lá, os de baixo os itens do lote). 155 lotes viraram "pego" entre as cópias e
  137 tinham um item que entrou no inventário no mesmo intervalo (os outros 18: Torch, Lifegem, Estus Flask Shard, Fire
  Seed, Human Effigy, gastos ou entregues no mesmo intervalo), em 9 áreas. Lote fora do vetor = **sem estado** (a área ou
  o trecho ainda não foi carregado). A Bonfire Ascetic desliga o bit e troca o lote pelo do NG+ (`10186020` → `10186021`):
  o lote do mapa casa pelo número sem o último dígito.
- **Outra tabela** (início do bloco, registros de `0xB10`): por área, a lista ordenada dos **geradores** de inimigo (os
  IDs são os mesmos do `generatorlocation`), base para "inimigo que não volta mais" (12 mortes) num passo futuro.
- **Não achado**: porta que só abre por evento sem mudar o estado (alguns 10 continuam 10 depois de abertos? nenhum caso
  visto), elevador (32/33 = andar em que está; não é "aberto"), Pharros (10→20 nove vezes, sem confirmação de qual
  pedra foi usada): ficam **sem estado**.

## Peças de mapa montadas com ossos (2026-10-11, Iron Keep)

Print do jogo × página na fogueira Threshold Bridge: no jogo, um patamar de pedra com balaustrada, uma escada subindo à
direita e uma ponte em arco por cima; na página, a fogueira "flutuava" na lava, sem piso, sem degraus (só o corrimão),
com lajes escuras soltas no ar. A correção anterior (`a90a082`, nomes atrás da parede) só tratou os rótulos; o cenário
estava mesmo errado.

- **Causa**: peça de mapa do DS2 também pode ter ossos. O artista monta a peça com cópias de partes menores, e cada cópia
  é um osso: em `m0002`, 62 ossos com nomes como `階段_1` (escada), `鉄柵_002` (grade de ferro) e `Floor`. A malha é rígida
  e fica no espaço do osso (o 4º byte da normal escolhe o osso na lista da malha), igual aos objetos e personagens. O
  extrator só aplicava os ossos em objetos e personagens ("as peças de mapa já vêm no lugar"), e as cópias ficavam todas
  na origem do modelo.
- **Prova** (sem depender de olhar a tela): a caixa do cabeçalho do FLVER. Com os ossos, os vértices de cada modelo caem
  dentro dela; sem eles, m0001, m0002, m0003 e m0005–m0008 da Iron Keep passavam de 14 m a 89 m da caixa. Nas 28 áreas:
  24 modelos de mapa mudam com os ossos, 23 passam a caber na caixa e nenhum fica pior (o outro já cabia dos dois jeitos;
  em Shrine of Amana a caixa calculada com os ossos é igual à do cabeçalho nos 7 modelos com ossos). Áreas afetadas além
  da Iron Keep: Majula, Forest of Fallen Giants, Huntsman's Copse, The Gutter, Shrine of Amana e Undead Crypt.
- **Correção**: `ler_flver` aplica os ossos sempre (peça de mapa, objeto e personagem) e a caixa sai dos vértices;
  `CENA_VERSAO` 6 refaz a cena de toda área já extraída na próxima abertura. Embaixo da Threshold Bridge, antes só havia
  lava (y 165,11); agora há o piso `floor_05_d` em y 165,64, na altura da fogueira (165,6). Teste com o jogo instalado:
  `test_iron_keep_pecas_de_mapa_no_lugar_e_chao_na_threshold_bridge`.

## Rota × portas (2026-10-11, Task 4 do plano)

- **Vão real da porta** (responde ao "centro do modelo não conferido" de "Limites", acima): pela caixa dos modelos na
  cena 3D, a porta de dobradiça do jogo tem a origem **na dobradiça** e o vão ao longo de +x (Wooden Door, Iron Door,
  Prison Door: x de 0 a 1,4 m), enquanto grade e portão são centrados (Iron Bars: x de -1,53 a 1,53; Large Iron Bars
  Gate: -2,34 a 2,34). Uma grade (Iron Bars da arena da Lost Bastille) tem o vão no z do modelo: vale o lado mais
  comprido da caixa no chão.
- `ds2mapa.portas_no_caminho` cruza a rota com o vão de cada porta (caixa do modelo quando a cena já foi extraída,
  senão centrada com a largura pelo nome, como o `mapa.js`) e com a altura (entre 1,5 m abaixo da base e o topo); a
  rota do servidor e as rotas do plano trazem `portas` na ordem do caminho. Conferido com o jogo: da fogueira Straid's
  Cell até a Petrified Dragon Bone a rota passa pelas duas Prison Doors (7,6 m e 14,1 m).
- Página: o aviso da rota diz "Passa por N portas" e, pelo save, "aberta no seu save" ou "fechada no seu save, abre com
  X" (só quando a chave é conhecida). **Fechada não é trancada**: o save só diz que a porta ainda não abriu.
- Fica para depois: o desenho da porta no 2D continua centrado na posição (sem a cena na hora de montar a página, o
  vão real não é conhecido); a chave das portas comuns é a Parte B do plano.

## Chave das portas comuns pelo script de evento (2026-10-11, Task 5 do plano)

- **Onde**: `/ezstate/event_<área>.esd` (EzState "fsSL", 64 bits; leitor em `ds2esd.py`, formato pelo SoulsFormats como
  referência). Cada máquina de estado é um evento; a porta com chave chama a máquina comum (banco 6, `0x7FFFFFFA`) com
  `(mensagem, mensagem, ID da chave, flag)`, e o ID da chave aparece como constante int32 (`0x82` + int32).
- **Evento → porta**: o ID da máquina é a linha do `eventparam_<área>.param` (16 bytes: evento, **ref da parte do MSB**,
  `0x02000000`, 1). Ex.: Lost Bastille, evento 18010 → ref 10160432 (`o00_0316_0002`).
- **Conferido**: nas 28 áreas, 29 portas ganham chave pelo evento (e a Rotunda Switch de Majula, que fica de fora por
  ser alavanca). As 4 portas cujo nome do modelo cita a chave (Large Stone Door da Forgotten Key em Majula e duas no
  Gutter, Large Door da Key to King's Passage) dão a mesma chave pelo evento. Na wiki: Bastille Key abre a cela ao lado
  da do Straid (o evento 18010 aponta essa) e outras celas da Lost Bastille/Sinners' Rise (7 pelo evento); Brightstone
  Key abre uma sala em Tseldora (2 portas, os dois lados); Antiquated Key abre a porta de madeira do primeiro pátio da
  Lost Bastille (`o00_0301_0000`).
- **Na extração** (`EXTRACAO_VERSAO` 9): `objetos[].chave` vem do nome do modelo e, se ele não diz, do evento;
  `chave_fonte` = `modelo` ou `evento`. A página mostra "Abre com" e onde pegar a chave para essas portas, e o popover
  diz de onde veio a chave. Evento com mais de uma chave, sem linha no `eventparam` ou ESD que não abre: sem chave.

## Personagens na pose de espera (2026-10-11, Tasks 7/8 do plano)

- **Formato**: o DS2 SotFS não usa Havok para animar personagens, usa o **Morpheme 4** da NaturalMotion:
  `/morpheme4/chr/<cXXXX>.anibnd.dcx` (BND4) com `<cXXXX>.nmb` (a rede e o rig) e as animações `.nsa`
  (`a00_00_0000_Idle_untitled_<hash>.nsa`; 234 no Hollow Soldier). As ferramentas públicas que leem isso usam o runtime
  da NaturalMotion (código proprietário); `ds2anim.py` foi escrito a partir dos bytes, sem esse código. Layout no
  docstring do módulo.
- **Rig ↔ FLVER**: o rig do `.nmb` é o esqueleto do FLVER com Y e Z trocados (posição FLVER = (x, z, y), rotação =
  (−qx, −qz, −qy, qw)); os ossos casam pelo nome. Prova: aplicando a pose de referência do rig na malha do FLVER, os
  vértices não mudam (desvio ≤ 0,00001 m no Hollow Soldier, Pursuer, Straid e Lucatiel).
- **NSA**: canais parados (u16×3 numa faixa) e amostrados por seção (posição u32 11:11:10, rotação u16×3 em tangente de
  um quarto do ângulo, média de 8 bits + conjunto de quantização por canal); canal c = osso c+1. Conferido: no quadro 0
  do Idle os dedos dos pés ficam em z ≈ 0 em 52 dos 53 personagens das cenas extraídas (o outro não tem Idle).
- **Na cena** (`CENA_VERSAO` 7): cada inimigo e NPC com modelo sai no quadro 0 da espera (`a00_00_0000_Idle`), com a
  malha com pele posta pelos pesos (soma dos pesos × mundo posado × inverso do mundo de referência). Modelo variante sem
  animação própria usa a do modelo base (c7643 → c7640). Sem animação legível, fica a pose de referência e
  `personagens[c].sem_pose` diz por quê. Custo: +0,3 MB e +0,7 s na Lost Bastille.
- **Sentado × em pé (falta a regra)**: cada NPC tem animações `a75_01_71x0_Wep01_StartUp_0N` cujo quadro 0 é a pose
  em que ele espera (Straid StartUp_01: pelve a 0,11 m, sentado no chão; McDuff StartUp_01/03: pelve a 0,78 m, sentado
  num banco; Lucatiel StartUp_03: agachada). Qual delas cada gerador usa **não foi achado**: não está nos scripts de
  evento nem de conversa (nenhuma constante 7100–7131) e os campos do `GeneratorParam` não deram uma regra clara. Até
  achar, todos ficam na espera em pé.
- Animação em movimento (laço do Idle no 3D) fica para depois: a pose estática já tira a pose T; animar exige mandar os
  pesos e os ossos para a página.
