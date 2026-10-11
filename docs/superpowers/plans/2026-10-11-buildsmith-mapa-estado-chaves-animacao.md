# Mapa: estado pelo save, chave das portas e inimigos animados — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fechar os três buracos que ficaram do mapa 3D: (A) o mapa mostrar o que já mudou no seu mundo (porta aberta, alavanca puxada, baú aberto, item já pego naquele ponto) e a rota avisar quando passa por porta trancada; (B) dizer qual chave abre cada porta, não só as que o nome do modelo cita; (C) inimigos animados (parados em pose de ataque/espera, não na pose de referência do modelo).

**Architecture:** Mesmo caminho de hoje: Python lê o jogo e o save (`ds2save.py`, `ds2mapa.py`, `ds2cena.py`) e grava cache em `~/.buildsmith/cache/ds2/`; o servidor local (`app/serve.py`) expõe o que é por personagem (save) e o que é por área (jogo); a página (`mapa.js`, `iso.js`, `vivo.js`) só desenha. Cada parte começa por um **spike com o jogo instalado** com critério de saída: sem confirmação em pelo menos dois casos, a parte para e o achado vai para o spec (como foi feito com as tochas).

**Tech Stack:** Python 3 (struct, zlib, pycryptodome), three.js r160 (vendor), JavaScript ES6+, pytest, node para as funções puras do JS, Chromium (Playwright) para a página.

**Spec:** `docs/superpowers/specs/2026-10-10-buildsmith-mapa-isometrico-design.md` (seções "Entidades em escala…", "Modelos reais…", "Save ao vivo…" e "Próximos passos").

## Global Constraints

- Sem bibliotecas pesadas (sem numpy, sem Pillow): biblioteca padrão + `pycryptodome`.
- Todo fato com fonte: tabela do jogo, save ou wiki. Nome/valor descoberto por engenharia reversa só entra depois de conferido em pelo menos dois casos com o jogo; até lá fica no spec como hipótese.
- Nada que precise do jogo roda nos testes comuns: dados sintéticos; testes com o jogo pulados sem ele (`GAME / "GameDataEbl.bhd"`), como os de hoje.
- O save só é lido; nunca gravado.
- Cache com versão (`EXTRACAO_VERSAO`, `CENA_VERSAO`) e gravação atômica; mudou o formato, sobe a versão.
- Página publicada (sem servidor) e navegador sem WebGL continuam funcionando: o que depende do save ou do 3D some com aviso, não quebra.
- `pytest -q` 100% verde a cada commit.

## Review Focus

1. **Flag errada vira mentira na tela:** porta "aberta" que está trancada é pior que não dizer nada. Só mostra estado com regra confirmada; o resto fica "sem estado".
2. **Save sendo gravado:** leitura no meio da gravação do jogo não pode derrubar o servidor nem piscar estado na página (manter o último bom).
3. **Rota × porta:** o cruzamento da rota com a porta usa a largura real da porta (não o centro); porta aberta no save não gera aviso.
4. **Chave por evento:** o vínculo chave → porta vem do script do jogo (ou da wiki pelo plano), nunca de "porta mais perto da chave".
5. **Animação pesada:** dezenas de inimigos animados não podem derrubar o quadro; limite de quantos animam ao mesmo tempo e o resto parado.
6. **Objeto que só existe em evento:** lápide de NPC, ajudantes "Dummy", escada que o NPC monta: não entram no cenário sem o estado do save que diz que estão lá.

## Retorno do primeiro teste no jogo (2026-10-11) e o que já foi feito na 0.19.0

| Visto no jogo | Causa | Situação |
|---|---|---|
| Baú virava a caixa de reserva (laranja) | bug no leitor de FLVER: em modelo rígido com várias malhas, a lista de matrizes de osso sobrescrevia a de materiais e a 2ª malha quebrava o modelo inteiro | **corrigido** (teste `test_flver_rigido_com_varias_malhas_mantem_os_materiais`); `CENA_VERSAO` 4 refaz as cenas |
| Por que um objeto ficou com a forma de reserva | não aparecia em lugar nenhum | **feito**: o popover do objeto no 3D diz o motivo (`cena.json` → `sem_modelo`); `ds2cena.py modelo --modelo oXX_XXXX` mostra o binder e cada malha |
| NPC virava uma lápide | a lápide `o00_9050` (o jogo só mostra quando o NPC morre) entrava no cenário com os outros objetos | **feito**: lápide e ajudantes "Dummy" fora do cenário (`ds2nomes.fora_da_cena`); NPC com modelo próprio (Straid `c7680`, McDuff `c7643`, Lucatiel `c7520`) aparece com ele no 3D pelo filtro NPCs |
| Inimigos em pose T | o modelo vem sem animação (pose de referência) | **Parte C** (Tasks 7 e 8) |
| NPC humano sem modelo próprio | usa o corpo humano `c0001` com peças de armadura | **Task 8b** |
| Lápide quando o NPC morreu | precisa do estado do NPC no save | **Task 3b** |

---

## Parte A — Estado do mundo pelo save

### Task 1: Spike — onde o save guarda porta, alavanca, baú e item pego

**Files:**
- Modify: `skills/ds2-save/scripts/ds2save.py` (CLI `blocos-diff`)
- Create: `tests/test_ds2save_blocos.py`
- Modify: `docs/superpowers/specs/2026-10-10-buildsmith-mapa-isometrico-design.md` (fatos descobertos)

**Interfaces:**
- Produces:
  - `ds2save.blocos(path) -> dict[str, bytes]` (cada `USER_DATA0xx` decifrado)
  - `ds2save.diff_blocos(antes: dict, depois: dict) -> list[dict]` com `{bloco, offset, bit, antes, depois}`
  - CLI: `ds2save.py blocos-diff --antes A.sl2 --depois B.sl2 [--bloco USER_DATA011]`

- [ ] **Step 1: Teste falhando** — dois saves sintéticos (com `conftest.build_bnd4`) que diferem em 3 bits de `USER_DATA011` e 1 byte de `USER_DATA001`; `diff_blocos` devolve exatamente essas 4 mudanças, com bit e bloco.
- [ ] **Step 2: Rodar e ver falhar** — `pytest tests/test_ds2save_blocos.py -v` → FAIL (função não existe).
- [ ] **Step 3: Implementar** `blocos` e `diff_blocos` (reaproveita `_read_entries`); CLI imprime JSON agrupado por bloco.
- [ ] **Step 4: Rodar e ver passar.**
- [ ] **Step 5: Spike com o jogo** (manual, no PC com o DS2): copiar o save; abrir um baú conhecido na Lost Bastille (lote do `ds2mapa.py extrair`), sair para o menu, copiar de novo; `blocos-diff`. Repetir com: um segundo baú, um item no chão, uma porta de cela (Bastille Key), uma alavanca, e o mesmo em outra área. Procurar o padrão: bit por linha do `mapobjectinstanceparam_<área>` (ordem da linha?), flag por evento (`eventparam_<área>`: `Event ID` + `Event Flag ID`, Paramdex), ou faixa por área no bloco de mundo.
- [ ] **Step 6: Critério de saída** — regra explicada e conferida em ≥ 2 objetos de cada tipo em ≥ 2 áreas. Escrever no spec ("Fatos descobertos", com offsets e exemplos). Sem regra: escrever o que foi tentado e parar a Parte A aqui.
- [ ] **Step 7: Commit**

```bash
git add skills/ds2-save/scripts/ds2save.py tests/test_ds2save_blocos.py docs/superpowers/specs/2026-10-10-buildsmith-mapa-isometrico-design.md
git commit -m "feat(save): diff de blocos do save para achar o estado de portas, baús e itens"
```

---

### Task 2: Estado dos objetos e dos lotes pela regra achada

**Files:**
- Modify: `skills/ds2-save/scripts/ds2save.py`
- Modify: `skills/ds2-save/scripts/ds2mapa.py` (cada objeto/lote guarda a chave do estado: linha da instância, evento ou flag, conforme o spike)
- Modify: `tests/test_ds2save.py`, `tests/test_ds2mapa.py`

**Interfaces:**
- Consumes: regra do Task 1; `ds2mapa.montar_objetos`, `ds2mapa.marcar_itens`
- Produces:
  - `ds2mapa` (`EXTRACAO_VERSAO` + 1): `objetos[].estado_ref` e `itens[].estado_ref`
  - `ds2save.estado_mundo(world: bytes, refs: list) -> dict[ref, bool]` (aberto/pego = True)

- [ ] **Step 1: Teste falhando** — bloco de mundo sintético com os bits da regra ligados para 2 refs; `estado_mundo` devolve `True` só nelas; ref fora da faixa = `None` (sem estado), nunca `False`.
- [ ] **Step 2: Rodar e ver falhar.**
- [ ] **Step 3: Implementar** a leitura e o `estado_ref` na extração (teste sintético do `montar_objetos` com a ref).
- [ ] **Step 4: Rodar e ver passar** (+ teste com o jogo, pulado sem ele: a porta/baú do spike sai com o estado certo).
- [ ] **Step 5: Commit** — `feat(mapa): estado de portas, baús e itens pelo save`

---

### Task 3: Servidor e página mostram o estado

**Files:**
- Modify: `app/serve.py` (`MapaVivo.estado_area(slug, area)`, `GET /api/ds2/<personagem>/mundo?area=<area>`)
- Modify: `skills/build-page/scripts/mapas_pagina.py` (leva `estado_ref` para a página)
- Modify: `skills/build-page/template/mapa.js`, `skills/build-page/template/iso.js`, `skills/build-page/template/pagina.css`
- Modify: `tests/test_serve.py`, `tests/test_prepare_page.py`, `tests/test_injection.py`

**Interfaces:**
- Consumes: `ds2save.estado_mundo`
- Produces: `GET /api/ds2/<personagem>/mundo?area=m10_16_00_00` → `{"objetos": {parte: true|false}, "lotes": {lote: true|false}}` (só refs com regra; relê quando o save muda; área validada por `AREA_OK`)

- [ ] **Step 1: Testes falhando** — rota com save sintético (200, 404 personagem, 400 área inválida); `mapa.js` puro: `estadoObjeto(o, mundo)` → "aberta"/"fechada"/null.
- [ ] **Step 2: Rodar e ver falhar.**
- [ ] **Step 3: Implementar** — a página consulta junto com a posição (mesmo intervalo, só a área aberta); 2D: porta aberta tracejada e clara, baú aberto cinza, item já pego com ✓ cinza ("já pegou aqui"); 3D: realce verde para aberto; popover diz "aberta no seu save".
- [ ] **Step 4: Rodar e ver passar** + Chromium com cena e save sintéticos (porta aberta/fechada, baú aberto).
- [ ] **Step 5: Commit** — `feat(mapa): portas, baús e itens já usados no seu save`

---

### Task 3b: Lápide do NPC morto e objetos de evento pelo save

**Files:**
- Modify: `skills/ds2-save/scripts/ds2save.py`, `skills/ds2-save/scripts/ds2mapa.py`, `skills/ds2-save/scripts/ds2cena.py`, `skills/ds2-save/scripts/ds2nomes.py`
- Modify: `skills/build-page/template/mapa.js`, `skills/build-page/template/iso.js`
- Modify: `tests/test_ds2save.py`, `tests/test_ds2nomes.py`, `tests/test_injection.py`

**Interfaces:**
- Consumes: regra do Task 1 (flags de evento) e `npcs[].id`
- Produces: `npcs[].morto` no `/api/ds2/<personagem>/mundo`; a lápide (`o00_9050`) volta para a cena como objeto **condicional** (`cena.json` → `instancias[].evento`), desenhada só quando o save diz que o NPC morreu (e o retrato do NPC some).

- [ ] **Step 1: Teste falhando** — `fora_da_cena` deixa de excluir a lápide e passa a marcá-la condicional; NPC com flag de morte ligada no mundo sintético sai `morto: true`.
- [ ] **Step 2: Rodar e ver falhar.**
- [ ] **Step 3: Implementar** (flag de morte do NPC pelo spike do Task 1: matar/ver morrer um NPC e `blocos-diff`).
- [ ] **Step 4: Rodar e ver passar** + Chromium (NPC vivo: modelo/retrato; morto: lápide).
- [ ] **Step 5: Commit** — `feat(mapa): lápide do NPC morto pelo save`

---

### Task 4: Rota avisa porta trancada no caminho

**Files:**
- Modify: `skills/ds2-save/scripts/ds2mapa.py` (função pura `portas_no_caminho`)
- Modify: `app/serve.py` (`/api/ds2/rota` devolve `portas`)
- Modify: `skills/build-page/template/mapa.js`
- Modify: `tests/test_ds2mapa.py`, `tests/test_serve.py`

**Interfaces:**
- Produces: `ds2mapa.portas_no_caminho(pontos: list, objetos: list, largura=None) -> list[dict]` — porta cuja largura (segmento pelo eixo x local girado pela rotação do MSB, largura de `mapa.js dimsObjeto`) cruza a polilinha da rota, na ordem do caminho.

- [ ] **Step 1: Teste falhando** — rota reta cruzando uma porta de 2,2 m girada 90°; outra porta ao lado (não cruza); porta acima/abaixo do andar (altura) não conta.
- [ ] **Step 2: Rodar e ver falhar.**
- [ ] **Step 3: Implementar** e levar na resposta da rota; a página escreve "passa pela porta X" e, com o estado do Task 3, "trancada no seu save: abre com Y" (chave do Task 6) ou "aberta".
- [ ] **Step 4: Rodar e ver passar.**
- [ ] **Step 5: Commit** — `feat(rota): portas no caminho e se estão trancadas`

---

## Parte B — Qual chave abre cada porta

### Task 5: Spike — chave nos scripts de evento (EzState)

**Files:**
- Create: `skills/ds2-save/scripts/ds2esd.py` (leitor mínimo de ESD: estados, condições e constantes)
- Create: `tests/test_ds2esd.py`
- Modify: spec (fatos descobertos)

**Interfaces:**
- Produces:
  - `ds2esd.ler_esd(data: bytes) -> dict` (máquinas, estados, condições com o bytecode das expressões)
  - `ds2esd.constantes(expr: bytes) -> list[int]` (inteiros empilhados na expressão)
  - CLI: `ds2esd.py chaves --area m10_16_00_00` → eventos que testam um ID de `games/ds2/ids/KeyItems.txt`

- [ ] **Step 1: Teste falhando** — ESD sintético mínimo (1 máquina, 2 estados, 1 condição cuja expressão empilha `50800000` e um ID de evento); `constantes` acha os dois.
- [ ] **Step 2: Rodar e ver falhar.**
- [ ] **Step 3: Implementar** o leitor pelo formato do SoulsFormats/ESDLang (MIT, referência; não copiar código): cabeçalho, tabelas de máquinas/estados/condições/comandos, expressões como bytes.
- [ ] **Step 4: Rodar e ver passar.**
- [ ] **Step 5: Spike com o jogo** — `/ezstate/event_m10_16_00_00.esd`: achar os estados que testam a Bastille Key (`50800000`) e o que mais aparece junto (ID de evento, de objeto, flag). Ligar o evento à posição por `eventlocation_m10_16_00_00.param` (posição do evento) ou pela parte do MSB, e daí à porta mais perto **do evento** (não da chave).
- [ ] **Step 6: Critério de saída** — ≥ 3 portas com a chave conferida na wiki (ex.: cela do Straid com Bastille Key, porta da Forgotten Key em Majula, Brightstone Key em Tseldora). Sem isso, documentar e seguir só com o Task 6.
- [ ] **Step 7: Commit** — `feat(eventos): leitor de ESD e chaves pedidas pelos eventos`

---

### Task 6: Chave da porta pelo plano (wiki) e pelo evento

**Files:**
- Modify: `skills/build-page/scripts/validate_plano.py` (nó `porta`, ponto `tipo: "objeto"`, `ref` = parte do MSB)
- Modify: `skills/ds2-save/scripts/ds2mapa.py` (CLI `objetos --area A [--cat porta] [--perto item:LOTE|fogueira:ID]`; `ponto_de` aceita `objeto`; chave do evento quando o Task 5 confirmou)
- Modify: `skills/build-page/scripts/mapas_pagina.py`
- Modify: `skills/build/SKILL.md` (como achar a porta e citar a chave com a wiki)
- Modify: `skills/build-page/template/mapa.js`
- Modify: `tests/test_validate_plano.py`, `tests/test_ds2mapa.py`, `tests/test_prepare_page.py`

**Interfaces:**
- Produces:
  - nó de fluxo `{"tipo": "porta", "nome": "Cela do Straid", "chave": "Bastille Key", "link": <wiki>, "ponto": {"area", "tipo": "objeto", "ref": "<parte>"}}`
  - `objetos[].chave` também com `fonte: "modelo" | "evento" | "plano"`

- [ ] **Step 1: Testes falhando** — validador aceita o nó `porta` e recusa chave que não é item do jogo; `ponto_de(area, "objeto", parte)`; a porta do plano sai no `mapas/<area>.json` com a chave e a fonte.
- [ ] **Step 2: Rodar e ver falhar.**
- [ ] **Step 3: Implementar**; a rota do passo passa pela porta (pino no lugar da porta, popover "abre com" + onde pegar).
- [ ] **Step 4: Rodar e ver passar** + Chromium.
- [ ] **Step 5: Commit** — `feat(plano): porta com chave no fluxo e no mapa`

---

## Parte C — Inimigos animados

### Task 7: Spike — esqueleto e animação do personagem

**Files:**
- Modify: `skills/ds2-save/scripts/ds2cena.py` (pesos e índices de osso do FLVER; esqueleto no `cena.json`)
- Create: `skills/ds2-save/scripts/ds2anim.py` (leitor do `.anibnd`)
- Create: `tests/test_ds2anim.py`
- Modify: spec

**Interfaces:**
- Produces:
  - `geo.bin`: por submalha de personagem, índices (u8×4) e pesos (u8×4 normalizados) de osso; `cena.json` → `personagens[c].ossos` (pai, T, R, S)
  - `ds2anim.listar(anibnd: bytes) -> list[str]` e, se o formato abrir, `ds2anim.pose(anibnd, nome, t) -> list[matriz]`

- [ ] **Step 1: Teste falhando** — FLVER sintético com BoneIndices (tipo 0x2F/0x18) e BoneWeights (0x13/0x1A): o leitor devolve índices e pesos; a pose de referência reconstruída pelos ossos dá os mesmos vértices de hoje.
- [ ] **Step 2: Rodar e ver falhar.**
- [ ] **Step 3: Implementar** pesos/índices e o esqueleto no cache (`CENA_VERSAO` + 1).
- [ ] **Step 4: Rodar e ver passar.**
- [ ] **Step 5: Spike com o jogo** — abrir `/morpheme4/chr/c1020.anibnd.dcx`: listar o conteúdo (Morpheme e/ou Havok `.hkx`), achar a animação de espera. Critério de saída: uma pose de espera do Hollow Soldier (c1020) aplicada no 3D sem o modelo "explodir". Sem isso, documentar e ficar só com o Task 8 na pose de referência.
- [ ] **Step 6: Commit** — `feat(cena): esqueleto e pesos dos personagens; leitor de anibnd`

---

### Task 8: Inimigo animado no 3D

**Files:**
- Modify: `skills/build-page/template/iso.js` (`THREE.SkinnedMesh` por inimigo perto; instâncias paradas para o resto)
- Modify: `skills/build-page/template/mapa.js`
- Modify: `tests/test_injection.py`

**Interfaces:**
- Consumes: esqueleto/pesos do Task 7 e a pose (`/api/ds2/cena/<area>/anim/<c>.json` se o spike abriu)
- Produces: `iso.setEntidades` aceita `animar: true`; até `ANIMADOS_MAX` (≈ 40) inimigos mais perto do centro animam, o resto fica instanciado e parado.

- [ ] **Step 1: Teste falhando (node)** — escolha dos animados pela distância ao centro com limite; matriz de osso composta igual à do Python.
- [ ] **Step 2: Rodar e ver falhar.**
- [ ] **Step 3: Implementar**; realce (H) e filtro Inimigos continuam valendo para os animados.
- [ ] **Step 4: Rodar e ver passar** + Chromium (cena sintética com 1 personagem de 2 ossos girando).
- [ ] **Step 5: Commit** — `feat(mapa-3d): inimigos animados perto da câmera`

---

### Task 8b: NPC humano com o corpo e a armadura dele

**Files:**
- Modify: `skills/ds2-save/scripts/ds2cena.py` (corpo `c0001` + peças de `/model/parts/{head,body,arm,leg}/` e arma de `/model/parts/weapon/`)
- Modify: `skills/ds2-save/scripts/ds2mapa.py` (NPC sem modelo próprio: linha do `NpcPlayerStatusParam` com Head/Chest/Hands/Legs Armor ID e armas, definição do Paramdex)
- Modify: `skills/build-page/template/iso.js`, `skills/build-page/template/mapa.js`
- Modify: `tests/test_ds2cena.py`, `tests/test_ds2mapa.py`

**Interfaces:**
- Produces: `npcs[].pecas = {"cabeca": id, "peito": id, "maos": id, "pernas": id, "R": id, "L": id}`; a cena junta corpo + peças num modelo `npc_<id>` (mesmo esqueleto do `c0001`).

- [ ] **Step 1: Spike com o jogo** — achar a linha do `NpcPlayerStatusParam` de um NPC humano (ex.: Carhillion of the Fold, sem modelo próprio) e o arquivo de cada peça em `/model/parts/` (lista de arquivos do Smithbox); conferir com a wiki o equipamento do NPC.
- [ ] **Step 2: Testes falhando** — peças sintéticas (FLVER de 1 malha cada) juntas no modelo do NPC com o esqueleto do corpo.
- [ ] **Step 3: Implementar** (parte que não abre fica de fora, com aviso; sem corpo, fica só o retrato).
- [ ] **Step 4: Rodar e ver passar** + Chromium.
- [ ] **Step 5: Commit** — `feat(mapa-3d): NPC humano com o corpo e a armadura dele`

---

### Task 9: Docs, versão e conferência

**Files:**
- Modify: `README.md`, `skills/ds2-save/SKILL.md`, `skills/build-page/SKILL.md`, `skills/build/SKILL.md`, spec, `.claude-plugin/plugin.json`

- [ ] **Step 1:** Documentar cada parte entregue (e as que pararam no spike, com o porquê).
- [ ] **Step 2:** `python -m pytest -q` verde; com o jogo: `pytest -k real`.
- [ ] **Step 3:** Subir a versão do plugin (uma por parte entregue).
- [ ] **Step 4: Commit** — `docs: estado do mundo, chaves e animação no mapa; versão`
