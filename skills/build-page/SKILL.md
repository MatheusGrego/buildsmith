---
name: build-page
description: Publica ou atualiza a página fixa do plano de build do buildsmith (estilo wiki do DS2, fluxos com ícones e tabelas de dados). Use no fim do /buildsmith:build, depois que o plano.json v2 estiver pronto.
---

# build-page

## Regra de credibilidade (obrigatória, vale para tudo)

Nenhum fato de jogo vem da memória. Todo fato que aparece no plano, na página ou na resposta do chat precisa de **fonte verificada**:

- **O que conta como fato:** onde fica um item, NPC, chefe, baú ou fogueira; como chegar lá; requisito (atributo, chave, chefe, evento); quem vende, troca ou recebe o item; preço; efeito; drop, chance e quantidade; rota e ordem das áreas.
- **Fontes aceitas, nesta ordem:**
  1. **Tabelas do jogo e o save**, pelos scripts (`ds2save`, `ds2data`, `ds2calc`): números, lojas, trocas, requisitos, custos, progresso.
  2. **Wiki**, pela skill `wiki-cache` (URL + data, cache de até 30 dias): locais, rotas, baús, drops e efeitos que as tabelas não descrevem.
- **Sem fonte, não entra:** escreva `"—"` ou "não confirmado" e diga no chat o que faltou. Nunca complete com o que "deve ser".
- **Antes de publicar**, confira cada local, requisito e efeito do plano contra a fonte. Fonte e plano têm que dizer a mesma coisa.
- **Se o jogador contestar um fato**, verifique na fonte antes de responder. Se estava errado, diga isso claramente, corrija o cache e o plano.

Formato do plano: `example/plano.json` desta pasta (versão 2). Spec: `docs/superpowers/specs/2026-10-06-buildsmith-pagina-v2-design.md`.

## Regras do conteúdo

- **Nada de frase explicativa.** Todo passo é `fluxo` (nós com ícone e link) + `dados` (linhas Dado | Agora | Depois | Efeito).
- `sinal`: `"+"` = ganho (âmbar), `"-"` = perda ou falta (azul), `""` = neutro. Valor sem fonte = `"—"`.
- `titulo` até 40 caracteres; `sub` de nó até 30.
- Nó: `tipo` (`item, chefe, inimigo, npc, local, bau, almas, atributo`), `nome`, `link` da wiki, `icone` = URL do ícone da wiki (vem do cabeçalho `icone:` do `wiki-cache`), `sub` curto (`"×1"`, `"+ 1.500 almas"`, `"R1 · +5"`).
- Almas e níveis sempre do `ds2save.py levels`; dano sempre do `ds2calc.py ar`.
- `progresso` (aba Progresso) e `dano` (aba Dano) são opcionais; estado é texto (`derrotado`/`vivo`, `feito`/`pendente`), a página desenha o selo no estilo da wiki.
- `feiticos` (aba Feitiços), `agora` (painel no topo), `id` em passos e itens, e requisito `{"texto", "item"}` estão em `example/plano.json` e no spec `2026-10-07-buildsmith-feiticos-fila-ux-design.md`.

## Modelo da página

`template/index.html` (esqueleto) + `template/pagina.css` + `template/pagina.js`: o `prepare_page` junta tudo num `index.html` só (o CSP do servidor só aceita script e estilo inline). Layout v2: cabeçalho com retrato e "Trocar personagem", menu lateral (Plano · Coletar · Combate · Registro), lista + detalhe em Passos e Onde pegar. A seleção lista os personagens do save (`GET /api/ds2/personagens`); retrato = foto enviada, último print da Steam ou mosaico do equipamento.

**Equipamento:** seção no grupo Plano quando o plano tem `equipamento` (gerado pelo `ds2equip.py`): grade como o menu de equipamento do DS2 (mãos, armadura, anéis, sintonia) com Comparar / Agora / Plano, ganho por slot e painel com AR, quanto vem dos atributos, letras de escala (tabela de upgrade da wiki, `escala_wiki.py`, cache `~/.buildsmith/cache/ds2/escala.json`) e botão Onde pegar. O `prepare_page` completa ícones e letras sozinho.

**Ao vivo** (só pelo servidor local): a página lê `/api/ds2/<personagem>/save` (nível, almas, atributos, inventário, equipado e chefes derrotados, relidos quando o save muda) e `vivo.js` marca sozinha: item do plano no inventário ("✓ você tem ×N", também no mapa), passo feito no jogo (`equipar`: o que entra equipado e o que sai fora; `chefe`: flag do chefe; `compra`/`troca`: o item no inventário, com a quantidade do "→ N" do `sub`; `upgrade`: o item do nó com `sub` "+N" no reforço N; `nivel`: o atributo do nó `atributo` com "a → b" chegou em b) e o que avançou sem fechar ("VGR 14 de 20", "Dull Ember no inventário"). O que o jogo mostra feito conta em "N de M feitos" junto com as fogueiras marcadas. Nada é gravado: a marca some se o save voltar atrás.

**Mapa:** seção própria no menu (Coletar → Mapa), vista de cima estilo The Division: seletor de área e de andar, grade de 10 m, régua, zoom/arrastar/pinça, todos os itens da área com ícone da wiki (os do plano com moldura âmbar), fogueiras, filtros e clique no ponto. Zonas de fogueira em cores sequenciais (ordem pela distância a pé desde a entrada da área), chefes com retrato e estado do save, NPCs com retrato (os do plano com aro âmbar e o que o plano precisa deles no popover) e o painel "Rota da área" com as zonas em ordem; tudo sai do jogo e da wiki por script. Pelo servidor local a página mostra você em vermelho (posição do save, `/api/ds2/<personagem>/posicao`) e calcula "Rota até aqui" (`/api/ds2/rota`); a área onde você está entra sempre. Inimigos: HP, almas e drops do jogo; nome pela linha do EnemyParam ou pelo modelo do jogo (`ds2nomes.py`, com a prova), retrato e link da wiki pelo nome base; a wiki (`inimigos_wiki.py`, cache `~/.buildsmith/cache/ds2/inimigos_wiki.json`) só é consultada para o tipo que o jogo não nomeia, e só dá nome quando um único inimigo da wiki bate nos drops e nas almas ou na lista da área; chefe de outra área visto como inimigo (o Pursuer na Lost Bastille) ganha marca própria. Objetos (`objetos` em `mapas/<area>.json`): portas, névoas, alavancas, elevadores, pontes, escadas, Pharros e baús, com tamanho em metros e a rotação do jogo; porta cujo modelo diz a chave mostra a chave, o ícone e onde ela está no chão ("ver no mapa"). Filtros: Chaves (itens que são chave e portas com chave, ligado), Baús, Portas e alavancas e Inimigos (desligados): ligar mostra no 2D e no 3D, desligar some dos dois. O `prepare_page` faz tudo por script, sem gastar token: lê o jogo instalado (`ds2mapa.py`), gera a planta limpa por andar, acha os ícones (`icones_wiki.py`, cache em `~/.buildsmith/cache/ds2/icones.json`) e copia `mapas/<area>.json` + `mapas/indice.json` (áreas dos pontos, as 4 com mais itens do plano, a sua e depois todas as outras do jogo, cada uma com os IDs das fogueiras e a posição na rota de `games/ds2/rota.json`). Pelo servidor, o seletor separa liberadas e não liberadas pelas fogueiras acesas no save (`/api/ds2/<personagem>/posicao` traz `fogueiras`) e o mapa abre na área onde você está. "Ver no mapa" aparece em cada item (todos os pontos dele) e nas fontes/passos com `ponto` (rota pelo chão). Pelo servidor local o botão **3D** abre o cenário do jogo (`iso.js` + `vendor/three.module.js`, three.js r160): câmera fixa (arrastar, botão direito, roda, WASD/Q/E/R/F) e **Livre** (V: câmera de espectador em perspectiva, WASD voa para onde olha, segurar e arrastar olha em volta, E/Espaço sobe, Q/C desce), Interior (corte acima do andar pelo navmesh), Foco (escurece longe do centro) e os mesmos marcadores, filtros, andares e rota projetados por cima; inimigos e objetos usam os modelos do jogo (objetos no cenário, realçados pelos filtros; inimigos pelo filtro Inimigos), e o que não tem modelo legível vira uma forma na escala do cenário (cápsula do tamanho do inimigo, porta, baú, alavanca, elevador, névoa); o cenário vem de `/api/ds2/cena/<area>/` (extraído na primeira vez, em segundo plano). Na página publicada (sem servidor) ou sem WebGL 2 o 3D fica desligado com o motivo no botão. Sem jogo instalado: aviso `mapa indisponível` e a seção diz o motivo. Ponto que não existe na área: erro (corrija o `ref`).

## Passos

Padrão: **página local** (sem Artifact, mais barata). Só publique no Artifact quando o pedido tiver `publicar`.

1. Grave o `plano.json` em `<scratchpad>/buildsmith-plano.json` (sem scratchpad, rodando pela página: `~/.buildsmith/tmp/buildsmith-plano.json`).
2. Rode `python "<pasta>/scripts/prepare_page.py" <scratchpad>/buildsmith-plano.json ~/.buildsmith/paginas/<jogo>/<slug-do-personagem> --jogo <jogo>`.
   - Ele valida o plano, baixa os ícones (cache em `~/.buildsmith/cache/<jogo>/icons/`), copia o modelo e imprime `{"index", "files", "avisos"}`.
   - `{"error": ...}` → corrija o plano e rode de novo. `avisos` → ícones que não baixaram; o nó mostra a inicial do nome.
3. Servidor local (`<pasta>/../../app/serve.py`, porta 8642; rodando pela página ele já está de pé): se `http://127.0.0.1:8642/api/ping` não responder, suba em segundo plano com `pythonw "<app>/serve.py"` (Windows: `Start-Process pythonw -ArgumentList '"<app>\serve.py"'`). O jogador também pode abrir pelo atalho **Forja de Build** da área de trabalho (`app/instalar_atalho.py` cria): ele roda `app/abrir.py` (git pull, reinicia o servidor se o código mudou e refaz as páginas a partir do `plano.json` salvo, sem token). Desligar/reiniciar à mão: `serve.py parar` / `serve.py reiniciar`.
4. Responda a fila com `serve.py responder` / `serve.py confirmar` (veja a skill `build`).
   - Aberta pelo servidor, a página tem os botões **Atualizar plano** e **Responder fila**: rodam esta skill sem janela (`app/runner.py`, `claude -p`) e mostram etapas + microtexto. Visual: `docs/design-system.md`.
5. Responda com o link `http://127.0.0.1:8642/p/<jogo>/<slug-do-personagem>/` e as 2–3 linhas de `mudancas` mais importantes.

### Modo `publicar` (Artifact, para ver no celular)

- Prepare a página em `<scratchpad>/buildsmith-page/<jogo>/` (o Artifact só publica arquivos do diretório de trabalho ou do scratchpad).
- `~/.buildsmith/config.json`, chave `paginas.<jogo>.<personagem>`: **com URL** → `Artifact` `action: "read"` e depois publique com `url`, `file_path` = `index` e `files` da saída; **sem URL** → publique com `icon: "sword"`, `description` de uma frase e `capabilities: {"db": {}}`, e grave a URL.
- Nesse modo a fila fica no banco da página: leia e responda com `ArtifactData` (`pedidos`, `feitos`, `config/feiticos`).
