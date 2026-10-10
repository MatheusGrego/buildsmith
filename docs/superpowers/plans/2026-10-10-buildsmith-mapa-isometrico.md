# Mapa Isométrico do DS2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar visualização isométrica 3D interativa das áreas de Dark Souls II SotFS com o cenário real (paredes, chão, escadas) e texturas do jogo, corte de altura por andar, alternância 2D/Isométrico e sincronização de pontos/jogador/rota.

**Architecture:** Python extrai sob demanda do jogo (`.mapbhd`/`.mapbdt`, `.tpfbhd`/`.tpfbdt`, `.msb`) os modelos FLVER2, matrizes de instâncias e texturas DDS compactas para `~/.buildsmith/cache/ds2/cena/<area>/`. O servidor local `serve.py` expõe a cena via `/api/ds2/cena/...`, e o frontend (`iso.js` com Three.js ortográfico) renderiza a cena em ângulo isométrico com plano de corte por andar e sobreposição dos marcadores já existentes do `mapa.js`.

**Tech Stack:** Python 3 (struct, zlib, pycryptodome), Three.js r160 (ESM bundle standalone), WebGL com extensões S3TC/DXT, JavaScript ES6+.

**Spec:** `docs/superpowers/specs/2026-10-10-buildsmith-mapa-isometrico-design.md`

## Global Constraints

- Python sem bibliotecas pesadas externas (sem numpy, sem scipy, sem Pillow); usa apenas biblioteca padrão + `pycryptodome`.
- Three.js incluído como arquivo vendor único em `skills/build-page/template/vendor/three.module.min.js` (sem build/bundler, roda offline).
- Orçamento por área: máximo 30 MB em disco e menos de 60s de extração inicial.
- Cache atômico com verificação de assinatura dos arquivos do jogo e versão `CENA_VERSAO`.
- Fallback gracioso: se o jogo não estiver instalado ou o navegador não suportar WebGL S3TC, o mapa 2D continua funcionando sem erros.
- A suíte de testes `pytest` deve permanecer 100% verde.

## Review Focus

1. **Área sem modelos/não encontrada:** Requisições para `/api/ds2/cena/<area>/...` de área inexistente devem devolver 404 limpo com JSON explicativo, sem travar o servidor.
2. **Câmera isométrica em 4 rotações (0°, 90°, 180°, 270°):** A projeção dos marcadores 2D ("Você", fogueiras, itens) deve se alinhar perfeitamente com a geometria 3D em todos os 4 ângulos.
3. **Plano de corte por andar:** Quando o usuário seleciona um andar específico, o plano de clipping oculta tetos e andares superiores sem furar o chão do andar atual.
4. **Extração sob demanda concorrente:** Se múltiplos requests de extração para a mesma área chegarem simultaneamente, apenas uma extração executa e as outras aguardam ou reutilizam o resultado.
5. **DDS sem mipmaps excessivos:** Texturas 1024px cortadas no cabeçalho DDS para 512px para respeitar a cota de 30 MB sem decodificar pixels na CPU.

---

### Task 1: Leitor de FLVER2 e BHF4 em `ds2cena.py`

**Files:**
- Create: `skills/ds2-save/scripts/ds2cena.py`
- Create: `tests/test_ds2cena.py`

**Interfaces:**
- Produces:
  - `ds2cena.ler_bhf4(bhd_bytes: bytes, bdt_bytes: bytes, filtro_ext: str = None) -> dict[str, bytes]`
  - `ds2cena.ler_flver(flver_bytes: bytes) -> dict` contendo `version`, `bb`, `materiais`, `malhas` (com vértices, normais, uvs, índices e textura difusa).

- [ ] **Step 1: Escrever teste falhando para `ler_bhf4` e `ler_flver` com dados sintéticos**

Criar `tests/test_ds2cena.py` com testes que constroem um BHF4 sintético e um FLVER2 mínimo válido (1 submalha, 3 vértices com posição float32, normal int8, uv half-float, e 1 triângulo).

- [ ] **Step 2: Rodar teste para verificar que falha**

Run: `pytest tests/test_ds2cena.py -v`
Expected: FAIL (módulo `ds2cena` não encontrado)

- [ ] **Step 3: Implementar `ler_bhf4` e `ler_flver` em `ds2cena.py`**

Implementar a leitura dos cabeçalhos BHF4/BDF4 e descompressão DCX de arquivos selecionados, além da decodificação de cabeçalho FLVER2, submalhas, layouts de vértices (semânticas 0=Pos, 3=Norm, 5=UV) e listas de faces.

- [ ] **Step 4: Rodar testes para verificar aprovação**

Run: `pytest tests/test_ds2cena.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add skills/ds2-save/scripts/ds2cena.py tests/test_ds2cena.py
git commit -m "feat: leitor de FLVER2 e BHF4 para extração de cena do DS2"
```

---

### Task 2: Extração de Texturas TPF/DDS e Compactação de Geometria

**Files:**
- Modify: `skills/ds2-save/scripts/ds2cena.py`
- Modify: `tests/test_ds2cena.py`

**Interfaces:**
- Consumes: `ds2cena.ler_flver`
- Produces:
  - `ds2cena.extrair_dds_tpf(tpf_bytes: bytes, max_dim: int = 512) -> bytes | None`
  - `ds2cena.empacotar_geometria(modelos_flver: dict) -> tuple[dict, bytes]` (metadados de offset/tamanho e buffer binário `geo.bin`).

- [ ] **Step 1: Escrever testes falhando para recorte de cabeçalho DDS e empacotamento binário**

Adicionar teste em `tests/test_ds2cena.py` verificando que um TPF sintético com DDS DXT1 1024x1024 tem seus mipmaps maiores ajustados para 512x512 reescrevendo o cabeçalho DDS, e que `empacotar_geometria` empacota posições e índices em buffers contíguos.

- [ ] **Step 2: Rodar teste para verificar falha**

Run: `pytest tests/test_ds2cena.py -k "test_dds or test_empacotar" -v`
Expected: FAIL

- [ ] **Step 3: Implementar recorte de DDS e empacotamento binário em `ds2cena.py`**

Adicionar as funções de extração de DDS de dentro dos contêineres TPF e empacotamento das malhas em um buffer binário compacto único (`geo.bin`), com offsets e contagens salvos no dicionário de modelos.

- [ ] **Step 4: Rodar testes**

Run: `pytest tests/test_ds2cena.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add skills/ds2-save/scripts/ds2cena.py tests/test_ds2cena.py
git commit -m "feat: extração de texturas DDS e empacotamento de geometria"
```

---

### Task 3: Montagem Completa da Cena por Área e CLI de Extração

**Files:**
- Modify: `skills/ds2-save/scripts/ds2cena.py`
- Modify: `tests/test_ds2cena.py`

**Interfaces:**
- Produces:
  - `ds2cena.extrair_cena(game_dir, area: str, cache_dir) -> dict`
  - CLI `python ds2cena.py extrair --area <area>`

- [ ] **Step 1: Escrever teste falhando para `extrair_cena` com MSB**

Criar teste que valida o processamento das partes de mapa e objetos do MSB, convertendo rotações Euler em matrizes 4x4, gerando `cena.json`, `geo.bin` e `tex/` no diretório de destino.

- [ ] **Step 2: Rodar teste para verificar falha**

Run: `pytest tests/test_ds2cena.py -k "test_extrair_cena" -v`
Expected: FAIL

- [ ] **Step 3: Implementar `extrair_cena` e CLI em `ds2cena.py`**

Integrar leitura de MSB (`MODEL_PARAM_ST` e `PARTS_PARAM_ST`), cálculo de matriz de transformação (translação, rotação XYZ em graus, escala), corte de andares (reaproveitando `ds2planta.detectar_andares`), e salvamento atômico em `~/.buildsmith/cache/ds2/cena/<area>/`.

- [ ] **Step 4: Rodar testes unitários e teste real com Majula (se jogo presente)**

Run: `pytest tests/test_ds2cena.py -v`
Expected: PASS

- [ ] **Step 5: Testar extração real da área Majula via linha de comando**

Run: `python skills/ds2-save/scripts/ds2cena.py extrair --area m10_04_00_00`
Expected: Resumo JSON impresso com sucesso e arquivos gerados em `~/.buildsmith/cache/ds2/cena/m10_04_00_00/` dentro do limite de 30 MB.

- [ ] **Step 6: Commit**

```bash
git add skills/ds2-save/scripts/ds2cena.py tests/test_ds2cena.py
git commit -m "feat: extração completa de cena isométrica com CLI"
```

---

### Task 4: Rotas de API da Cena no Servidor Local (`serve.py`)

**Files:**
- Modify: `app/serve.py`
- Modify: `tests/test_serve.py`

**Interfaces:**
- Rotas adicionadas:
  - `GET /api/ds2/cena/<area>/cena.json`
  - `GET /api/ds2/cena/<area>/geo.bin`
  - `GET /api/ds2/cena/<area>/tex/<nome>.dds`
  - `POST /api/ds2/cena/<area>/extrair`

- [ ] **Step 1: Escrever teste falhando para as rotas de cena em `test_serve.py`**

Adicionar casos de teste para:
1. `GET` de área não extraída retornando 404 com comando para extrair.
2. `GET` de cena existente servindo `cena.json`, `geo.bin` e textura `.dds`.
3. Validação de segurança (bloqueio de traversal `..` e nomes inválidos).
4. `POST /api/ds2/cena/<area>/extrair` disparando extração assíncrona.

- [ ] **Step 2: Rodar teste para verificar falha**

Run: `pytest tests/test_serve.py -k "cena" -v`
Expected: FAIL

- [ ] **Step 3: Implementar handlers de cena em `app/serve.py`**

Adicionar suporte às rotas na classe `Handler` de `serve.py`, checando existência em `home / "cache" / "ds2" / "cena" / area`.

- [ ] **Step 4: Rodar testes de `test_serve.py`**

Run: `pytest tests/test_serve.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/serve.py tests/test_serve.py
git commit -m "feat: rotas de API para servir e extrair cena 3D no serve.py"
```

---

### Task 5: Three.js Vendor e Módulo Isométrico `iso.js`

**Files:**
- Create: `skills/build-page/template/vendor/three.module.min.js`
- Create: `skills/build-page/template/vendor/DDSLoader.js`
- Create: `skills/build-page/template/iso.js`
- Modify: `skills/build-page/template/index.html`

**Interfaces:**
- Produces:
  - `initIso(containerEl, areaData, apiBaseUrl) -> { setAndar, setGiro, focarPonto, destruir, projetarParaTela }`

- [ ] **Step 1: Instalar arquivos vendor Three.js e DDSLoader**

Copiar o bundle standalone `three.module.js` (r160) e `DDSLoader.js` para `skills/build-page/template/vendor/`.

- [ ] **Step 2: Criar `skills/build-page/template/iso.js`**

Implementar visualizador Three.js:
1. Cena com fundo escuro característico do Buildsmith (#101013).
2. Câmera ortográfica configurada com projeção isométrica.
3. Carregamento de `cena.json`, `geo.bin` e texturas DDS via `DDSLoader`.
4. Iluminação hemisférica + luz direcional atrelada à câmera.
5. Plano de clipping vertical `clippingPlanes` ajustável por andar (`setAndar(andarId)`).
6. Rotação em passos de 90° (`setGiro(delta)`).
7. Função de projeção 3D -> 2D tela para ancorar marcadores HTML.

- [ ] **Step 3: Testar carregamento sintético de `iso.js` em Node ou página de teste**

Criar página HTML mínima ou teste de importação para validar sintaxe e inicialização.

- [ ] **Step 4: Commit**

```bash
git add skills/build-page/template/vendor/ skills/build-page/template/iso.js
git commit -m "feat: módulo Three.js e visualizador isométrico iso.js"
```

---

### Task 6: Integração no `mapa.js` (Botão 2D / Isométrico e Sincronização)

**Files:**
- Modify: `skills/build-page/template/mapa.js`
- Modify: `skills/build-page/template/pagina.css`
- Modify: `skills/build-page/template/index.html`

**Interfaces:**
- Alternador de vista no cabeçalho do mapa: `[ 2D | Isométrico ]`.
- Sincronização bidirecional: andar selecionado atualiza tanto a planta 2D quanto o corte de altura 3D; clique em rota ou marcador foca a câmera na mesma coordenada.

- [ ] **Step 1: Atualizar UI do mapa com controles do modo Isométrico**

Adicionar botão alternador de visualização e botões de giro da câmera (⟲ 90° ⟳) no HTML/CSS.

- [ ] **Step 2: Implementar alternância e sincronização de eventos em `mapa.js`**

Integrar ciclo de vida de `iso.js` no `mapa.js`:
- Ao ativar Isométrico: oculta SVG do chão, inicializa canvas WebGL, mantém camada de ícones/marcadores projetada sobre as coordenadas 3D.
- Atualização contínua de posição dos ícones durante pan/zoom/giro do Isométrico.
- Tratamento de fallback se a cena não estiver extraída (botão "Extrair modelo 3D desta área").

- [ ] **Step 3: Validar visualmente com Majula rodando `app/serve.py`**

Abrir página local e validar transição fluida entre 2D e Isométrico, giro 90°, corte por andar e marcador do jogador "Você" no lugar exato.

- [ ] **Step 4: Rodar suíte completa de testes**

Run: `pytest`
Expected: 100% PASS

- [ ] **Step 5: Commit**

```bash
git add skills/build-page/template/mapa.js skills/build-page/template/pagina.css skills/build-page/template/index.html
git commit -m "feat: integração de alternância 2D e Isométrico no mapa"
```

---

### Task 7: Documentação e Atualização de Versão

**Files:**
- Modify: `skills/ds2-save/SKILL.md`
- Modify: `README.md`
- Modify: `.claude-plugin/plugin.json` (ou controle de versão correspondente)

- [ ] **Step 1: Documentar novo comando `ds2cena.py extrair` e modo isométrico**

Atualizar a documentação da skill `ds2-save` e o README do projeto descrevendo a funcionalidade de mapa isométrico 3D.

- [ ] **Step 2: Rodar checagem final de testes**

Run: `pytest`
Expected: PASS

- [ ] **Step 3: Commit final**

```bash
git add skills/ds2-save/SKILL.md README.md
git commit -m "docs: documentação do mapa isométrico e comando ds2cena"
```
