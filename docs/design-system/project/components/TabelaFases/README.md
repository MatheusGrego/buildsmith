# TabelaFases

Tabela da aba Fases que ordena o gasto de almas por fase de um atributo, com o custo de cada fase, o acumulado e o total até o nível final.

## Quando usar

- Use na aba Fases, com a seção "Fases de nível", uma linha por fase.
- Use para responder "quanto falta e em que ordem subir".

## Quando não usar

- Não use para mostrar o valor do atributo. Isso é a BarraAtributo.
- Não use para custo de compra ou upgrade. Esses entram como Linha no passo ("Almas" `0` → `−2.500`, "faltam 2.500").

## O que entra

`fases[]`: `{"nome", "atributo", "de", "ate", "almas"}`. `de`, `ate` e `almas` são inteiros; `atributo` é um dos 9 (`validate_plano.py` L91–L96). Exemplo real (`example/plano.json` L508–L537):

```json
{"nome": "VGR 9 → 20", "atributo": "VGR", "de": 65, "ate": 76, "almas": 82736},
{"nome": "INT 26 → 40", "atributo": "INT", "de": 76, "ate": 90, "almas": 138935},
{"nome": "END 6 → 15", "atributo": "END", "de": 90, "ate": 99, "almas": 112167},
{"nome": "DEX 18 → 25", "atributo": "DEX", "de": 99, "ate": 106, "almas": 99790}
```

O acumulado e o total não vêm do plano: a página soma `acc += f.almas` linha a linha.

## Anatomia

`phases()` (`skills/build-page/template/index.html` L340–L353):

```html
<section><h2>Fases de nível</h2><div class="tw"><table>
  <thead><tr><th>Fase</th><th>Nível</th><th class="r">Custo (almas)</th><th class="r">Acumulado</th></tr></thead>
  <tbody><tr><td><span class="cell-ic"><img src="icons/stat-VGR.png" alt="" onerror="this.remove()">VGR 9 → 20</span></td><td>65 → 76</td><td class="r neg">82.736</td><td class="r">82.736</td></tr>…</tbody>
  <tfoot><tr><td colspan="3">Total até o nível 106</td><td class="r">433.628</td></tr></tfoot>
</table></div></section>
```

| Coluna | Conteúdo | Visual |
|---|---|---|
| Fase | ícone do atributo e `nome` em `.cell-ic` | `corpo` em `head` |
| Nível | `de → ate`, cru, sem `fmt` | `head` |
| Custo (almas) | `almas` com `fmt` | `td.r.neg`: sempre `neg`, peso 500 |
| Acumulado | soma até a linha, com `fmt` | `td.r`, `head` |
| rodapé | "Total até o nível N" em `colspan="3"` e o total | `tfoot td` em `rodape-tabela` |

`N` é o `ate` da última fase. O resto da anatomia é a TabelaWiki.

O ícone `icons/stat-<ATR>.png` não está neste sistema. Sem o arquivo a página remove a imagem (`onerror="this.remove()"`); o preview já vem sem ela.

## Estados e variantes

- Lista vazia: `<section><h2>Fases de nível</h2><p class="empty">Sem fases planejadas.</p></section>` (L341).
- A aba mostra o contador com `fases.length` (L488).
- Ícone que falha: some, e o nome da fase fica sozinho na célula.

## Regras de conteúdo

- Faça cada fase subir um atributo só. Ponha sobrevivência primeiro quando VGR estiver abaixo de 20 (`skills/build/SKILL.md` L64).
- Escreva o `nome` como "SIGLA de → para" ("VGR 9 → 20"), com a sigla do jogo.
- Grave `almas` como inteiro, tirado do save (`ds2save.py levels`), nunca de cabeça. A página põe o milhar.

## Acessibilidade

- O custo em `neg` dá 5.40:1 sobre a célula; o cabeçalho "Custo (almas)" diz o que a cor marca.
- Valores em `head` sobre a célula: 14.35:1.

## Tokens usados

Os da TabelaWiki e mais: `neg`, `cell-icon-gap`, `icon-small`. Tipo: `rodape-tabela`, `titulo-secao`, `vazio`.

## Problemas conhecidos

- Sem `<caption>` e sem `scope` nos `<th>` (L348–L351).
- O ícone de atributo depende de `icons/stat-<ATR>.png` copiado pelo `prepare_page.py`. Sem ele, a célula mostra só o nome (`aba-fases-desktop.png`).
