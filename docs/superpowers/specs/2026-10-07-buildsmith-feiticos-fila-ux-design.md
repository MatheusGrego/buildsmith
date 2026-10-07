# buildsmith — feitiços, fila de pedidos, checkbox de fogueira e painel Agora

Data: 2026-10-07
Status: aprovado em conversa ("pode começar")

## 1. Dano de feitiço (dados do jogo)

Validado contra o menu Status (FOR 10 · DES 18 · INT 26 · FÉ 6):

- Bônus por elemento (`PhysicalStatsPerLevelStatValuesParam`, linha = valor do atributo):
  mágico = linha INT · fogo = linha ⌊(INT + FÉ)/2⌋ · raio = linha FÉ · sombrio = linha min(INT, FÉ). Bate com o menu: 108 / 99 / 54 / 63.
- AR de catalisador por elemento = ⌊(base(L) + escala(L) × bônus) × mult/100⌋ (mesma interpolação de nível da arma).
  Menu = soma dos elementos: Sorcerer's Staff +2 = 190 + 166 = **356** ✓; Pyromancy Flame = **204** ✓.
- Feitiço: `SpellParam` (requisitos INT/FÉ, `right_damage_id`, slots, usos por faixa) → `PlayerDamageParam` (`damage_type_0`: 1 mágico, 2 raio, 3 fogo, 4 sombrio; `damage_mult`).
  AR do feitiço = ⌊AR do catalisador no elemento × `damage_mult`⌋. Ex.: Soul Arrow = ⌊190 × 0,85⌋ = 161.
  O jogo não mostra esse número no menu: a página marca como "calculado". `damage_mult` = 0 (feitiços teleguiados, dano nos projéteis filhos) → "—".
- Sintonia: slots e faixa de usos pela linha ATN (`attunement_slots`, `cast_amount_tier`). ATN 30 = 6 slots, faixa 3.

CLI: `ds2calc.py catalisador`, `ds2calc.py feitico`.

## 2. Banco da página (capability `db`)

A página declara `capabilities: {db: {}}` (só o dono escreve). O banco fica no servidor, junto da página: qualquer chat que rode `/buildsmith:build` acha a página pela URL em `~/.buildsmith/config.json` e lê/escreve o mesmo banco (ferramenta `ArtifactData`).

| Documento | Conteúdo | Quem escreve |
|---|---|---|
| `pedidos/<slug>` | `texto`, `origem`, `estado` (`na_fila` / `respondido`), `criado_em`, `item_id` da resposta | página cria; skill responde |
| `feitos/<passo_id>` | `marcado`, `em`, `confirmado` (true / false / null) | página marca; skill confirma pelo save |
| `config/feiticos` | `selecionados`: ids de feitiço | página |

Sem `db` (página aberta fora do viewer): os botões viram "Copiar pedido" com `/buildsmith:build ds2 onde pegar: <texto>`.

## 3. Plano v4

- `passos[].id` e `itens[].id`: slugs únicos (âncoras e chaves do banco).
- `fontes[].requisito`: texto **ou** `{"texto": "...", "item": "<itens.id>"}` (vira link para o item).
- `agora`: `{"acoes": [ids de passo, até 3], "almas": n, "faltam": [Nó]}` — painel no topo.
- `feiticos`: `{"catalisador": Nó, "ar": {"magico": 190, ...}, "slots": {"total": 6}, "lista": [{"id", "no", "estado": "equipado|tem|sugerido", "elemento", "ar", "usos", "slots", "requisito", "requisito_ok"}]}`.

## 4. Página

- **Painel Agora** acima das abas: 3 próximas ações (com checkbox), almas que faltam, materiais que faltam.
- **Checkbox de fogueira**: ícone da fogueira da wiki; apagada (cinza) = pendente, acesa (dourada, brasa) = feito. Grava em `feitos/<id>`; "confirmado pelo save" quando a skill confirmar.
- **Pesquisar**: botão em cada requisito sem item ligado e em cada item marcado `tem`; grava em `pedidos/`; mostra selo "Na fila". Aba **Fila** lista pedidos e respostas.
- **Fontes compactas**: mostra "Mais cedo" e "Mais rentável"; as demais em "Ver todas (n)".
- **Aba Feitiços**: tabela com AR calculado, usos, slots, requisito; seleção com a mesma fogueira; contador de slots usados × total; grava em `config/feiticos`.

## 5. Skill `build`

Passo 0 novo: ler `pedidos`, `feitos` e `config/feiticos` da página (ArtifactData). Responder cada pedido (wiki-cache + ds2data) como entrada em `itens`, marcar `estado: respondido` + `item_id`. Confirmar `feitos` pelo save quando der (chefe/compra/item/upgrade); passo marcado sai do plano. Usar a seleção de feitiços nas sugestões de sintonia.
