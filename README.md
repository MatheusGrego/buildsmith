# buildsmith

Conjunto de skills do Claude Code para planejar builds de jogos a partir do save do jogador.

Primeiro jogo suportado: Dark Souls II: Scholar of the First Sin.

## Instalar

```bash
pip install pycryptodome
claude plugin marketplace add C:/Users/Matheus/Dev/Projects/buildsmith
claude plugin install buildsmith@buildsmith
```

## Usar

No Claude Code: `/buildsmith:build ds2` ou `/buildsmith:build ds2 quero focar piromancia`.

A página abre em `http://127.0.0.1:8642/p/ds2/<personagem>/`, servida por `app/serve.py` (só Python padrão). Para ter um ícone na área de trabalho que sobe o servidor e abre a página:

```bash
pip install pillow
python app/instalar_atalho.py
```

Na página local, **Atualizar plano** e **Responder fila** rodam a skill sem abrir o Claude Code (`claude -p` em segundo plano, uma execução por vez, com etapas e custo na tela). Precisa do `claude` no PATH e logado: rode `claude` uma vez no terminal e use `/login`.

Essa execução lê a wiki sem ninguém olhando, então roda trancada: sem as suas configurações do Claude Code, em modo `dontAsk`, e com `app/guard.py` decidindo cada ferramenta (só os scripts do buildsmith, gravação só em `~/.buildsmith/`, WebFetch só na wiki). O que o guarda bloqueia aparece na barra de progresso.

Vários personagens no mesmo save: **Trocar personagem** (no topo da página) lista os personagens do save, abre a página de cada um ou gera o plano de quem ainda não tem. O retrato é automático (equipamento do save), ou uma foto que você solta no card, ou o último print do DS2 na Steam (F12).

**Mapa:** com o DS2 SotFS instalado, a seção Mapa mostra cada área vista de cima, andar por andar, com o chão real do jogo (navmesh limpo em planta), grade, zoom, todos os itens da área com ícone e as fogueiras; a área fica dividida em zonas de fogueira coloridas em sequência (dourado na entrada até brasa no fim, pela distância a pé), com chefes (retrato, vivo ou derrotado pelo save) e NPCs (os que o plano usa, como o Straid, com aro âmbar e o que você precisa deles) e o painel "Rota da área"; você aparece em vermelho na posição da última gravação do save (o servidor local relê a cada 5 s) e "Rota até aqui" desenha o caminho pelo chão até qualquer item, NPC, chefe, fogueira ou inimigo (de você, se estiver na mesma área, ou da fogueira da zona do alvo); clicar num inimigo mostra HP, almas e drops do jogo e o nome só quando a wiki confirma (drops e almas batendo, com a prova); "Ver no mapa" leva ao item ou à rota de um passo. Tudo é gerado por script no seu PC e fica em `~/.buildsmith/cache/ds2/` (nada do jogo vai para o repositório).

Para ver no celular, publique no Artifact: `/buildsmith:build ds2 publicar`.

Seus dados (perfil, histórico, cache da wiki, link da página) ficam em `~/.buildsmith/`, fora do repositório.

## Testes

```bash
pip install pytest pycryptodome
python -m pytest -q
```

`tests/test_injection.py` tem um teste por caminho de prompt injection conhecido. Para rodar o mesmo ataque contra o `claude -p` de verdade (custa centavos): `BUILDSMITH_LIVE=1 python -m pytest -q tests/test_injection_live.py`.

Listas de IDs do DS2: [DS2S-META](https://github.com/Nordgaren/DS2S-META) (MIT).
