# buildsmith

Conjunto de skills do Claude Code para planejar builds de jogos a partir do save do jogador.

Primeiro jogo suportado: Dark Souls II: Scholar of the First Sin.

## Instalar

```bash
pip install pycryptodome
claude plugin marketplace add C:/Users/<usuario>/Dev/Projects/buildsmith
claude plugin install buildsmith@buildsmith
```

## Usar

No Claude Code: `/buildsmith:build ds2` ou `/buildsmith:build ds2 quero focar piromancia`.

A página abre em `http://127.0.0.1:8642/p/ds2/<personagem>/`, servida por `app/serve.py` (só Python padrão). Para ter um ícone na área de trabalho que sobe o servidor e abre a página:

```bash
pip install pillow
python app/instalar_atalho.py
```

O atalho **Forja de Build** roda `app/abrir.py`, que abre sempre atualizado: `git pull` (só avança; com alteração local, pula), reinicia o servidor se o código mudou e refaz as páginas a partir do `plano.json` que já estão em `~/.buildsmith/paginas/` (sem Claude, nenhum token). Uma janelinha mostra os passos e fecha quando o navegador abre. O mesmo vale para `python app/serve.py --open` (atalho antigo). Para desligar ou reiniciar o servidor à mão (Windows incluso):

```bash
python app/serve.py parar
python app/serve.py reiniciar
```

**Ao vivo:** com a página aberta pelo servidor local, o save é relido sempre que o jogo grava (sem Claude, sem token): nível e almas no topo (com quanto subiu desde o plano), atributos na hora, "✓ você tem" nos itens do plano que já estão no inventário (e no mapa), e os passos que o jogo já mostra feitos (anel equipado, chefe derrotado, compra no inventário, arma no reforço, atributo no alvo) entram na conta de feitos.

Na página local, **Atualizar plano** e **Responder fila** rodam a skill sem abrir o Claude Code (`claude -p` em segundo plano, uma execução por vez, com etapas e custo na tela). Precisa do `claude` no PATH e logado: rode `claude` uma vez no terminal e use `/login`.

Essa execução lê a wiki sem ninguém olhando, então roda trancada: sem as suas configurações do Claude Code, em modo `dontAsk`, e com `app/guard.py` decidindo cada ferramenta (só os scripts do buildsmith, gravação só em `~/.buildsmith/`, WebFetch só na wiki). O que o guarda bloqueia aparece na barra de progresso.

Vários personagens no mesmo save: **Trocar personagem** (no topo da página) lista os personagens do save, abre a página de cada um ou gera o plano de quem ainda não tem. O retrato é automático (equipamento do save), ou uma foto que você solta no card, ou o último print do DS2 na Steam (F12).

**Equipamento:** a página mostra seu equipamento como o menu do DS2 (mãos, armadura, anéis, sintonia) e o melhor do plano ao lado, com o ganho de AR em cada slot e em cada feitiço, quanto do dano vem dos seus atributos e a letra de escala de cada peça (da wiki).

**Mapa:** com o DS2 SotFS instalado, a seção Mapa tem vista 2D e **3D** com o cenário do jogo (peças de mapa e texturas originais). No 3D a câmera é de espectador: arrastar move pelo chão, botão direito (ou Alt) gira e inclina, roda dá zoom no cursor, **WASD** anda, **Q/E** giram, **R/F** inclinam, Shift acelera. **Interior** (tecla I) corta o que está acima do andar para ver dentro de cavernas e prédios em qualquer ângulo (PgUp/PgDn trocam o andar); **Foco** (O) escurece o que está longe do centro da vista. O seletor lista todas as áreas do jogo na ordem da rota, separadas em **Liberadas** e **Ainda não liberadas** pelas fogueiras acesas no save (lidas ao vivo: acendeu uma fogueira, a lista muda); o mapa abre onde você está, e cada zona mostra se a fogueira dela está acesa. Itens, fogueiras, NPCs, chefes, inimigos, "Você" e a rota aparecem por cima nos dois modos; no 3D, inimigos e objetos (portas, baús, alavancas, elevadores...) usam os **modelos do próprio jogo**: os objetos fazem parte do cenário e os filtros **Portas e alavancas**, **Baús** e **Chaves** os destacam com cor; os inimigos aparecem e somem pelo filtro **Inimigos** e os NPCs que têm modelo próprio (Straid, McDuff...) pelo filtro **NPCs** (sem modelo legível, uma forma simples no tamanho certo fica no lugar, e o popover diz por quê). **Realçar inimigos** (tecla H) deixa os inimigos em vermelho forte, com um anel pulsando, e visíveis através das paredes no 3D (o resto do mapa fica apagado). Os inimigos ainda estão sem animação (pose de referência do modelo). O nome do inimigo vem da linha do próprio jogo (o Pursuer perto do McDuff aparece como The Pursuer); porta cujo modelo diz a chave mostra qual chave abre e onde ela está. **Livre** (tecla V) troca a câmera fixa por uma de espectador: WASD voa para onde você olha, segurar e arrastar olha em volta, E/Espaço sobe, Q/C desce; a rota pelo chão sai reta, dobrando só nas quinas, com as paradas numeradas do dourado (1ª) à brasa (última). O cenário de cada área é extraído na primeira vez que você abre o 3D (uns 5–10 s) para `~/.buildsmith/cache/ds2/cena/`.

Para ver no celular, publique no Artifact: `/buildsmith:build ds2 publicar`.

Seus dados (perfil, histórico, cache da wiki, link da página) ficam em `~/.buildsmith/`, fora do repositório.

## Testes

```bash
pip install pytest pycryptodome
python -m pytest -q
```

`tests/test_injection.py` tem um teste por caminho de prompt injection conhecido. Para rodar o mesmo ataque contra o `claude -p` de verdade (custa centavos): `BUILDSMITH_LIVE=1 python -m pytest -q tests/test_injection_live.py`.

Listas de IDs do DS2: [DS2S-META](https://github.com/Nordgaren/DS2S-META) (MIT). Nomes de inimigos e objetos por linha/modelo do jogo: [Smithbox](https://github.com/vawser/Smithbox) (MIT, `games/ds2/nomes_smithbox.json`).
