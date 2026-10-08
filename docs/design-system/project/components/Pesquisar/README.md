# Pesquisar

Botão pequeno `.pesq` ao lado de um requisito em texto, que manda a pergunta para a fila da skill e mostra o estado do pedido no próprio rótulo: Pesquisar, Na fila ou Respondido.

## Quando usar

- Use na célula Requisito da tabela de fontes (Onde pegar) quando o requisito é texto, sem item ligado. Quem põe o botão é `requisito()` (`skills/build-page/template/index.html` L248–L253).
- Use a mesma classe `.pesq` para os controles da Forja: Cancelar, Tentar de novo e Fechar (ver Forja).

## Quando não usar

- Não use quando o requisito aponta para um item do plano. Aí o requisito vira link `.req-link` para o item.
- Não use para ação grande de menu. Isso é a Acao.
- Não use para enviar o formulário da Fila. Ele tem botão próprio (`.fila-form button`, ver Fila).

## O que entra

- `itens[].fontes[].requisito` em texto, ou objeto `{"texto"}` sem `item`. Vira `data-q`.
- `itens[].item.nome`. Vira `data-origem`.
- Do banco (Artifact ou servidor local), não do plano: o documento `pedidos/<slug>` com `estado` `na_fila` ou `respondido`. Sem banco, o botão nunca muda de rótulo.

Exemplo real, Soul Spear (`example/plano.json` L1387): `"requisito": "INT 40 · Undead Crypt"`, item "Soul Spear". O exemplo tem 30 fontes: 28 com Pesquisar e 2 com link para item.

## Anatomia

```html
<td>INT 40 · Undead Crypt<button class="pesq" type="button" data-q="INT 40 · Undead Crypt" data-origem="Soul Spear">Pesquisar</button></td>
```

Depois do clique sem banco, o JS põe a nota logo depois do botão (L751–L756):

```html
<span class="copiado">Copiado: /buildsmith:build ds2 onde pegar: INT 40 Undead Crypt</span>
```

| Parte | Regra |
|---|---|
| `.pesq` | `botao-pequeno` (Marcellus 12px, `letter-spacing: 0.04em`), padding `pesq-pad-y` `pesq-pad-x`, borda `border-hair` em `link`, sem fundo, texto `link`, `margin-left` `inline-offset`, `white-space: nowrap` (L153). |
| `.pesq:hover` | Fundo `panel` (L154). |
| `.pesq:disabled` | Borda `line`, texto `text`, `cursor: default` (L155). |
| `.pesq:focus-visible` | Anel `focus-width` em `link`, `outline-offset` `focus-offset` (L156). |
| `.forja-botoes .pesq` | `margin: 0` (L191). |
| `.copiado` | `contador` (12px `body`), texto `text`, `margin-left` `inline-offset`, `user-select: all` (L157). |

## Estados e variantes

| Estado | Gatilho | Rótulo | Visual |
|---|---|---|---|
| Livre | sem pedido com o mesmo slug | Pesquisar | texto e borda `link` |
| Hover | `:hover` | igual | fundo `panel` |
| Foco | `:focus-visible` | igual | anel `link` de 2px |
| Gravando | `disabled` durante a gravação (L761) | Pesquisar | borda `line`, texto `text` |
| Na fila | pedido com `estado` diferente de `respondido` (L551–L552) | Na fila | desativado |
| Respondido | pedido respondido pela skill | Respondido | desativado |
| Sem banco, depois do clique | `navigator.clipboard.writeText` deu certo (L754) | Pesquisar | nota `.copiado` "Copiado: <comando>" |
| Sem banco, área de transferência negada | o `writeText` falhou (L755) | Pesquisar | nota `.copiado` só com o comando; um clique seleciona tudo |

O clique chama `enqueue(q, origem, botão)` (L800–L801, L747–L767):

1. `limpaPedido()` (L742–L745) troca caractere de controle por espaço, apaga tudo que não for letra, número, espaço ou `' & + , . ( ) -`, junta espaços e corta em 120 caracteres. A origem é cortada em 80. Texto que fica vazio não faz nada.
2. Sem banco, copia `/buildsmith:build ds2 onde pegar: <texto limpo>` e mostra a nota.
3. Com banco, grava `pedidos/<slug>` com `{texto, origem, estado: "na_fila", criado_em}` (L763). Se o slug já existe, sai sem gravar.

O rótulo vem de `applyState()` (L548–L553), que liga botão e pedido por `slug(data-q)` (`slug()` em L245).

## Regras de conteúdo

- Use só os três rótulos: Pesquisar, Na fila, Respondido. Nos controles da Forja: Cancelar, Tentar de novo, Fechar.
- Escreva o requisito com letras, números e pontuação simples. O pedido perde o resto: "INT 40 · Undead Crypt" chega à fila e ao comando como "INT 40 Undead Crypt".
- Mantenha o requisito em uma linha, com até 80 caracteres (`validate_plano.py` L21–L22, L172).
- O servidor local aceita texto de pedido com até 160 caracteres, origem com até 80 e no máximo 50 pedidos abertos (`app/serve.py` L40–L41, L89–L90, L233–L234).

## Acessibilidade

- `<button type="button">` com texto visível. O estado está no rótulo, e Na fila e Respondido vêm com `disabled`.
- Contraste: `link` sobre célula 5.01:1, no texto e na borda. Desativado, `text` sobre célula 6.79:1; a borda `line` é isenta. A nota `.copiado` em `text` dá 6.79:1 sobre célula e 8.40:1 sobre `panel`.
- A nota não tem `aria-live`: o leitor de tela não anuncia a cópia.

## Tokens usados

Cor: `link`, `text`, `line`, `panel`. Espaço: `pesq-pad-y`, `pesq-pad-x`, `inline-offset`, `focus-offset`. Borda: `border-hair`, `focus-width`. Tipo: `botao-pequeno`, `contador`.

## Problemas conhecidos

- Cada clique sem banco acrescenta outra `.copiado` depois do botão; nenhuma some (L752–L756).
- O hover pinta o fundo `panel` também no botão desativado: a regra não tem `:not(:disabled)` (L154).
- Falha ao gravar é silenciosa. O botão volta a ficar ativo, sem mensagem (L764–L766). Pedido repetido e texto que fica vazio depois da limpeza também saem sem aviso (L749, L760).
- O botão pode não virar Na fila. Ele procura o pedido pelo slug do texto cru (L549), e o pedido é gravado pelo slug do texto limpo (L748, L759). Quando um caractere apagado fica entre letras, os slugs diferem ("chave/anel" dá `chave-anel` e `chaveanel`). Nenhum dos 28 requisitos do exemplo cai nesse caso.
- A spec `2026-10-07-buildsmith-feiticos-fila-ux-design.md` (L44) põe Pesquisar também em cada item marcado `tem`. O código só chama `pesq()` dentro de `requisito()` (L248–L253).
