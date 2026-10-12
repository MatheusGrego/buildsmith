# Simulador de armas e metas por arma (Equipamento)

Data: 2026-10-12 · Pedido do jogador: "selecionar o upgrade e a imbuição da arma no Equipamento; quando eu equipo ela no jogo, o
equipamento herda a build; e posso ir modificando pelo buildsmith". Escolha do jogador: **calculadora + botão "virar meta"**.

## Objetivo

Na seção Equipamento (servidor local), o jogador testa qualquer arma que tem (ou do catálogo) com qualquer reforço (+N) e
qualquer infusão que a arma aceita, e vê o AR calculado **por código** (tabelas do jogo, sem IA) contra o que está equipado. Uma
combinação pode virar **meta** daquela arma. Quando a arma está equipada no save, o slot mostra a meta ao lado do "agora", com o
que falta (pedra, materiais, almas, ferreiro). A meta fica guardada no estado local da página e muda pela própria página.

Sucesso: "Old Knight Halberd +8 Fogo" mostra o AR por elemento sem ninguém abrir o chat; equipar a halberd no jogo faz o slot R1
mostrar "agora +0 normal → meta +8 Fogo · faltam 3 Titanite Chunk, 1 Firedrake Stone, 11.460 almas".

## O que o jogo diz (investigação de 2026-10-12)

- **Escala por infusão:** `WeaponStatsAffectParam` tem 10 linhas por arma: `stats_affect_id + k`, k = código da infusão.
- **Multiplicador de dano:** os 2 floats do cabeçalho de cada linha: 1,0 (normal, Enchanted), 1,4 (elementais, veneno,
  sangramento), 1,15 (Raw), 0,5 (Mundane). Elemental divide meio a meio entre físico e o elemento: Uchigatana +10 = 230 × 1,4 / 2
  = 161 físico + 161 do elemento (bate com a wiki); Raw +10 = 230 × 1,15 = 264 (bate com a wiki).
- **Código no save:** byte 1 do campo `extra` do registro de inventário (byte 0 = reforço). Visto: Uchigatana `0x8` → `0x808`
  depois de 1 Magic Stone.
- **Arma aceita a infusão k** quando o bit k da máscara está ligado: `WeaponReinforceParam` +232 = id da linha em
  `CustomAttrSpecParam` (4 bytes = máscara). Ex.: espadas 0x3ff (todas), cajados 0x15 (0, 2, 4), sinos 0x19 (0, 3, 4),
  chamas de piromancia id 0 (nenhuma).
- **Código ↔ elemento ↔ pedra:** pela máscara e pela wiki (cajado aceita Mágica e Sombria; sino aceita Raio e Sombria; Lizard
  Staff "infundir com Faintstone"): 1 Fogo (Firedrake Stone), 2 Mágica (Faintstone), 3 Raio (Boltstone), 4 Sombria
  (Darknight Stone), 5 Veneno (Poison Stone), 6 Sangramento (Bleed Stone), 7 Raw (Raw Stone), 8 Enchanted (Magic Stone,
  confirmado no save), 9 Mundane (Old Mundane Stone). Palestone tira a infusão. A ordem dos ids das pedras **não** é a dos
  códigos.
- As 10 linhas de escala existem para toda arma, até as que não aceitam infusão: a permissão vem só da máscara.
- **Serviço:** só o Steady Hand McDuff infunde: 2.000 almas + a pedra; tirar: 1.000 almas + Palestone (wiki, cache
  `steady-hand-mcduff.md`).

Não conferido no menu ainda: Enchanted (para onde vai o bônus de INT) e Mundane. A página marca esses dois como "calculado, não
conferido" até um teste com o valor do menu do jogo.

## Componentes

1. **`ds2calc.Calc.weapon_ar(item_id, nivel, infusao, stats)`** → `{"fisico": n, "magico": n, ...}` só com os elementos > 0, e
   `weapon_parts(...)` com base e atributos por elemento (como `catalyst_parts`). `infusao=0` dá o mesmo que `physical_ar` hoje
   (e o elemento próprio da arma, como em `ds2equip.peca`). `infusoes(item_id)` → códigos aceitos (máscara). Catalisador
   infundido: o multiplicador do cabeçalho é 1,0 e só a escala muda (AR do catalisador pela linha `affect + k`). Constantes `INFUSOES` (código → nome, elemento, pedra id/nome). Linha de bônus do
   elemento pelos atributos já existe (`bonus_rows`). CLI: `ds2calc ar --infusao fogo|3`.
2. **`ds2save.parse_slot`**: item de equipamento ganha `"infusao": k` (0 = nenhuma). `ds2equip.peca` usa a infusão da cópia
   escolhida (a de maior reforço; o save só guarda o id na mão) e mostra o nome da infusão no `sub`.
3. **`ds2simula.py`** (novo, puro): `simular(calc, data, names, snap, item_id, nivel, infusao, atributos=None)` →
   `{item, nivel, infusao, ar, partes, requisito, requisito_ok, nivel_max, infusoes, agora: {...mesma arma como está no save ou
   null}, falta: {almas, materiais[{item, qtd, tem}], pedra{item, tem} | null, ferreiro}}`. Custo do reforço por
   `ds2data.custo-upgrade` a partir do nível da cópia que o jogador tem; infusão nova = pedra + 2.000 almas; voltar ao normal =
   Palestone + 1.000.
4. **Servidor:**
   - `GET /api/ds2/<personagem>/simular?item=<id>&nivel=<n>&infusao=<k>` → `ds2simula.simular` com o save de agora.
   - Coleção nova `metas` no estado (`POST /api/ds2/<personagem>/metas/<item_id>`): `{item_id, nivel, infusao, ativa, desde}`,
     validada em `clean_doc` (ints no limite, sem campo extra), máximo 40 ativas.
   - `/combate` passa as metas ativas para `ds2combate`: cada slot de arma equipada com meta ganha `meta` (o resultado do
     `simular`); `armas` = armas do inventário (id, nome, nível, infusão) para o seletor. A chave de cache do combate inclui o
     arquivo de estado.
5. **Página (`equip.js`)**: no painel da arma, bloco **Simular**: seletor de arma (as do inventário; a do slot vem marcada),
   nível (0..máx.), infusão (só as aceitas, com o nome da pedra). Resultado: AR por elemento e Δ contra o equipado, requisito,
   o que falta. Botão **Virar meta** / **Tirar meta**. Slot com meta mostra um selo "meta +8 Fogo" e, na coluna Plano, a meta
   (ela vence a troca do plano naquele slot). Lista "Metas" abaixo da grade com as metas de armas que não estão na mão.

## Fluxo

Página → `GET simular` a cada mudança de seletor (debounce) → painel. "Virar meta" → `POST metas/<id>` → `/combate` refeito
(chave de cache muda) → slot mostra a meta. Equipar a arma no jogo → save muda → `/combate` refeito → a meta aparece no slot dela.

## Erros

Arma fora da `WeaponParam` ou infusão não aceita → 400 com o motivo. Nível acima do máximo → 400. Sem save / jogo ausente → 503
(como `/combate`). Página publicada (sem servidor): o bloco Simular não aparece; as metas não existem lá.

## Testes

- `ds2calc`: params sintéticos (fórmula elemental, Raw, Mundane, infusão não aceita) e reais (Uchigatana +10 Mágica = 161 base de
  cada lado; Raw +10 = 264 de base; infusão 0 = `physical_ar`, que já bate com o menu).
- `ds2save`: byte de infusão lido de um registro sintético e do save real (Uchigatana = 8).
- `ds2simula`: falta (materiais que tem/não tem, pedra, almas) com snapshot sintético.
- `serve`: `clean_doc` de `metas`, rota `simular` (400/200), `/combate` com meta.
- JS (`node`, como `test_catalogo_js.py`): funções puras do Simular (texto da infusão, Δ por elemento).
