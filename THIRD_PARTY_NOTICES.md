# Avisos de terceiros

O buildsmith é licenciado pela [PolyForm Strict 1.0.0](LICENSE). Os itens abaixo **não são** nossos: seguem as
próprias licenças, que continuam valendo para eles, e são listados aqui como essas licenças pedem.

## Arquivos de terceiros no repositório

| O quê | Onde | Licença | Texto da licença |
|---|---|---|---|
| [three.js](https://github.com/mrdoob/three.js) r160 (desenho 3D da página) | `skills/build-page/template/vendor/three.module.js` | MIT, © 2010-2023 three.js authors | `skills/build-page/template/vendor/LICENSE-THREEJS` |
| Listas de IDs de itens do DS2, do [DS2S-META](https://github.com/Nordgaren/DS2S-META) | `games/ds2/ids/*.txt` | MIT, © 2021 Nordgaren | `games/ds2/ids/LICENSE-DS2S-META` |
| Nomes de inimigos, personagens e objetos por linha/modelo do jogo, do [Smithbox](https://github.com/vawser/Smithbox) | `games/ds2/nomes_smithbox.json` | MIT, © 2025 Vawser | `games/ds2/LICENSE-SMITHBOX` |

## Dentro do executável do Windows (release)

| O quê | Licença | Texto da licença no zip |
|---|---|---|
| Python 3.12 (o `runtime\` que roda os scripts) | PSF License Agreement | `licencas/PYTHON-LICENSE.txt` |
| [pycryptodome](https://github.com/Legrandin/pycryptodome) 3.21 (abre os índices e o save do jogo) | BSD 2-Clause (e partes em domínio público) | `licencas/PYCRYPTODOME-LICENSE.rst` |
| Carregador do [PyInstaller](https://pyinstaller.org) 6.11 (`Buildsmith.exe`, `python.exe`, `pythonw.exe`) | GPL 2.0 com a exceção do bootloader, que permite distribuir o programa empacotado sob qualquer licença | `licencas/PYINSTALLER-COPYING.txt` |
| Runtime e biblioteca padrão do [Go](https://go.dev) (o lançador do exe único `Buildsmith.exe`, que traz o zip dentro) | BSD 3-Clause, © The Go Authors | `licencas/GO-LICENSE.txt` (no exe único: na pasta que ele descompacta em `%LOCALAPPDATA%\Buildsmith\<versão>\`) |

## Só como referência (nenhum código copiado)

- [SoulsFormats](https://github.com/JKAnderson/SoulsFormats) (MIT): o layout dos formatos FLVER, BND/BHF, TPF, MSB e
  ESD foi conferido lá; os leitores do buildsmith foram escritos do zero.
- [Paramdex](https://github.com/soulsmods/Paramdex) (soulsmods): nomes e posições de campos das tabelas de parâmetros
  do DS2, usados como referência para ler as tabelas do jogo.
- [DS2S-META](https://github.com/pseudostripy/DS2S-META) (MIT, © 2021 Nordgaren): endereços de memória do DS2 SotFS (padrão
  do ponteiro `BaseA` e as cadeias do jogador, da câmera e do nome) usados pela leitura ao vivo (`ds2mem`, `ds2vivo`), só
  leitura; o leitor foi escrito do zero.

## Conteúdo que não vai no repositório nem na release

- **Dark Souls II: Scholar of the First Sin** é da FromSoftware e da Bandai Namco. O buildsmith é um projeto de fãs,
  sem ligação com elas. Mapas, modelos, texturas, textos e tabelas do jogo são lidos **da instalação do jogo na
  máquina de quem usa**, na hora, e ficam só no cache local (`~/.buildsmith/`); nenhum arquivo do jogo é
  redistribuído. Os arquivos em `games/ds2/` guardam só fatos (IDs, nomes, flags) com a fonte de cada um.
- **Wiki do DS2 na Fextralife** (darksouls2.wiki.fextralife.com): páginas e ícones são buscados na hora e citados com
  link; ficam só no cache local. Os ícones do jogo e da wiki pertencem aos seus donos.
