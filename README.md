# Forja de Build (buildsmith)

Companion para jogar com o plano de build do lado. O buildsmith é um programa que roda na sua máquina, lê o seu save e os arquivos do jogo instalado e mostra uma página no navegador: seu personagem, o equipamento, um catálogo com todos os itens do jogo (marque o que você quer e veja onde pegar e os passos), o plano de build e o mapa 2D/3D de cada área com o que importa (itens, inimigos, portas e chaves, fogueiras, a rota pelo chão). Tudo isso se atualiza sozinho enquanto você joga, e quase tudo funciona sem IA.

Primeiro jogo: **Dark Souls II: Scholar of the First Sin** (Steam, Windows).

> **Early alpha.** Funciona no dia a dia do desenvolvimento, mas ainda muda bastante entre versões.

## Instalar (Windows, sem Python)

1. Baixe o **`Buildsmith.exe`** na página de [Releases](https://github.com/MatheusGrego/buildsmith/releases) (um arquivo só).
2. Dê dois cliques nele. Na primeira vez ele descompacta o programa em `%LOCALAPPDATA%\Buildsmith\<versão>\` (alguns segundos); depois abre direto. Uma janelinha mostra os passos e o navegador abre em `http://127.0.0.1:8642/`.
3. Opcional: `Buildsmith.exe atalho` (num terminal na pasta dele) cria o atalho **Forja de Build** na área de trabalho, apontando para esse exe.

Versão nova: baixe o `Buildsmith.exe` novo; ele descompacta em outra pasta e apaga as antigas (seus dados em `%USERPROFILE%\.buildsmith\` ficam). O Windows pode avisar "editor desconhecido" (o exe não é assinado): **Mais informações → Executar assim mesmo**.

Prefere sem descompactar nada sozinho? A release também traz o `buildsmith-<versão>-windows-x64.zip`: descompacte onde quiser e dê dois cliques no `Buildsmith.exe` da pasta. Ela traz o Python embutido (`python.exe`, `pythonw.exe` e `runtime\`). Nada do jogo vem junto: mapas, modelos e textura são lidos da sua instalação do DS2, na hora.

## O que ele faz sozinho (sem IA)

- **Catálogo:** todos os itens do jogo (armas, escudos, catalisadores, feitiços, milagres, hexes, piromancias, armaduras, anéis e o resto), com filtro, busca, requisito e quantas fontes cada um tem. Marque com ★ e **Onde pegar** e **Passos** mostram o item:
  - quem vende (preço e estoque), troca de alma de chefe (e qual chefe dá a alma), chão/baú/cadáver, drop de inimigo e recompensa de chefe, tudo pelas tabelas do jogo;
  - **agora** (área com fogueira acesa no seu save), **em breve** (a próxima da rota de progressão) e **tarde**, com o **mais cedo** (mais perto da fogueira acesa) e o **mais rentável** (loja ilimitada ou drop que repete);
  - rota pelo chão da fogueira até o ponto, com as portas do caminho e a chave de cada uma;
  - o que falta: almas, chave, alma de chefe, níveis e almas para o requisito; item já pego e chefe já derrotado vão para o fim;
  - passos de comprar, trocar, pegar, farmar, upar e equipar; o que só a wiki diz (loja que abre por evento, chance de drop) aparece como "ver na wiki".
- **Página de cada personagem** do save, mesmo sem plano (criada pelo `Buildsmith.exe`, sem IA).
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

Só o **plano de build**, que é opcional: qual build seguir, quais itens buscar e por quê, o objetivo e a comparação com builds da comunidade. Onde pegar e os passos dos itens do plano saem do mesmo código do Catálogo (a IA não escreve fonte nem rota). Na página, **Atualizar plano** e **Responder fila** rodam o Claude Code em segundo plano (`claude -p`), uma execução por vez, com etapas e custo na tela. Precisa do `claude` instalado e logado (`claude`, depois `/login`).

Essa execução lê a wiki sem ninguém olhando, então roda trancada: sem as suas configurações do Claude Code, em modo `dontAsk`, e com `app/guard.py` decidindo cada ferramenta (só os scripts do buildsmith, gravação só em `~/.buildsmith/`, WebFetch só na wiki). O que o guarda bloqueia aparece na barra de progresso.

## Seus dados

Perfil, páginas, itens marcados, histórico e cache (wiki, mapas, índice de itens, cenas 3D) ficam em `%USERPROFILE%\.buildsmith\`. O save do jogo só é lido, nunca gravado.

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

`app/abrir.py` é o que o `Buildsmith.exe` roda: com o repositório, faz `git pull` (só avança; com alteração local, pula), reinicia o servidor se o código mudou, refaz as páginas a partir do `plano.json` de cada uma e cria a página sem IA de quem ainda não tem (sem Claude). `python app/instalar_atalho.py` (precisa de `pip install pillow`) cria o atalho apontando para o repositório.

O mesmo código também é um plugin do Claude Code (`.claude-plugin/`, `skills/`): é assim que o plano é gerado. Para usar direto no Claude Code: `claude plugin marketplace add <pasta do repositório>`, `claude plugin install buildsmith@buildsmith` e `/buildsmith:build ds2`. Para ver no celular, publique no Artifact: `/buildsmith:build ds2 publicar`.

### Gerar o executável

```bash
python release/construir.py
```

Cria `build/venv` (PyInstaller e pycryptodome com versão fixa), desenha o ícone, empacota `Buildsmith.exe`, `python.exe` e `pythonw.exe` com um só runtime, copia os arquivos do programa para o lado, testa cada executável e gera `build/buildsmith-<versão>-windows-x64.zip`. Com o Go instalado (1.21 ou mais novo), monta também o exe único `build/Buildsmith.exe`: o lançador de `release/lancador/` (só biblioteca padrão do Go) com esse zip e o ícone embutidos, testado numa pasta temporária.

## Testes

```bash
pip install pytest pycryptodome
python -m pytest -q
```

Os testes que precisam do jogo ou do save são pulados sem eles. `tests/test_injection.py` tem um teste por caminho de prompt injection conhecido; para rodar o mesmo ataque contra o `claude -p` de verdade (custa centavos): `BUILDSMITH_LIVE=1 python -m pytest -q tests/test_injection_live.py`.

## Licença

**[PolyForm Strict 1.0.0](LICENSE)** — o código é público para ser lido, mas não é open source:

- **pode:** baixar e usar o programa para fins **não comerciais** (uso pessoal, estudo, hobby, pesquisa);
- **não pode**, sem permissão por escrito dos autores: modificar, criar obras derivadas, redistribuir (o código, o
  executável ou partes deles) ou usar comercialmente.

Para pedir permissão, abra uma issue no repositório. O resumo acima não substitui o texto da [LICENSE](LICENSE).

Copyright 2026 Matheus Grego e jpmelo031.

## Créditos e avisos de terceiros

Os arquivos de terceiros seguem as próprias licenças (lista completa em [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)):

- [three.js](https://github.com/mrdoob/three.js) r160 (MIT), embutido na página para o mapa 3D;
- listas de IDs do DS2 do [DS2S-META](https://github.com/Nordgaren/DS2S-META) (MIT, `games/ds2/ids/`);
- nomes de inimigos e objetos por linha/modelo do jogo do [Smithbox](https://github.com/vawser/Smithbox) (MIT,
  `games/ds2/nomes_smithbox.json`);
- no executável: Python (PSF), [pycryptodome](https://github.com/Legrandin/pycryptodome) (BSD) e o carregador do
  [PyInstaller](https://pyinstaller.org) (GPL com exceção para programas empacotados), com as licenças em `licencas/`;
- só como referência, sem código copiado: [SoulsFormats](https://github.com/JKAnderson/SoulsFormats) e
  [Paramdex](https://github.com/soulsmods/Paramdex) (formatos e tabelas do jogo).

Projeto de fãs, sem ligação com a FromSoftware ou a Bandai Namco. **Dark Souls II** é delas: o buildsmith lê os
arquivos do jogo instalado na sua máquina, e nada do jogo vai no repositório nem na release. Páginas e ícones da
[wiki Fextralife](https://darksouls2.wiki.fextralife.com) são buscados na hora, citados com link, e ficam só no seu
cache local.
