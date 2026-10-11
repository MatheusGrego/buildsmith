# Forja de Build (buildsmith)

Companion para jogar com o plano de build do lado. O buildsmith é um programa que roda na sua máquina, lê o seu save e os arquivos do jogo instalado e mostra uma página no navegador: seu personagem, o equipamento, o plano de build e o mapa 2D/3D de cada área com o que importa (itens, inimigos, portas e chaves, fogueiras, a rota pelo chão). Tudo isso se atualiza sozinho enquanto você joga.

Primeiro jogo: **Dark Souls II: Scholar of the First Sin** (Steam, Windows).

> **Early alpha.** Funciona no dia a dia do desenvolvimento, mas ainda muda bastante entre versões.

## Instalar (Windows, sem Python)

1. Baixe o `buildsmith-<versão>-windows-x64.zip` na página de [Releases](https://github.com/MatheusGrego/buildsmith/releases) e descompacte onde quiser.
2. Dê dois cliques em **`Buildsmith.exe`**. Uma janelinha mostra os passos e o navegador abre em `http://127.0.0.1:8642/`.
3. Opcional: `Buildsmith.exe atalho` (num terminal na pasta) cria o atalho **Forja de Build** na área de trabalho.

A pasta traz o Python embutido (`python.exe`, `pythonw.exe` e `runtime\`). Nada do jogo vem junto: mapas, modelos e textura são lidos da sua instalação do DS2, na hora.

## O que ele faz sozinho (sem IA)

- **Save ao vivo:** relê o save sempre que o jogo grava. Nível e almas no topo, atributos, inventário ("✓ você tem" nos itens do plano), passos que o jogo já mostra feitos (anel equipado, chefe derrotado, compra, reforço, atributo no alvo), fogueiras acesas e áreas liberadas.
- **Equipamento:** igual ao menu do DS2 (mãos, armadura, anéis, sintonia), com o melhor do plano ao lado, o ganho de AR por slot e por feitiço e a letra de escala de cada peça.
- **Mapa 2D e 3D** com o cenário real do jogo (peças de mapa, objetos e inimigos com os modelos e texturas originais):
  - câmera fixa ou **livre** (V); **Interior** (I) corta o que está acima do andar; **Foco** (O) escurece o resto;
  - itens, fogueiras, NPCs, chefes e inimigos com o nome do próprio jogo; **Realçar inimigos** (H) mostra os inimigos através das paredes;
  - **estado do seu mundo** pelo save: porta aberta, alavanca puxada, baú aberto, item que você já pegou;
  - **chave de cada porta**, pelo script de evento do jogo, com onde pegar a chave;
  - **rota pelo chão** até qualquer ponto, avisando as portas do caminho e se estão abertas no seu save.
- **Vários personagens** no mesmo save: Trocar personagem, com retrato automático.

O cenário de cada área é extraído na primeira vez que você abre o 3D (de 5 a 15 s) e fica em cache.

## O que usa IA

O **plano de build** (o que buscar, em que ordem, onde pegar, quanto upar) é escrito pelo Claude a partir do save e da wiki. Na página, **Atualizar plano** e **Responder fila** rodam o Claude Code em segundo plano (`claude -p`), uma execução por vez, com etapas e custo na tela. Precisa do `claude` instalado e logado (`claude`, depois `/login`).

Essa execução lê a wiki sem ninguém olhando, então roda trancada: sem as suas configurações do Claude Code, em modo `dontAsk`, e com `app/guard.py` decidindo cada ferramenta (só os scripts do buildsmith, gravação só em `~/.buildsmith/`, WebFetch só na wiki). O que o guarda bloqueia aparece na barra de progresso.

## Seus dados

Perfil, páginas, histórico e cache (wiki, mapas, cenas 3D) ficam em `%USERPROFILE%\.buildsmith\`. O save do jogo só é lido, nunca gravado.

Parar ou reiniciar o servidor (na pasta do programa; pelo código-fonte, troque `python.exe` por `python`):

```bash
python.exe app\serve.py parar
python.exe app\serve.py reiniciar
```

## Pelo código-fonte

```bash
pip install pycryptodome
python app/abrir.py
```

`app/abrir.py` é o que o `Buildsmith.exe` roda: com o repositório, faz `git pull` (só avança; com alteração local, pula), reinicia o servidor se o código mudou e refaz as páginas a partir do `plano.json` de cada uma (sem Claude). `python app/instalar_atalho.py` (precisa de `pip install pillow`) cria o atalho apontando para o repositório.

O mesmo código também é um plugin do Claude Code (`.claude-plugin/`, `skills/`): é assim que o plano é gerado. Para usar direto no Claude Code: `claude plugin marketplace add <pasta do repositório>`, `claude plugin install buildsmith@buildsmith` e `/buildsmith:build ds2`. Para ver no celular, publique no Artifact: `/buildsmith:build ds2 publicar`.

### Gerar o executável

```bash
python release/construir.py
```

Cria `build/venv` (PyInstaller e pycryptodome com versão fixa), desenha o ícone, empacota `Buildsmith.exe`, `python.exe` e `pythonw.exe` com um só runtime, copia os arquivos do programa para o lado, testa cada executável e gera `build/buildsmith-<versão>-windows-x64.zip`.

## Testes

```bash
pip install pytest pycryptodome
python -m pytest -q
```

Os testes que precisam do jogo ou do save são pulados sem eles. `tests/test_injection.py` tem um teste por caminho de prompt injection conhecido; para rodar o mesmo ataque contra o `claude -p` de verdade (custa centavos): `BUILDSMITH_LIVE=1 python -m pytest -q tests/test_injection_live.py`.

## Créditos

Listas de IDs do DS2: [DS2S-META](https://github.com/Nordgaren/DS2S-META) (MIT). Nomes de inimigos e objetos por linha/modelo do jogo: [Smithbox](https://github.com/vawser/Smithbox) (MIT, `games/ds2/nomes_smithbox.json`). Formato dos arquivos do jogo: SoulsFormats (MIT), só como referência. Dark Souls II é da FromSoftware/Bandai Namco; nenhum arquivo do jogo vai no repositório nem na release.
