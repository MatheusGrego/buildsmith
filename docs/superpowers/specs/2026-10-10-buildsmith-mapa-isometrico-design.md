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
