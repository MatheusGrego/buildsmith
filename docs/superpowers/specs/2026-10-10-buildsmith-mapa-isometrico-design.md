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
