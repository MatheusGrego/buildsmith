# Feiticos

Aba Feitiços com o catalisador e o AR dele por elemento, o contador de slots e a tabela de feitiços com estado, AR calculado, usos, slots, requisito e a fogueira que escolhe o que sintonizar.

## Quando usar

- Use uma vez por página, no painel da aba `feiticos`, quando o plano tem `feiticos` (`skills/build-page/template/index.html` L486).
- Liste os feitiços que o jogador tem e os sugeridos, com o AR calculado pelas regras do jogo.

## Quando não usar

- Não use para o dano de arma. Isso é a TabelaDano.
- Não use a fogueira daqui para marcar passo feito. Aqui ela seleciona o feitiço para sintonizar.
- Não ponha feitiço sugerido sem entrada em Onde pegar: ele entra na regra de fechamento (`validate_plano.py` L255–L257).

## O que entra

`feiticos` (`example/plano.json` L2189–L2393, `icone` e `link` omitidos):

```json
{"catalisador": {"tipo": "item", "nome": "Sorcerer's Staff", "sub": "+2 · menu 356", "tem": true},
 "ar": {"magico": 190, "sombrio": 166},
 "slots": {"total": 6, "faixa": 3},
 "lista": [
  {"id": "soul-arrow", "no": {"tipo": "item", "nome": "Soul Arrow", "tem": true}, "estado": "equipado",
   "elemento": "mágico", "ar": 161, "usos": 32, "slots": 1, "requisito": "INT 10", "requisito_ok": true},
  {"id": "soul-spear", "no": {"tipo": "item", "nome": "Soul Spear"}, "estado": "sugerido",
   "elemento": "mágico", "ar": 341, "usos": 2, "slots": 1, "requisito": "INT 40 · falta 14", "requisito_ok": false}]}
```

O exemplo tem 11 feitiços: 5 equipados, 4 sugeridos e 2 "tem". `slots.faixa` não aparece na página.

Do banco (Artifact ou servidor local), não do plano: `config/feiticos` com `selecionados` (ids). Sem esse documento, a seleção começa nos equipados (`selectedSpells()`, L529–L532).

## Anatomia

`spells()` (L441–L460) e o contador de `applyState()` (L543–L547):

```html
<section><h2>Feitiços<small>AR calculado pelas regras do jogo</small></h2>
  <div class="block-head"><a class="node" href="…"><span class="ini" aria-hidden="true">S</span><span class="nm">Sorcerer's Staff</span><span class="sub">+2 · menu 356</span></a><span class="muted">AR do catalisador: magico 190 · sombrio 166</span></div>
  <p class="slots">Slots selecionados: <span id="slots-usados"><span class="pos">5</span></span> de 6</p>
  <div class="tw"><table><thead><tr><th></th><th>Feitiço</th><th>Estado</th><th>Elemento</th><th class="r">AR</th><th class="r">Usos</th><th class="r">Slots</th><th>Requisito</th></tr></thead><tbody>
    <tr><td><button class="fogueira" type="button" data-feitico="soul-spear" aria-pressed="false" aria-label="Selecionar para sintonizar" title="Selecionar para sintonizar"><img src="icons/fogueira.png" alt=""></button></td><td><a class="node solo" href="…"><span class="ini" aria-hidden="true">S</span><span class="nm">Soul Spear</span></a></td><td class="selos"><span class="estado destaque">Sugerido</span></td><td>mágico</td><td class="r">341</td><td class="r">2</td><td class="r">1</td><td><span class="neg">INT 40 · falta 14</span></td></tr>
  </tbody></table></div>
</section>
```

| Parte | Regra |
|---|---|
| `.block-head` | Nó do catalisador (nó cheio, ver No) e o AR por elemento em `.muted` (`pequeno`, `text`). |
| `.slots` | `contador-slots` (Marcellus 15px) em `head` (L166). O número usado vem em `.pos` ou `.neg` com a família `body` (`valor-slots`, L167). |
| Tabela | Tabela wiki de 8 colunas (ver TabelaWiki). AR, Usos e Slots à direita (`.r`). A 1ª coluna tem `th` vazio. |
| Fogueira | Botão `.fogueira` de `fogueira-size` com ícone em `icon-fogueira` (L133–L142; ver Fogueira). |
| Estado | Selo em `td.selos`: `.estado.feito` Equipado, `.estado.destaque` Sugerido, `.estado` Tem (L448; ver Selo). |
| Requisito | `<span class="neg">` quando `requisito_ok` é falso; senão `<span class="">` em `head`. |

O ícone `icons/fogueira.png` não está neste sistema. O preview mostra o botão sem a imagem.

## Estados e variantes

| Caso | Resultado |
|---|---|
| Selecionado | fogueira com `aria-pressed="true"`: borda `pos`, ícone aceso |
| Não selecionado | `aria-pressed="false"`: borda `line`, ícone cinza |
| Gravando a seleção | fogueira `disabled`, `cursor: progress` (L785–L787) |
| Sem banco | fogueiras com `hidden`; a coluna sem título continua, vazia |
| Slots dentro do total | número em `.pos` ("5 de 6") |
| Slots acima do total | número em `.neg` ("7 de 6") |
| Antes do `applyState()` | o número é "—" (L457); a troca acontece logo depois do render, com ou sem banco |
| `ar` "—" | célula "—" (buff e teleguiado: Magic Weapon, Heavy Homing Soul Arrow) |
| `elemento` ausente | "—" (L449) |
| Sem `feiticos` | `<p class="empty">Este plano não tem feitiços.</p>` (L443) |

O clique alterna o id em `config/feiticos.selecionados` e grava (L780–L789).

## Regras de conteúdo

- Use `estado` entre `equipado`, `tem` e `sugerido` (`validate_plano.py` L14, L208). Rótulos fixos: Equipado, Tem, Sugerido (template L243).
- Escreva `ar` como inteiro ou "—". Use "—" para feitiço sem dano direto (`validate_plano.py` L210; `skills/build/SKILL.md` L66).
- Escreva `usos`, `slots` e `slots.total` como inteiros (`validate_plano.py` L203, L212–L214).
- Marque `requisito_ok: false` quando faltar INT ou FÉ, e diga quanto falta no texto: "INT 40 · falta 14" (`skills/build/SKILL.md` L66).
- Use o `sub` do nó para o que muda a leitura do AR: "por lança", "Pyromancy Flame · 204", "teleguiado"; no catalisador, "+2 · menu 356".
- A chave de `ar` aparece como está no JSON: `{"magico": 190}` vira "magico 190" (L444).

## Acessibilidade

- A fogueira é um botão de alternância: `aria-pressed`, `aria-label` e `title` "Selecionar para sintonizar". Foco em anel `focus-width` `link` com `focus-offset`.
- Requisito que falta vem em `neg` e também diz "falta N". A cor não vai sozinha.
- Contraste sobre célula: `head` 14.35:1; `neg` 5.40:1; borda `pos` da fogueira acesa 7.80:1. Contador sobre `panel`: `pos` 9.65:1, `neg` 6.69:1.
- O contador não tem `aria-live`.

## Tokens usados

Cor: `head`, `text`, `pos`, `neg`, `link`, `line`, `th`, `td`, `edge`, `fogueira-glow`. Espaço: `cell-pad-y`, `cell-pad-x`, `seal-pad-y`, `seal-pad-x`, `focus-offset`. Borda: `border-hair`, `border-table`, `focus-width`. Layout: `fogueira-size`, `icon-fogueira`, `icon-node-table`, `table-min-width`. Tipo: `titulo-secao`, `subtitulo-secao`, `contador-slots`, `valor-slots`, `pequeno`, `cabecalho-tabela`, `corpo`, `nome-no`, `legenda-no`, `selo`.

## Problemas conhecidos

- O AR do catalisador sai sem acento: "AR do catalisador: magico 190 · sombrio 166" (L444; `aba-feiticos-desktop.png`).
- A imagem da fogueira não tem fallback. Sem o arquivo, a coluna vira uma fila de imagens quebradas; acesa e apagada só se distinguem pela borda `pos` (L246; `aba-feiticos-desktop.png`; ver Problemas conhecidos, item 7).
- O `th` da coluna das fogueiras é vazio (L458): a coluna não tem nome para o leitor de tela.
- Sem banco, a coluna das fogueiras fica na tabela com as células vazias.
