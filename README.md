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

**Equipamento:** a página mostra seu equipamento como o menu do DS2 (mãos, armadura, anéis, sintonia) e o melhor do plano ao lado, com o ganho de AR em cada slot e em cada feitiço, quanto do dano vem dos seus atributos e a letra de escala de cada peça (da wiki).

**Mapa:** com o DS2 SotFS instalado, a seção Mapa oferece alternância entre visão 2D e Isométrica 3D com a geometria real do jogo (paredes, chão, escadas) e texturas originais (DDS). Permite rotação em passos de 90° (atalhos Q e E), corte de altura por andar e sincronização total dos marcadores (itens, fogueiras, NPCs, chefes, inimigos, rota e "Você") projetados sobre o mundo 3D. Tudo gerado localmente em `~/.buildsmith/cache/ds2/` sem dependências pesadas externas.

Para ver no celular, publique no Artifact: `/buildsmith:build ds2 publicar`.

Seus dados (perfil, histórico, cache da wiki, link da página) ficam em `~/.buildsmith/`, fora do repositório.

## Testes

```bash
pip install pytest pycryptodome
python -m pytest -q
```

`tests/test_injection.py` tem um teste por caminho de prompt injection conhecido. Para rodar o mesmo ataque contra o `claude -p` de verdade (custa centavos): `BUILDSMITH_LIVE=1 python -m pytest -q tests/test_injection_live.py`.

Listas de IDs do DS2: [DS2S-META](https://github.com/Nordgaren/DS2S-META) (MIT).
