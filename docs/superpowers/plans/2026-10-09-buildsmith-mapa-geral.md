# Mapa geral estilo The Division — plano

- Status: concluído (0.10.0)
- Data: 2026-10-09
- Decisor: Matheus (aprovado no chat: 2D de cima, todos os itens com ícone, seção própria + "Ver no mapa")
- Substitui: o mapa embutido por item da Entrega B (`2026-10-09-buildsmith-v2-selecao-mapa.md`, tarefas 11–12)

## Contexto

- O mapa atual é um SVG isométrico por fonte/passo, recortado em volta da rota (`skills/build-page/template/mapa.js`). Não tem zoom, grade nem visão da área inteira; os ícones ficam grandes e a malha aparece como triângulos.
- O navmesh do jogo é feito para a IA andar, não para ser mapa: na Lost Bastille são 6.269 triângulos e 4.526 de 11.629 arestas parecem "borda" só porque os pedaços não se encaixam (medido em 2026-10-09 no cache `m10_16_00_00.json`).
- As alturas se separam em andares: picos de área em −78, −70, 0, 8, 13, 22 e 30 m na Lost Bastille.
- Ícones hoje só existem para os itens do plano (`prepare_page` baixa da wiki).

## Decisão

1. **Planta limpa por andar (Python, no cache):** andares detectados pelo histograma de área por altura; cada andar é rasterizado numa grade de 1 m, as frestas são fechadas (dilatar e erodir 1 célula) e o contorno vira polígono simplificado. Cada ponto (fogueira, item, inimigo) ganha o andar dele.
2. **Ícone de todo item da área:** achado na página do item na wiki (só hosts da Fextralife), guardado no cache uma vez por item; item sem ícone vira losango.
3. **Seção "Mapa" na página:** vista de cima 2D, seletor de área e de andar, grade de 10 m (forte a cada 50 m), régua de escala, zoom (roda, pinça, botões) e arrastar, ícones com tamanho de tela fixo e nome ao aproximar, filtros (Fogueiras · Itens do plano · Outros itens · Inimigos), clique mostra o conteúdo do ponto. "Ver no mapa" em Onde pegar e Passos abre a seção no andar certo, com zoom na rota e nos passos numerados.
4. **Página recebe planta e pontos, não triângulos.** O mapa embutido por item sai.

## Opções consideradas

1. **Isométrico da área inteira** — descartado: andares se sobrepõem e escondem pontos.
2. **Desenhar os triângulos com contorno de borda** — descartado: as frestas entre pedaços viram paredes falsas (4.526 bordas).
3. **Raster + contorno por andar** — escolhido: fecha as frestas, dá parede nítida e polígonos leves.
4. **Ícones extraídos das texturas do jogo** — adiado: exige decodificar DDS e achar o ID de ícone de cada item; a wiki já tem os ícones.

## Consequências

- (+) Mapa legível, uma vez por área, sem gastar token: tudo vem de script e cache.
- (+) Página mais leve: polígonos no lugar de triângulos.
- (−) Primeira execução extrai as 28 áreas (~1 min) e baixa os ícones (~1 min por área nova).
- (−) Escada e rampa entram no andar mais próximo; uma rampa longa pode aparecer cortada entre dois andares.
- (−) Portas, alavancas e quedas continuam fora da rota (aviso fica na legenda).

## Critério de aceite

- Lost Bastille: andares detectados incluem alturas a ±2 m de −78, 0, 8, 13 e 22; cada andar sai com polígonos fechados; nenhum ponto sem andar.
- Duas malhas sintéticas encostadas com fresta de 0,3 m saem como um polígono só.
- Página: a seção Mapa abre a Lost Bastille com grade, régua, andares, ícones e filtros; "Ver no mapa" da fonte de Large Titanite Shard e do passo do Straid centraliza e desenha a rota; funciona em 375 px sem rolagem lateral.
- `python -m pytest -q` verde.

## Tarefas

- [x] **1. Planta por andar** (`ds2mapa.py`): detectar andares, rasterizar, fechar frestas, contornar, simplificar, andar de cada ponto; guardado no JSON da área com versão (refaz se a versão mudar). *Pronto quando:* testes sintéticos (dois andares; fresta fechada; ponto no andar certo) e o teste da Lost Bastille passam.
- [x] **2. Ícones da wiki para todo item** (`build-page/scripts`): achar o ícone pela página do item, cache de nome → URL (inclusive "não achou", com data), baixar pelo `IconStore`. *Pronto quando:* teste com página falsa extrai a URL certa, recusa host de fora e reaproveita o cache.
- [x] **3. Áreas na pasta da página** (`prepare_page.py`): áreas dos pontos + áreas onde há itens do plano; cada `mapas/<area>.json` com andares, fogueiras, itens (com ícone local e marca "plano"), inimigos; `mapas/indice.json`; pontos do plano ganham o andar. *Pronto quando:* testes mostram área sem triângulos, item do plano marcado, área incluída só pelo nome do item, aviso quando falta o jogo.
- [x] **4. Seção Mapa** (`mapa.js`, `pagina.js`, `pagina.css`): visualizador 2D com tudo da Decisão 3; "Ver no mapa" nas fontes e passos; sai o mapa embutido. *Pronto quando:* funções puras testadas no node (encaixe da vista, visibilidade por andar) e conferido no navegador em desktop e 375 px.
- [x] **5. Docs, versão e publicação**: skills (`build`, `build-page`, `ds2-save`), design system (Mapa), README, plugin 0.10.0, página real refeita, push na `master`, plugin atualizado. *Pronto quando:* suíte verde e página real abrindo a seção Mapa.

## Glossário

- **Navmesh:** malha de triângulos onde a IA pode andar; é o "chão" que o jogo conhece.
- **Rasterizar:** pintar os triângulos numa grade de quadradinhos (aqui, 1 m) para trabalhar com "tem chão / não tem".
- **Fechar frestas (dilatar e erodir):** engordar a área pintada uma célula e depois emagrecer de volta; buracos menores que a célula somem.
- **Contorno (marching squares):** percorre a grade e devolve a linha que separa chão de vazio — vira a parede no mapa.
- **Simplificar (Douglas-Peucker):** tira pontos quase em linha reta do contorno, mantendo a forma com menos vértices.
- **viewBox:** a janela do SVG; zoom e arrastar mudam essa janela, não o desenho.
