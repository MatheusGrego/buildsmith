# Simulador de armas e metas por arma — plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** a página calcula por código o AR de qualquer arma do jogador em qualquer reforço e infusão, e guarda metas por arma
que aparecem no slot quando a arma está equipada no save.

**Architecture:** `ds2calc` ganha a infusão (escala da linha `affect + k`, multiplicador do cabeçalho, máscara da
`CustomAttrSpecParam`); `ds2save` lê o byte da infusão; `ds2simula` (novo) junta AR + o que falta; o servidor expõe
`/simular` e a coleção `metas`, e `/combate` leva as metas; `equip.js` desenha o bloco Simular e as metas.

**Tech Stack:** Python 3.12 (stdlib + pycryptodome), JS sem build (template da página), pytest, node para os testes de JS.

**Spec:** `docs/superpowers/specs/2026-10-12-buildsmith-simulador-armas-design.md`

## Global Constraints

- Nenhum número de jogo na mão: tudo das tabelas (`regulation`) e do save; nomes de pedra pelo `games/ds2/ids`.
- Códigos de infusão: 0 Normal, 1 Fogo (Firedrake Stone), 2 Mágica (Faintstone), 3 Raio (Boltstone), 4 Sombria (Darknight
  Stone), 5 Veneno (Poison Stone), 6 Sangramento (Bleed Stone), 7 Raw (Raw Stone), 8 Enchanted (Magic Stone), 9 Mundane
  (Old Mundane Stone); Palestone (61160000) tira.
- Infusão: 2.000 almas + pedra, só McDuff; tirar: 1.000 almas + Palestone (wiki).
- Enchanted e Mundane, e infusão em arma com elemento próprio: "calculado, não conferido".
- `infusao=0` não muda nenhum número que já existe (os testes de menu de `test_ds2calc.py` seguem passando).
- Texto da página em pt-BR, sem frase de enchimento (memória: sem "ai-slop").

## Review Focus

- Arma que não aceita a infusão pedida (chama de piromancia, cajado com Fogo) → 400 com o motivo, página mostra só as aceitas.
- Nível pedido abaixo do que a cópia do jogador já tem → resultado sem custo de reforço e com aviso "o jogo não desfaz reforço".
- Duas cópias da mesma arma no inventário (ex.: dois Sorcerer's Staff) → usa a de maior reforço, como o resto do código.
- Meta de arma que o jogador já não tem → a lista de metas mostra "não está no inventário" em vez de quebrar o `/combate`.
- Estado com `metas` adulterado (tipos errados) → `clean_doc` recusa; `/combate` ignora documento inválido.

---

### Task 1: infusão no `ds2calc`

**Files:** Modify `skills/ds2-save/scripts/ds2calc.py`; Test `tests/test_ds2calc.py`

**Interfaces — Produces:**
- `ds2calc.INFUSOES: dict[int, tuple[str, str | None, str | None]]` (nome, elemento, pedra)
- `Calc.infusoes(item_id) -> list[int]` (sempre começa com 0)
- `Calc.physical_ar(item_id, level, stats, infusao=0)`, `physical_parts(..., infusao=0)`,
  `catalyst_ar(..., infusao=0)`, `catalyst_parts(..., infusao=0)`
- `Calc.weapon_ar(item_id, level, infusao, stats) -> dict[str, int]` e `Calc.weapon_parts(...) -> dict[str, dict]`
- `Calc.conferido(item_id, infusao) -> bool`

- [ ] Teste sintético: infusão 2 (Mágica) com cabeçalho 1,4 divide a base entre físico e mágico; Raw (7) com 1,15 só físico;
  infusão fora da máscara → `SaveError("... não aceita ...")`; `infusao=0` igual ao `physical_ar` atual.
- [ ] Teste real: Uchigatana +10 Mágica tem base 161 + 161 (`weapon_parts`), Raw +10 base 264, Fogo usa a linha
  ⌊(INT+FÉ)/2⌋; `infusoes` = 0..9 na Uchigatana, [0, 2, 4] no Sorcerer's Staff, [0] no Pyromancy Flame.
- [ ] Implementar: máscara por `reinforce_id` lendo `WeaponReinforceParam`+232 → `CustomAttrSpecParam` (u32); cabeçalho
  `<2f` da linha `affect + k` (interpolado pelo nível); físico = base × mult × (½ se k ∈ 1..6) + escalas da linha k;
  Enchanted soma escala mágica × bônus de INT ao físico; elemento da infusão = base do elemento × mult × ½ + escala do
  elemento × bônus da linha do elemento; elemento próprio da arma = `catalyst_ar` com a linha k.
- [ ] CLI `ds2calc ar ... [--int N --fth N --infusao K|nome]` → `{"ar": {...}, "conferido": bool}` além do `ar_fisico`.
- [ ] `pytest tests/test_ds2calc.py` verde; commit.

### Task 2: infusão no save e no Equipamento

**Files:** Modify `skills/ds2-save/scripts/ds2save.py`, `skills/ds2-save/scripts/ds2equip.py`; Test `tests/test_ds2save.py`,
`tests/test_ds2equip.py`

**Interfaces — Consumes:** Task 1. **Produces:** item de equipamento do snapshot com `"infusao": int`;
`ds2equip.peca(calc, names, item_id, nivel, stats, infusao=0)` com `infusao`, `infusao_nome`, `conferido`;
`ds2equip.copias(snapshot) -> dict[int, tuple[int, int]]` (id → (nível, infusão) da cópia de maior reforço);
troca `"R1=Old Knight Halberd:8:1"`.

- [ ] Teste: registro sintético `extra = 0x0308` → upgrade 8, infusão 3; save real: Uchigatana infusão 8.
- [ ] Teste: `equipamento` com a Uchigatana Enchanted mostra `infusao_nome == "Enchanted"` no slot R1 e AR calculado com a
  infusão; `ler_troca("R1=Old Knight Halberd:8:1") == ("R1", ("Old Knight Halberd", 8, 1))`.
- [ ] Implementar e commit.

### Task 3: `ds2simula.py`

**Files:** Create `skills/ds2-save/scripts/ds2simula.py`; Test `tests/test_ds2simula.py`

**Interfaces — Consumes:** Tasks 1–2, `ds2data.Data.upgrade_cost`. **Produces:**
`simular(calc, data, names, snap, item_id, nivel, infusao, atributos=None) -> dict` com `peca`, `agora` (ou `None`),
`infusoes` (`[{"k", "nome", "pedra"}]`), `nivel_max`, `conferido`, `falta` (`{"almas", "almas_tem", "materiais":
[{"item", "qtd", "tem"}], "ferreiro", "avisos": [...]}`); `armas_do_inventario(names, snap) -> list[dict]`.

- [ ] Testes: cópia +0 normal → +8 Fogo pede o custo do reforço + Firedrake Stone + 2.000 almas e McDuff; voltar a Normal pede
  Palestone + 1.000; nível abaixo do que tem → aviso e sem custo de reforço; arma que não tem → `agora is None` e aviso.
- [ ] CLI `ds2simula.py --personagem N --item NOME --nivel 8 --infusao fogo`; commit.

### Task 4: servidor (`/simular`, `metas`, `/combate`)

**Files:** Modify `app/serve.py`, `skills/ds2-save/scripts/ds2combate.py`; Test `tests/test_serve.py`, `tests/test_ds2combate.py`

**Interfaces — Consumes:** Task 3. **Produces:** `GET /api/ds2/<p>/simular?item&nivel&infusao`; `POST
/api/ds2/<p>/metas/<item_id>` `{item_id, nivel, infusao, ativa, desde}`; `/combate` com `armas`, `metas` (lista) e
`slot["meta"]` nos slots de mão; `ds2combate.combate(..., metas=None)`.

- [ ] Testes `clean_doc`: aceita meta válida; recusa nível 11, infusão 10, campo extra, `item_id` ≠ id do documento.
- [ ] Teste rota: `simular` 400 sem item / nível inválido; 200 com o simulador injetado.
- [ ] Teste `ds2combate`: meta da arma da R1 vira `slot["meta"]`; meta de arma fora do inventário fica na lista com aviso.
- [ ] Cache do `/combate` muda quando o arquivo de estado muda; commit.

### Task 5: página (`equip.js`)

**Files:** Modify `skills/build-page/template/equip.js`, `skills/build-page/template/pagina.js`,
`skills/build-page/template/pagina.css`; Test `tests/test_equip_js.py` (novo, node)

**Interfaces — Consumes:** Task 4 (`/simular`, `metas`, `armas`). **Produces:** `buildsmithEquip.ligar(raiz, p, ctx)` com
`ctx = {base, headers, atualizar}`; puras `metaTexto`, `faltaTexto`, `infusaoOpcoes`.

- [ ] Teste node das puras: `metaTexto({nivel: 8, infusao_nome: "Fogo"}) == "+8 Fogo"`; `faltaTexto` lista o que falta
  com "tem N" e as almas.
- [ ] Bloco Simular no painel de slot de mão (só com servidor): seletores arma/nível/infusão, resultado com Δ, botão Virar meta /
  Tirar meta; selo "meta" no slot; coluna Meta no detalhe; lista Metas.
- [ ] `pagina.js` passa `armas`/`metas` do `/combate` e o `ctx`; conferir no navegador com o save real; commit.
