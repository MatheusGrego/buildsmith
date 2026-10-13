# Overlay in-game: minimapa 3D ao vivo e menu do buildsmith por cima do jogo

Data: 2026-10-13 · Pedido de um beta tester (streamer de DS2) e do jogador. Jogo: DS2 SotFS no Seamless Coop, com
`borderless_fullscreen = 1` no `ds2sc_settings.ini` (conferido no PC do jogador): tela cheia sem borda, então uma janela do
Windows "sempre por cima" aparece sobre o jogo sem tocar no processo do jogo.

## O que o jogador disse

- Minimapa 3D **sempre na tela** enquanto joga (2D vem depois, como alternativa: hoje o 2D não mostra escada nem objetos).
- O minimapa **gira com a câmera do jogo** (girar a câmera gira o mapa; andar não gira); uma **seta do personagem** mostra para
  onde ele olha. Altura ajusta sozinha (corte de andar pela altura do personagem).
- Posição **em tempo real**, como um minimapa de jogo. Rotas continuam funcionando.
- Uma **tecla** abre o overlay grande: mapa amplo + o menu do buildsmith (Equipamento, simulador, dano).
- Moldura com tamanho de acordo com o monitor. **Sem configuração do usuário**: a janela tem que aparecer sozinha.
- A mesma tela serve **para o jogador e como fonte no OBS**.

## Padrões que eu escolhi (revise)

- Minimapa: canto superior direito do monitor do jogo, quadrado, lado = 24% da altura do monitor, margem 2%.
- Overlay grande: 80% da largura e da altura do monitor do jogo, centrado.
- Teclas globais: **Ctrl+Shift+M** abre/fecha o overlay grande; **Ctrl+Shift+N** mostra/esconde o minimapa. Se o Windows recusar
  uma combinação (outro programa já usa), o buildsmith tenta Ctrl+Alt+M / Ctrl+Alt+N e o minimapa mostra a tecla em uso.
- Minimapa só aparece quando o jogo está em primeiro plano (some no alt-tab e quando o jogo fecha).
- Abrir o overlay grande tira o foco do jogo (o DS2 não pausa); fechar devolve o foco ao jogo.

## Partes (cada uma testável sozinha)

### 1. Leitura ao vivo da memória (`ds2vivo.py`)

Só leitura do processo `DarkSoulsII.exe` pela API do Windows (`OpenProcess` com `PROCESS_VM_READ |
PROCESS_QUERY_LIMITED_INFORMATION`, `ReadProcessMemory`, via ctypes; nada instalado, nada escrito no jogo).

- Lê: nome do personagem carregado, posição X/Y/Z, direção do personagem, direção (yaw) da câmera, área atual (id do mapa,
  ex. `m10_10_00_00`).
- Base: o AOB do `BaseA` e as cadeias do jogador local do DS2S-META (MIT); a direção da câmera e a área ainda não têm caminho
  conhecido: **engenharia reversa (REA/Ghidra)**, conferida em ≥ 2 lugares do jogo.
- Conferência: a posição lida da memória tem que bater com a do save (`ds2save.posicoes`) logo depois de o jogo gravar
  (descansar na fogueira); a yaw da câmera muda ao girar a câmera parado e não muda ao andar em linha reta.
- Se a yaw da câmera não for achada: o minimapa cai para norte fixo com a seta do personagem (padrão 3 da conversa).
- Sem jogo aberto ou leitura falhando: `{"ativo": false, "motivo": "..."}`; nunca derruba o servidor.

### 2. Fluxo ao vivo no servidor

- `GET /api/ds2/vivo` → um valor (posição, direções, área, `ts`); `GET /api/ds2/vivo/stream` → Server-Sent Events a ~10 Hz
  (EventSource funciona no Edge e na fonte de navegador do OBS). Uma thread lê a memória e todos os clientes recebem o mesmo
  valor. O jogador do processo é o personagem carregado; a página confere pelo nome contra o personagem dela.

### 3. Página do minimapa (`/overlay/ds2/<personagem>/`)

- Só o cenário 3D (`iso.js`) num quadro com moldura, em modo **seguir**: centro no jogador, rotação = yaw da câmera, inclinação
  e zoom fixos de minimapa, corte de interior acima da altura do personagem, seta do personagem pela direção dele, a rota ativa
  da página por cima. Troca de área recarrega a cena da área nova.
- Fundo: `?fundo=chave` (cor-chave para a janela do Windows) ou transparente (padrão, para o OBS).
- Sem jogo: mostra "jogo fechado" discreto; com o servidor fora, nada quebra.

### 4. Janelas por cima do jogo (`app/overlay.py`)

- Abre com o Buildsmith.exe e fica esperando o `DarkSoulsII.exe`; quando ele abre, cria **duas janelas** do Edge em modo app
  (`msedge --app=... --user-data-dir=<~/.buildsmith/overlay-edge> --no-first-run`), uma para o minimapa e outra (escondida)
  para o overlay grande (a página do personagem, na seção Mapa 3D seguindo o jogador).
- Ajustes pela API do Windows (ctypes): sem borda, sempre por cima, no monitor do jogo (`MonitorFromWindow`), consciente de DPI;
  minimapa com cor-chave (`WS_EX_LAYERED` + `LWA_COLORKEY`) e o clique passando para o jogo (`WS_EX_TRANSPARENT`), fora da barra
  de tarefas (`WS_EX_TOOLWINDOW`); "sempre por cima" reafirmado a cada segundo enquanto o jogo está em primeiro plano.
- Teclas globais por `RegisterHotKey` numa thread própria.
- Edge ausente: aviso na página principal e no log; o resto do buildsmith segue.
- Reserva, se a cor-chave ficar feia no teste com o jogo: janela Tauri/WebView2 com transparência real (spec à parte).

### 5. Overlay grande e página principal

- O overlay grande é a própria página do personagem (Mapa, Equipamento, simulador, Dano), com o 3D podendo seguir o jogador
  (botão "Seguir", ligado por padrão quando aberta pelo overlay). A página normal no navegador também passa a usar a posição ao
  vivo quando o jogo está aberto (e o save quando não está).

## Fora desta spec (próximas)

- Minimapa 2D; rota que considera a altura (item num andar acima do caminho); o amigo do coop no mapa (precisa de engenharia
  reversa da sessão do Seamless Coop); tecla no controle.

## Testes

- `ds2vivo`: leitura com um "processo" falso (bytes em memória) para cadeias e AOB; real (pulado sem o jogo aberto) conferindo
  com o save.
- Servidor: `/api/ds2/vivo` e o stream com um leitor injetado.
- `overlay.py`: cálculo da geometria por monitor e DPI e escolha das teclas (puras); a parte Win32 conferida à mão com o jogo.
- JS (node): matemática do modo seguir (rotação pela yaw, corte de andar pela altura, conversão posição → tela).
- Critério de aceite com o jogo aberto: minimapa aparece sozinho no canto, não rouba clique, gira com a câmera, a seta acompanha
  o personagem, a área troca ao passar de área, Ctrl+Shift+M abre e fecha o overlay grande, e a URL do minimapa funciona como
  fonte de navegador no OBS.
