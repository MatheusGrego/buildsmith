# buildsmith — fontes ordenadas (mais cedo / mais rentável) e passos por tipo

Data: 2026-10-07
Status: aprovado em conversa ("faz isso que te falei"); UX/UI será revista depois
Complementa: `2026-10-06-buildsmith-progresso-dano-design.md`

## Problemas

1. A página cita itens (Large Titanite Shard, Titanite Slab, Moonlight Greatsword) sem dizer onde conseguir.
2. Passos misturados; não estão em ordem de execução nem separados por tipo.
3. Para cada item falta: a forma **mais cedo** (a partir de onde o jogador está) e a forma **mais rentável** (farm repetível).

## Decisões

### Passos agrupados por tipo

Ordem fixa dos grupos na aba Passos; dentro de cada grupo, ordem cronológica de execução:

| `tipo` | Grupo |
|---|---|
| `equipar` | Equipar (agora, sem custo) |
| `explorar` | Explorar (itens no mapa, baús, NPCs a libertar) |
| `chefe` | Chefes |
| `troca` | Trocas de alma (alma de chefe ➜ NPC ➜ item) |
| `compra` | Compras (loja ➜ item, com preço) |
| `upgrade` | Upgrades (material × qtd + almas ➜ ferreiro ➜ +N) |
| `farm` | Farms |
| `nivel` | Nível (fases) |

### Fontes de item

`itens[]` passa a ser `{"item": Nó, "fontes": [Fonte], "dados": [Linha]}` (o antigo `onde` vira uma fonte).

```json
{"tipo": "compra|troca|drop|bau|farm|recompensa",
 "fluxo": [Nó], "requisito": "texto curto", "acesso": "agora|em_breve|tarde",
 "rendimento": "1 por sombra concluída", "destaques": ["mais_cedo", "mais_rentavel"]}
```

- Ordenadas por `acesso` (agora → em breve → tarde).
- Exatamente uma fonte com `mais_cedo` e no máximo uma com `mais_rentavel` (a melhor fonte repetível: farm infinito, loja com estoque infinito, respawn com Bonfire Ascetic).
- **Regra de fechamento**: todo nó `item` citado em `passos`, `dano` ou `comparacao.ajuste` precisa ter entrada em `itens`, exceto quando `"tem": true` (o jogador já possui). O validador bloqueia a publicação se faltar.

### Status de acesso calculado a partir do progresso

- `games/ds2/rota.json`: ordem das áreas segundo a página "Game Progress Route" da wiki (fonte e data no arquivo).
- Área mais avançada = maior índice entre as áreas dos chefes derrotados (`bosses.json`).
- `agora`: área com índice ≤ mais avançada + 1 (ou hubs: Majula, Things Betwixt); `em_breve`: até +4; `tarde`: além disso.

### Dados do jogo (exatos) — `ds2data.py`

| Comando | Fonte | Exemplo validado |
|---|---|---|
| `onde-comprar --item X` | `ShopLineupParam` (`material_id` = 0) + `ItemParam.base_price` × `price_rate` | Large Titanite Shard: McDuff, estoque ∞, 2.500 |
| `trocas --item X` / `--alma X` | `ShopLineupParam` com `material_id` (alma) | Moonlight Greatsword ⇐ Old Paledrake Soul (Ornifex) |
| `custo-upgrade --arma X --de A --ate B` | `ReinforceCostParam` | Uchigatana +6: 3 × Large Titanite Shard + 1.320 almas |
| `acesso --snapshot S.json` | `rota.json` + progresso | Lost Bastille: agora |

Locais de baú, drops e farms vêm da `wiki-cache` (com fonte); números sem fonte = "—".

### Save de teste

`find_save` lê `save_file_extension` do `SeamlessCoop/ds2sc_settings.ini` e prefere o save com essa extensão.

## Página

- Passos: um bloco por grupo (título em Marcellus SC + contagem), numeração dentro do grupo.
- Onde pegar: por item, tabela wiki `# | Como | Requisito | Acesso | Rendimento`, com selos "Agora / Em breve / Tarde" e "Mais cedo / Mais rentável" no mesmo estilo dos selos de estado.

## Testes

- `ds2data`: sintético para cada comando; real (pula sem o jogo): McDuff vende Large Titanite Shard a 2.500 com estoque ∞; Uchigatana +6 custa 3 Large Titanite Shards + 1.320; Ornifex troca Old Paledrake Soul por Moonlight Greatsword.
- `acesso`: área mais avançada a partir de flags sintéticas.
- `find_save`: ini com extensão `teste` escolhe `DS2SOFS0000.teste`.
- `validate_plano`: tipos de passo novos, fontes, destaques únicos, regra de fechamento.
