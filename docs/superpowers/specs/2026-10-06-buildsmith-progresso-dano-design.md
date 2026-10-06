# buildsmith — progresso lido do save e aba de dano

Data: 2026-10-06
Status: aprovado em conversa ("pode implementar os dois"; a lista de progresso segue o design system da wiki, sem check verde)
Complementa: `2026-10-06-buildsmith-pagina-v2-design.md`

## Objetivo

1. Saber **de fato** o que o jogador já fez (chefe morto, compra feita, evento) lendo o save, sem dedução por inventário.
2. Mostrar **por que** cada passo do plano importa, com o dano calculado pelas regras do próprio jogo: agora × depois.

## Fatos descobertos (validados em 2026-10-06 contra 10 backups reais)

### Flags globais no save

- Cada slot de personagem `n` tem um bloco de estado do mundo `USER_DATA0(10+n)` (slot 1 → `USER_DATA011`, ~490 KB).
- Flags globais 100000–109999: a flag `N` fica no byte `0x26DAA + (N − 100944) // 8`, bit `7 − (N − 100944) % 8` (o bit mais alto primeiro). Há uma cópia idêntica 0x604C bytes depois.
- Validação: Last Giant (100971) → Pursuer (100968) → Dragonrider (100959) → Old Dragonslayer (100960) → Flexile Sentry (100961) ligam nessa ordem ao longo dos backups; Ruin Sentinels (100962) desligada.

### Tabelas de regras do jogo (`Game/enc_regulation.bnd.dcx`)

- AES-128-CTR, chave `401781 30DF0A9454 3309E171ECBF254C` (pública, usada por ferramentas de modding); IV = `0x80` + primeiros 11 bytes do arquivo + `00 00 00 01`; dados a partir do byte 32. O resultado é DCX (DFLT/zlib) com um BND4 de 228 params.
- PARAM do DS2: cabeçalho de 0x40 bytes; contagem de linhas `u16` em `0x0A`; linhas a partir de `0x40`, 24 bytes cada (`u64 id, u64 offset dos dados, u64 offset do nome`).
- `BossBattleParam.map_clear_global_event_flag` (offset 20) = flag global de "chefe derrotado". Ex.: Pursuer 100968, Ruin Sentinels 100962.
- `ShopLineupParam` = lojas; o histórico de compras no save (slot, `0x830`, pares `u32 id da linha, u32 quantidade`, termina em zero) aponta para essas linhas.
- AR físico de arma (validado: Uchigatana +5 = 218, Cleric's Parma = 54, punho = 49 com FOR 10 / DES 18):
  - `base(L) = dano + (dano_max − dano) × L / nivel_max` (`WeaponReinforceParam`)
  - `bonus = escala_FOR(L) × bonus_FOR(FOR) + escala_DES(L) × bonus_DES(DES)` (`WeaponStatsAffectParam` × `PhysicalStatsPerLevelStatValuesParam`)
  - `AR = floor((base + bonus) × damage_mult_physical / 100)`
- Catalisadores (cajado, chama) **não** seguem essa fórmula (spell buff); ficam como "—" até serem validados.

Nada do jogo vai para o repositório: o script lê o `enc_regulation.bnd.dcx` instalado na máquina. Paramdefs não são copiados; o código guarda só os offsets dos campos usados.

## Componentes

| Arquivo | Responsabilidade |
|---|---|
| `skills/ds2-save/scripts/ds2save.py` | + `bnd4_entries()` genérico; + `progresso` no `snapshot` (chefes, compras, flags ligadas, eventos aprendidos); + comando `flags-diff` |
| `skills/ds2-save/scripts/ds2regulation.py` | acha, decifra e descomprime o regulation; lê PARAMs com layouts fixos |
| `skills/ds2-save/scripts/ds2calc.py` | AR físico de arma; CLI `ar` |
| `games/ds2/bosses.json` | flag → nome do chefe, área e página da wiki (fatos tirados do `BossBattleParam`) |
| `games/ds2/lojas.json` | prefixo da linha de loja → NPC |
| `~/.buildsmith/flags/ds2.json` | eventos aprendidos pelo jogador (`nome`, `flags`, `data`) |

## `snapshot` → `progresso`

```json
"progresso": {
  "chefes": [{"flag": 100968, "nome": "The Pursuer", "derrotado": true}],
  "compras": [{"linha": 76600301, "loja": "Carhillion of the Fold", "item_id": 31020000, "item": "Great Soul Arrow", "qtd": 1}],
  "flags": [100959, 100960, ...],
  "eventos": [{"nome": "Straid libertado", "feito": true}]
}
```

- `compras[].item` precisa do regulation; sem ele, `item` = `null` e o resto segue.
- `flags-diff --antes A.json --depois B.json` imprime `{"ligou": [...], "desligou": [...]}`.

## Aprender eventos

1. O jogador vai ao menu e roda `/buildsmith:build ds2` (leitura "antes").
2. Faz o evento, volta ao menu e roda `/buildsmith:build ds2 libertei o Straid`.
3. A skill roda `flags-diff` entre os dois snapshots. As flags que **ligaram** viram o evento `Straid libertado` em `~/.buildsmith/flags/ds2.json`.
4. Daí em diante o evento aparece em `progresso.eventos` sozinho.

## Plano e página

- `plano.json` ganha:
  - `progresso`: `{"chefes": [{"no": Nó, "estado": "derrotado"|"vivo"}], "compras": [{"loja": Nó, "item": Nó, "qtd": n}], "eventos": [{"nome": "...", "estado": "feito"|"pendente"}]}`
  - `dano`: `[{"arma": Nó, "agora": 218, "depois": 236, "detalhe": "DES 18 → 25", "por_causa": [Nó]}]` (`agora`/`depois` inteiros ou `"—"`).
- Página: aba **Progresso** (tabelas da wiki: Chefe | Estado; Loja | Item | Qtd; Evento | Estado) e aba **Dano** (Arma | Agora | Depois | Diferença | Por causa de). Estado é um selo em Marcellus SC no estilo `.badge`: "Derrotado"/"Feito" com borda dourada (`--link`), "Vivo"/"Pendente" em texto apagado. Sem ícones de check.
- A skill `build` tira do plano os passos cujo chefe/compra/evento já consta como feito.

## Testes

- `ds2regulation`: round-trip sintético (BND4 → DCX zlib → AES-CTR); PARAM sintético; real (pula se o jogo não estiver instalado): Uchigatana `WeaponReinforceParam` 115/230.
- `ds2calc`: AR sintético; real: Uchigatana +5 = 218, Cleric's Parma = 54, punho = 49.
- `progresso`: flag sintética no bloco do mundo; compras sintéticas; `flags-diff`; real: Pursuer derrotado, Ruin Sentinels vivo.
- `validate_plano`: `progresso` e `dano` opcionais, mas válidos quando presentes.
