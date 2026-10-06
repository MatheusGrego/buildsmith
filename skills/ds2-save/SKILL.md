---
name: ds2-save
description: Lê o save do Dark Souls II SotFS (PC) e devolve a ficha do personagem em JSON (atributos, nível, almas, equipado, inventário) ou o custo em almas de uma faixa de níveis. Use sempre que precisar de dados reais do personagem ou de custo de nível no DS2.
---

# ds2-save

Script: `scripts/ds2save.py` nesta pasta. Precisa de Python 3 e `pycryptodome` (`pip install pycryptodome`).

## Comandos

| Comando | Devolve |
|---|---|
| `python "<pasta>/scripts/ds2save.py" slots` | personagens do save: slot, nome, nível |
| `python "<pasta>/scripts/ds2save.py" snapshot [--slot N] [--save CAMINHO]` | ficha completa em JSON |
| `python "<pasta>/scripts/ds2save.py" levels --from A --to B` | custo de cada nível de A+1 até B e o total |

`<pasta>` é o diretório base desta skill. Sem `--save`, o script usa o arquivo mais recente entre `DS2SOFS*.sl2` e `DS2SOFS*.co2` (Seamless Co-op) em `%APPDATA%\DarkSoulsII\*\`. O save nunca é alterado.

## Regras

- Erro sai como `{"error": "..."}` com código 1. Mostre a mensagem ao usuário; não invente atributos.
- "mais de um personagem" → rode `slots`, pergunte qual é o personagem e passe `--slot`.
- Custo de alma: sempre use `levels`. Nunca some custos de cabeça.
- `hands` usa `L1 R1 L2 R2 L3 R3` (mão esquerda/direita, slots 1–3). `upgrade` é o +N da arma; `null` em consumíveis.
- Itens `desconhecido #ID` existem no save mas não estão nas listas de `games/ds2/ids/`; cite como desconhecidos. `3400000` numa mão costuma ser mão vazia.
- Equipamento não mostra infusão (ainda não mapeada); pergunte ao usuário se importar.
