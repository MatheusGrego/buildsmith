# Overlay in-game com minimapa 3D ao vivo — plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** minimapa 3D sempre na tela por cima do DS2 (e como fonte no OBS), seguindo o jogador ao vivo e girando com a câmera;
Ctrl+Shift+M abre o menu do buildsmith por cima do jogo.

**Architecture:** `ds2mem` lê o processo do jogo (só leitura, ctypes); `ds2vivo` monta o estado ao vivo (nome, posição, direção do
personagem, yaw da câmera pela posição câmera→personagem, área); o servidor publica a ~10 Hz (SSE); a página
`/overlay/ds2/<p>/` desenha o 3D (`iso.js`) em modo seguir; `app/overlay.py` cria e mantém as janelas do Edge por cima do jogo.

**Tech Stack:** Python 3.12 + ctypes (Win32), JS sem build (three.js r160 já vendorizado), Edge em modo app, pytest, node.

**Spec:** `docs/superpowers/specs/2026-10-13-buildsmith-overlay-minimapa-design.md`

## Global Constraints

- Só leitura da memória do jogo: `PROCESS_VM_READ | PROCESS_QUERY_LIMITED_INFORMATION`; nunca `WriteProcessMemory`, nunca DLL.
- Nenhuma dependência nova de Python (ctypes e stdlib); nada instalado na máquina do usuário além do que o Buildsmith já traz.
- Sem configuração do usuário: tudo se acha sozinho (processo, janela, monitor, DPI, Edge, teclas).
- Endereços do DS2S-META (MIT, © 2021 Nordgaren) — crédito no `THIRD_PARTY_NOTICES.md`:
  `BaseA` = AOB `48 8B 05 ? ? ? ? 48 8B 58 38 48 85 DB 74 ? F6` (rel32 na posição 3, instrução de 7 bytes, depois ler o ponteiro);
  `PlayerCtrl` = [BaseA+0xD0]; posição = [[PlayerCtrl+0xF8]+0xF0] com +0x20/+0x24/+0x28 (Y/Z/X no nome deles) e ângulos
  +0x34/+0x38/+0x3C; câmera = [[BaseA+0x0]+0x20] com +0x1A0/+0x1A4/+0x1A8 (X/Z/Y no nome deles); nome = [BaseA+0xA8]+0x114 (UTF-16).
- Teclas padrão Ctrl+Shift+M (overlay grande) e Ctrl+Shift+N (minimapa); reserva Ctrl+Alt+M/N.
- Minimapa: canto superior direito, quadrado de 24% da altura do monitor do jogo, margem 2%. Overlay grande: 80% × 80%, centrado.
- Texto em pt-BR, sem frase de enchimento.

## Review Focus

- Jogo fechado, na tela de título ou carregando (ponteiros nulos) → `{"ativo": false, "motivo": ...}` e o minimapa mostra "jogo
  fechado"/"carregando", sem exceção no servidor.
- Duas instâncias do jogo ou o processo trocando de PID (jogo reiniciado) → o leitor reabre o processo novo sozinho.
- Monitor com escala 125%/150% e jogo num segundo monitor → as janelas caem no monitor do jogo, no tamanho certo em pixels reais.
- Outra janela por cima (Discord, OBS) ou o jogo pegando o "topo" de novo → o minimapa volta para cima em ≤ 1 s com o jogo em foco.
- Combinação de tecla já registrada por outro programa → cai na reserva e o minimapa mostra qual tecla vale.

---

### Task 1: leitor de memória (`ds2mem.py`)

**Files:** Create `skills/ds2-save/scripts/ds2mem.py`; Test `tests/test_ds2mem.py`

**Interfaces — Produces:** `class Memoria` (ler(endereco, n) -> bytes; `u64`, `f32`, `utf16`); `class ProcessoWin(Memoria)`
(abre por nome do executável, `base_modulo`, `tamanho_modulo`, `fechar`); `class MemoriaFalsa(Memoria)` (dict de
regiões, para teste); `achar_aob(mem, inicio, tamanho, padrao) -> int | None`; `rel32(mem, endereco, pos, tam) -> int`;
`cadeia(mem, base, offsets) -> int | None` (segue ponteiros; None se algum for 0).

- [ ] Testes com `MemoriaFalsa`: AOB com curinga acha o endereço certo e devolve None quando não há; `rel32` resolve
  `instr + tam + rel`; `cadeia` segue 2 níveis e para em ponteiro nulo; leitura fora da região → `ErroMemoria`.
- [ ] Implementar `ProcessoWin` com `CreateToolhelp32Snapshot`/`Process32FirstW` (PID por nome), `OpenProcess`,
  `EnumProcessModulesEx`/`GetModuleInformation` (base e tamanho do módulo principal), `ReadProcessMemory`; varredura do AOB em
  blocos de 1 MiB com sobreposição do tamanho do padrão.
- [ ] Teste real pulado sem o jogo: acha o `BaseA` no `DarkSoulsII.exe`.
- [ ] Commit.

### Task 2: estado ao vivo (`ds2vivo.py`) + conferência com o jogo

**Files:** Create `skills/ds2-save/scripts/ds2vivo.py`; Test `tests/test_ds2vivo.py`; Modify `THIRD_PARTY_NOTICES.md`

**Interfaces — Consumes:** Task 1. **Produces:** `class LeitorVivo(mem_factory)` com `ler() -> dict`
`{"ativo", "nome", "pos": [x, y, z], "dir_personagem": rad, "yaw_camera": rad | None, "camera": [x, y, z], "area": str | None,
"ts"}` ou `{"ativo": False, "motivo"}`; `yaw_da_camera(camera, pos) -> float | None` (pura).

- [ ] Teste puro: `yaw_da_camera` com câmera atrás do personagem em +Z dá a direção −Z; câmera em cima (distância horizontal < 0,05 m)
  devolve None.
- [ ] Teste com `MemoriaFalsa` montando BaseA → PlayerCtrl → posição/câmera/nome: `ler()` devolve os valores nos eixos do mapa
  (os mesmos de `ds2save.posicao_do_slot`: `pos = [x, y_cima, z]`).
- [ ] Ponteiro nulo (tela de título/carregando) → `ativo: False, motivo: "carregando"`; processo some → reabre na próxima leitura.
- [ ] **Conferência com o jogo (manual, com o jogador):** descansar numa fogueira; a posição da memória bate com a do save
  (`ds2save.posicoes`) com erro < 0,5 m nos 3 eixos — é aqui que se fixa a ordem dos eixos do DS2S-META para os do mapa. Girar a
  câmera parado muda `yaw_camera`; andar em linha reta não muda. Repetir em 2 áreas.
- [ ] Crédito do DS2S-META no `THIRD_PARTY_NOTICES.md` (seção "Só como referência": endereços de memória).
- [ ] Commit.

### Task 3: área atual na memória (engenharia reversa)

**Files:** Modify `skills/ds2-save/scripts/ds2vivo.py`; Test `tests/test_ds2vivo.py`

- [ ] Achar o id do mapa atual (4 bytes no formato do save: `m{aa}_{bb}_{dd}_{cc}`) a partir de `PlayerDataMapPtr`
  ([[[PlayerCtrl+0x100]+0x320]+0x20], DS2S-META) ou do `MapManager` ([BaseA+0x38]): ler a região, trocar de área no jogo,
  ler de novo e ficar com o campo que muda para o id da área nova. Conferir com REA/Ghidra quem escreve o campo.
- [ ] Aceite: o campo bate com a área do save em ≥ 2 áreas diferentes (ex.: Majula `m10_04_00_00` e Forest of Fallen Giants
  `m10_10_00_00`).
- [ ] Sem campo achado: `area` vem do save (`ds2save.posicoes`) e é relida quando o `LoadingState` ([[[BaseA+0x80]+0x8]+0xBB4])
  sai de carregando; registrar a decisão.
- [ ] Teste com `MemoriaFalsa` do caminho escolhido; commit.

### Task 4: servidor ao vivo (`/api/ds2/vivo`, stream)

**Files:** Modify `app/serve.py`; Test `tests/test_serve.py`

**Interfaces — Consumes:** Task 2. **Produces:** `GET /api/ds2/vivo` (JSON) e `GET /api/ds2/vivo/stream` (`text/event-stream`,
`data: <json>\n\n` a cada ~100 ms; `retry: 2000`); `make_server(..., leitor_vivo=None)` injetável.

- [ ] Testes: `/api/ds2/vivo` com leitor falso; o stream manda ≥ 2 eventos em 400 ms e fecha sem erro quando o cliente sai;
  leitor que lança → `{"ativo": false}`.
- [ ] Uma thread leitora compartilhada (só lê enquanto há cliente), commit.

### Task 5: modo seguir e página do minimapa

**Files:** Modify `skills/build-page/template/iso.js`, `app/serve.py`; Create `skills/build-page/template/overlay.html`,
`skills/build-page/template/overlay.js`; Test `tests/test_injection.py` (padrão do `Iso._teste`), `tests/test_serve.py`

**Interfaces — Consumes:** Task 4. **Produces:** em `iso.js`: `seguir(estado)` (centro, giro = yaw da câmera, corte de
interior = altura do personagem + 2,5 m, seta pela `dir_personagem`) e puras `giroDoMinimapa(yaw)`, `corteDeAndar(y)`;
rota `GET /overlay/ds2/<personagem>/` (mesmo CSP da página).

- [ ] Testes node das puras: giro acompanha a yaw (mapa gira só com a câmera); corte = y + 2,5.
- [ ] Página do minimapa: só o canvas 3D numa moldura, EventSource no stream, troca de cena quando `area` muda, "jogo fechado"
  discreto, `?fundo=chave` pinta o fundo de `#FF00FF` (cor-chave da janela), padrão transparente (OBS).
- [ ] Teste de rota (200, CSP) e conferência no navegador com o jogo aberto; commit.

### Task 6: janelas por cima do jogo (`app/overlay.py`)

**Files:** Create `app/overlay.py`; Modify `app/abrir.py`; Test `tests/test_overlay.py`

**Interfaces — Produces:** puras `geometria(monitor, dpi) -> {"mini": (x, y, l, a), "grande": (...)}`,
`escolher_teclas(registrar) -> dict`; `class Overlay` (laço: acha `DarkSoulsII.exe` e a janela dele, abre o Edge
`--app=<url> --user-data-dir=<home>/overlay-edge --no-first-run --window-position --window-size`, acha a janela pelo PID,
aplica estilos, reafirma `HWND_TOPMOST` a cada 1 s com o jogo em foco, esconde quando o jogo sai do foco ou fecha).

- [ ] Testes das puras: 1920×1080 a 100% → mini (1418, 22, 259, 259) e grande (192, 108, 1536, 864); 2560×1440 a 150% com o
  monitor em x = 1920 → tudo deslocado e em pixels reais; teclas: primeira recusada → reserva.
- [ ] Win32 por ctypes: `SetProcessDpiAwarenessContext(PER_MONITOR_AWARE_V2)`, `EnumWindows` por PID, `SetWindowLongPtrW`
  (`WS_POPUP`; `WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW | WS_EX_TOPMOST` no mini), `SetLayeredWindowAttributes`
  (cor-chave magenta), `SetWindowPos`, `RegisterHotKey` + `GetMessageW` numa thread, `GetForegroundWindow`.
- [ ] `abrir.py` sobe o `Overlay` junto com o servidor (sem Edge: aviso no log e na página).
- [ ] Commit.

### Task 7: overlay grande e página principal ao vivo

**Files:** Modify `skills/build-page/template/pagina.js`, `skills/build-page/template/mapa.js` (marcador "você"),
`skills/build-page/template/iso.js`; Test `tests/test_injection.py`

- [ ] Página principal: com o jogo aberto, "você" vem do stream ao vivo (com o jogo fechado, do save como hoje); botão
  **Seguir** no 3D; aberta com `?overlay=1` abre direto no Mapa 3D seguindo.
- [ ] Teste node: escolha da fonte da posição (ao vivo × save) pelo `ativo` e pelo nome do personagem.
- [ ] Commit.

### Task 8: aceite com o jogo aberto (manual, com o jogador)

- [ ] Minimapa aparece sozinho no canto ao abrir o jogo, não rouba clique, gira só com a câmera, a seta acompanha o personagem,
  a cena troca ao mudar de área; Ctrl+Shift+M abre/fecha o overlay grande e devolve o foco ao jogo; alt-tab esconde o minimapa;
  URL do minimapa como fonte de navegador no OBS com fundo transparente.
