# Engenharia reversa da memória do DS2: como o minimapa sabe onde você está

Este documento explica, do zero, como o buildsmith lê a posição do personagem, a câmera e a área direto da memória do
Dark Souls II: Scholar of the First Sin, e como achamos os endereços que faltavam (a câmera e a área) numa sessão com o
jogo aberto em 2026-10-13. O código está em `skills/ds2-save/scripts/ds2mem.py` (ler a memória) e `ds2vivo.py` (montar o
estado ao vivo).

**Regra do projeto: só leitura.** Nada é escrito no jogo e nada é injetado nele. O buildsmith lê bytes do processo
usando a mesma API do Windows que depuradores e monitores de sistema usam (`ReadProcessMemory`).

---

## 1. O que é a memória de um programa

Quando o `DarkSoulsII.exe` roda, o Windows dá a ele um **espaço de endereços virtual**: uma faixa enorme de endereços (em
64 bits, até `0x7FFFFFFFFFFF`) em que cada byte tem um número. Só uma parte dela está de fato em uso, dividida em regiões:

| Região | O que tem | Muda de lugar a cada vez que o jogo abre? |
|---|---|---|
| **Módulo** (o `.exe` carregado) | O código de máquina, as tabelas fixas e as variáveis globais | O começo dele muda (ASLR), mas por dentro tudo fica na mesma distância |
| **Heap** | Os objetos que o jogo cria enquanto roda: o personagem, a câmera, a área carregada… | Sim, e mudam também durante o jogo (trocar de área recria objetos) |
| **Stack (pilha)** | Os dados temporários de cada função que está rodando agora | Sim, e a cada instante |

### Heap × stack, com calma

- A **stack (pilha)** funciona como uma pilha de pratos. Cada vez que uma função é chamada, ela empilha um "quadro" (frame)
  com as variáveis locais dela e o **endereço de retorno** (para onde voltar quando terminar). Quando a função termina, o quadro
  sai da pilha. Por isso o que está na pilha é **passageiro**: um valor que está lá agora some no próximo quadro do jogo.
  Não serve para o minimapa ler; serve muito, porém, para quem está **depurando** (o depurador mostra a pilha de chamadas:
  "quem chamou quem" até chegar aqui).
- O **heap** é onde ficam os objetos que duram: o jogo pede memória ("quero 0x600 bytes para a câmera") e usa até não
  precisar mais. É aí que estão a posição do personagem e a da câmera. O problema: o endereço muda toda vez.

### ASLR: por que o endereço muda toda vez

O Windows carrega o programa num lugar diferente a cada execução (ASLR, *Address Space Layout Randomization*), por
segurança. Numa das leituras desta sessão:

```
módulo DarkSoulsII.exe   começa em 0x7ff710df0000, tamanho 0x1d76000
```

Na próxima vez que o jogo abrir, vai começar em outro lugar. Então ninguém guarda "a posição está em 0x7ff4a82b4cb0":
guarda-se **um caminho** que sempre leva até ela.

---

## 2. Ponteiros e cadeias de ponteiros

Um **ponteiro** é um número de 8 bytes (em 64 bits) que é o endereço de outra coisa. A notação usada aqui:

- `[x]` = "leia os 8 bytes que estão no endereço x e use como endereço";
- `+0xD0` = "some 0xD0 (208) bytes": o deslocamento (offset) até um campo dentro do objeto.

O jogo tem uma variável global (no módulo, então com posição fixa em relação ao `.exe`) que aponta para um objeto
central, que o DS2S-META chama de **BaseA**. A partir dele dá para chegar em tudo:

```
módulo ──► [ponteiro estático] ──► BaseA (objeto no heap)
                                     │
                                     ├─ +0xD0 ──► PlayerCtrl ──► +0xF8 ──► … ──► +0xF0 ──► objeto da posição
                                     │                                                      +0x20  x  (float)
                                     │                                                      +0x24  y  (altura)
                                     │                                                      +0x28  z
                                     │                                                      +0x30  rotação (quaternion)
                                     ├─ +0xA8 ──► objeto do jogador   +0x114 nome (texto UTF-16)
                                     │                                +0x1B8 área atual       (achado nesta sessão)
                                     ├─ +0xB0 ──► objeto da câmera    +0x1E0 posição da câmera (achado nesta sessão)
                                     └─ +0x70 ──► EventManager        +0x164 área da última fogueira
```

Em código (`ds2mem.cadeia`), seguir `[[BaseA+0xD0]+0xF8]+0xF0` é só um laço: leia, some, leia de novo. Se algum ponteiro
der **0**, o objeto ainda não existe: é a tela de título ou uma tela de carregamento. O buildsmith responde
`{"ativo": false, "motivo": "carregando"}` em vez de ler lixo.

---

## 3. Achar o BaseA quando o jogo é atualizado: padrões de bytes (AOB)

O endereço do ponteiro estático pode mudar se o jogo receber um patch. Para não depender disso, procura-se o **código** que
usa esse ponteiro. Em algum lugar do `.exe` existe a instrução de máquina:

```
48 8B 05 ?? ?? ?? ??     mov rax, [rip + deslocamento]   ← lê o ponteiro estático
48 8B 58 38              mov rbx, [rax + 0x38]
48 85 DB                 test rbx, rbx
74 ??                    je  …
F6 …
```

A sequência `48 8B 05 ? ? ? ? 48 8B 58 38 48 85 DB 74 ? F6` é a **assinatura** (AOB, *array of bytes*), e os `?` são
bytes que mudam de versão para versão. O buildsmith varre o módulo procurando esse padrão (`ds2mem.achar_aob`).

### Endereçamento relativo ao RIP

Em x64, `mov rax, [rip + X]` não guarda o endereço completo; guarda **quanto andar** a partir do fim da instrução. RIP é
o registrador que aponta para a próxima instrução. Então:

```
endereço do ponteiro = início da instrução + 7 (tamanho dela) + X (os 4 bytes depois de 48 8B 05)
```

É o que `ds2mem.rel32(mem, instr, 3, 7)` faz. Numa leitura desta sessão o ponteiro estático estava em `0x7ff7124048f0`,
e o BaseA (o valor dele) em `0x7ff4a4b40260`.

---

## 4. Como os números estão guardados

- **Inteiros e ponteiros** são *little-endian*: o byte menos significativo vem primeiro. `60 02 B4 A4 F4 7F 00 00` é
  `0x7FF4A4B40260`.
- **Posições** são `float32` (IEEE 754): 4 bytes por número, 3 números seguidos (x, y para cima, z). É a mesma ordem da
  posição gravada no save, e foi isso que confirmamos ao ver o minimapa bater com o personagem.
- **Rotação do personagem** é um **quaternion** (w, x, y, z): uma forma de guardar rotação em 4 números sem os problemas
  dos ângulos. Para o minimapa basta o giro em volta do eixo vertical:
  `direção = atan2(2(wy + xz), 1 − 2(x² + y²))`.
- **Área** são 4 bytes, os mesmos do save: `00 00 04 0A` → `m10_04_00_00` (Majula). Cada byte é um número do nome do mapa,
  em ordem invertida.

---

## 5. A armadilha da vtable: por que a câmera do DS2S-META dava lixo

O DS2S-META (ferramenta aberta, licença MIT) dizia que a câmera estava em `[[BaseA+0x0]+0x20]`. No jogo, isso dava
posições como `1,3 × 10²⁷`: lixo.

O motivo: em C++, todo objeto de uma classe com métodos virtuais começa com um ponteiro para a **vtable**, uma tabela,
**dentro do `.exe`**, com os endereços das funções daquela classe. Então `[BaseA+0x0]` não é um objeto do heap: é a vtable
(o valor lido, `0x7ff711eb4c68`, cai dentro do módulo). `[vtable+0x20]` é o endereço de uma **função**, e os bytes de código
de máquina lidos como `float` viram números absurdos.

Dica de leitura: **um "ponteiro" que cai dentro do módulo quase sempre é vtable ou código, não dado.** O script de busca
(seção 6) pula esses de propósito.

---

## 6. Achando a câmera: o método "foto e filtro"

Sem caminho conhecido, procuramos a câmera pelo **comportamento**. É o mesmo raciocínio do Cheat Engine ("valor
desconhecido", depois "mudou" / "não mudou"):

1. **Foto.** A partir do BaseA, abrimos cada ponteiro que aparece nos primeiros 0x600 bytes de cada objeto, até 3 níveis
   de profundidade: **12.372 objetos**. Em cada um, guardamos todo trio de floats que fica a até 25 m do personagem e
   pouco acima dele: **34.883 candidatos**.
2. **Filtro "parado".** Sem ninguém mexer, lemos de novo e jogamos fora o que mudou sozinho (animação, partículas):
   **33.232**.
3. **Filtro "girou".** Você girou **só a câmera** ~90° para a esquerda. Ficamos com o que mudou e continuou perto:
   **228**.
4. **Geometria.** Dos 228, ficamos com os que **giraram em volta do personagem** mantendo a mesma distância: **76**, todos
   concordando (câmera a 3,57 m, 1,85 m acima, girou −73°). São cópias do mesmo dado em vários objetos.
5. **Escolha do caminho.** O mais curto: `[BaseA+0xB0]+0x1E0`. Caminho curto = menos objetos no meio = menos chance de
   quebrar.
6. **Confirmação.** Você girou ~90° para a direita: o yaw foi de +156,8° para −113,8°, ou seja, **+89,4°**.

A direção da câmera sai da posição dela e da do personagem: `yaw = atan2(x_personagem − x_câmera, z_personagem − z_câmera)`.
É a mesma convenção do mapa 3D da página (frente = (sen yaw, cos yaw)), então o minimapa gira direto com esse número.

---

## 7. Achando a área: separando "onde estou" de "última fogueira"

Mesmo método, mas procurando o **código da área** (4 bytes) em vez de floats:

| Momento | Área | Candidatos com o código certo |
|---|---|---|
| Em Majula | `m10_04_00_00` | 550 |
| Viajou por fogueira para a Cardinal Tower | `m10_10_00_00` | 297 |
| Viajou por fogueira para Heide | `m10_31_00_00` | 272 |
| **Andou a pé** de Heide até Majula | `m10_04_00_00` | **139** |

Viajar por fogueira muda ao mesmo tempo a "área atual" e a "área da última fogueira". Por isso a última etapa foi **a pé**:
os 2 campos que ficaram em Heide (`[BaseA+0x70]+0x164` e `[BaseA+0x40]+0x360`) guardam a **última fogueira**. Os 139 que
viraram Majula guardam a **área atual**. Escolhemos `[BaseA+0xA8]+0x1B8`, no mesmo objeto do nome do personagem.

---

## 8. Ferramentas

| Ferramenta | Para quê | Usamos aqui? |
|---|---|---|
| **API do Windows via `ctypes`** (`CreateToolhelp32Snapshot`, `OpenProcess`, `EnumProcessModulesEx`, `ReadProcessMemory`) | Achar o processo, o módulo e ler bytes | Sim: é o `ds2mem.py` |
| **Scripts de "foto e filtro"** (Python) | Busca por comportamento (seção 6 e 7) | Sim, descartáveis |
| **Cheat Engine** | O mesmo método com interface gráfica | Não (mesma ideia) |
| **Ghidra / REA** (desmontador e descompilador) | Análise **estática**: ler o código de máquina e ver *quem* lê ou escreve um campo (referências cruzadas), transformar assembly em pseudo-C | Não foi preciso desta vez. Seria o próximo passo para entender *por que* há 139 cópias da área, ou se o jogo mudar e a busca por comportamento falhar |
| **Depurador** (x64dbg) | Parar o jogo numa instrução, ver registradores e a **pilha de chamadas** | Não: pausar o jogo atrapalha jogar, e só leitura basta |

---

## 9. O que pode quebrar

- **Patch do jogo:** o padrão do BaseA segura mudanças pequenas. Os offsets (`+0xB0`, `+0x1E0`…) podem mudar num patch
  grande. Aí é refazer a seção 6/7 (umas dezenas de minutos com o jogo aberto).
- **Outros mods:** o Seamless Coop roda junto e não mudou nada disso nos testes.
- **Valor estranho:** a área passa por uma checagem de formato (`m10`..`m59`); se vier zerada ou fora disso, o buildsmith usa
  a área do save.

## Glossário

- **Processo:** um programa rodando.
- **Módulo:** um `.exe` ou `.dll` carregado na memória do processo.
- **Offset:** distância, em bytes, de um campo até o começo do objeto.
- **Ponteiro estático:** variável global com endereço fixo em relação ao módulo; é a raiz das cadeias.
- **AOB / assinatura:** sequência de bytes de código usada para achar um lugar no `.exe` mesmo depois de patches.
- **RIP:** registrador que aponta para a próxima instrução; base do endereçamento relativo do x64.
- **vtable:** tabela de funções de uma classe C++; o primeiro campo de muitos objetos aponta para ela.
- **Quaternion:** 4 números que guardam uma rotação 3D.
- **Stack / heap:** pilha (dados passageiros de cada função) / monte (objetos que duram).
- **ASLR:** o Windows muda o endereço do programa a cada execução.

## Créditos

Endereços de partida (padrão do BaseA, cadeias do jogador e do nome): [DS2S-META](https://github.com/pseudostripy/DS2S-META),
MIT, © 2021 Nordgaren (veja `THIRD_PARTY_NOTICES.md`). Câmera e área: achadas nesta sessão com o método da seção 6 e 7.
