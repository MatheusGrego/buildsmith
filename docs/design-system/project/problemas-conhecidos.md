# Problemas conhecidos

Defeitos visuais e de acessibilidade da página atual, cada um com a evidência. `L<linha>` é `skills/build-page/template/index.html`. As capturas citadas foram feitas com o plano de exemplo, a 1280px (desktop) e 400px (celular), sem acesso à wiki: por isso os nós mostram a inicial e as imagens da fogueira aparecem quebradas. Os valores dos tokens continuam exatos; esta lista é o que o refinamento tem para decidir.

## Layout e quebra de texto

### 1. Nome de nó quebra uma letra por linha no celular

- Onde: tabela de fontes de cada item, aba Onde pegar, a 400px.
- Evidência: captura `recorte-onde-celular.png`. "The Tower Apart", "Corpo à esquerda" e "Steady Hand McDuff" descem uma letra por linha na coluna Como.
- Causa: `.node .nm { overflow-wrap: anywhere }` (L70) deixa a largura mínima do nome em um caractere. A tabela tem `width: 100%; min-width: 30rem` (L55) e as outras colunas guardam conteúdo que não quebra (`.pesq` e `.estado` com `white-space: nowrap`, L123 e L153; `td.selos`, L130). O navegador espreme a coluna Como até a largura mínima.

### 2. "Uchigatana" quebra no meio na tabela de Dano

- Onde: aba Dano, a 1280px.
- Evidência: captura `aba-dano-desktop.png`. A 1ª coluna mostra "Uchigat" / "ana", "Soul" / "Arrow" e o `sub` "+5 · FOR" / "10".
- Causa: a mesma do item 1. A coluna Por causa de leva fluxos longos e a coluna Arma encolhe até o mínimo que `overflow-wrap: anywhere` permite.

### 3. Barra de abas cortada sem aviso

- Evidência: em `aba-dano-desktop.png` a 11ª aba aparece cortada ("Fi") na borda direita a 1280px; em `aba-fontes-celular.png` a primeira aba visível começa cortada ("pegar").
- Causa: as 11 abas passam da largura do painel; `.tabs` rola na horizontal com `scrollbar-width: thin` (L106) e não há degradê nem seta que mostre que existe mais.

### 4. Seta do fluxo pendurada no fim da linha

- Evidência: `topo-celular.png`, painel Agora: "Old Leo Ring ➞" fica numa linha e "Ring of Binding" desce para a seguinte; o mesmo em "Sublime Bone Dust ➞" e "Far Fire ➞".
- Causa: a seta é um item próprio do `.flow` com `flex-wrap: wrap` (L64, L278); ela fica com o nó da esquerda quando a linha quebra.

### 5. Data das fontes em ISO, quebrando no hífen

- Evidência: `aba-fontes-celular.png`, último item: "· 2026-" numa linha e "10-07" na seguinte.
- Causa: a data sai crua do JSON (L474), sem `Intl`, enquanto o cabeçalho formata `gerado_em` em pt-BR (L260).

### 6. Margem padrão do navegador em volta da página

- Causa: `body` não zera `margin` (L30). Fica a margem padrão de 8px em volta do `.page`, somada ao `gutter`.

## Imagem e ícone

### 7. Imagem da fogueira sem fallback nos botões e nas fogueiras

- Evidência: `topo-desktop.png` e `aba-feiticos-desktop.png`. As duas `.acao` (Atualizar plano, Responder fila) e todas as `.fogueira` mostram o ícone de imagem quebrada. Na aba Feitiços, a coluna de fogueiras vira uma fila de imagens quebradas; acesa e apagada só se distinguem pela borda `pos`.
- Causa: `icons/fogueira.png` entra com `alt=""` e sem `onerror` (L246, L293, L294). O `fallbackIcons()` só trata `img.ic` (L266–L271). Se o arquivo não existir, o botão fica sem nenhum conteúdo legível além do `aria-label`.

## Cor e contraste

### 8. `dim` abaixo de 4.5:1

- `dim` #7a7875 sobre `th` dá 4.29:1 em texto de 11 a 13px: selo Tarde (`.estado.apagado`, L126), rótulo de etapa (`.etapa .rotulo`, L195), tempo do log (`.linha .t`, L206), pensamento do log (`.linha-pensamento .x`, L210). Sobre `panel` daria 4.03:1 e sobre célula 3.26:1.
- `.acao:disabled` (L177) usa `dim` também, mas controle desativado é isento.

### 9. Campo da fila sem limite visível

- Borda `line` 1.41:1 e fundo `td` (#2a2a2a) 1.24:1 contra `panel` (L159). Falha 3:1 para componente de interface.

### 10. Zero pintado como perda

- Evidência: `aba-dano-desktop.png`, painel Agora: "Almas pra essas ações: 0" com o 0 em azul.
- Causa: o número sempre entra em `.neg` (L437), mesmo quando é 0.

### 11. Ganho e perda perdem o peso fora da Helvetica Neue

- `.pos` e `.neg` pedem `font-weight: 500` (L40–L41). A Arial não tem 500 e o navegador cai para 400. Sem a Helvetica Neue, ganho e perda se distinguem só pela cor e pelo sinal.

## Foco e teclado

### 12. Foco do microtexto fora do padrão

- `.microtexto:focus-visible { outline: 1px solid var(--line) }` (L204): 1.49:1 sobre `th`. O resto da página usa 2px em `link`.

### 13. Botão da fila e "Ver todas as fontes" sem foco próprio

- `.fila-form button` (L161) e `details.mais summary` (L162) não têm `:focus-visible`; usam o anel padrão do navegador. O botão da fila também não tem `:hover` nem `:disabled`.

### 14. Abas sem Home e End

- O teclado só trata seta direita e esquerda (L507–L514). Todas as abas ficam na ordem do Tab; não há `tabindex="-1"` nas não selecionadas.

## Leitor de tela

### 15. Tabelas sem `caption` e sem `scope`

- `rows()` (L283), `grid()` (L392–L394), a Ficha (L303) e as Fases (L348–L351) geram `<th>` sem `scope` e nenhuma tabela tem `<caption>`. A tabela de Feitiços abre com um `<th>` vazio na coluna das fogueiras (L458).

### 16. Relógio da Forja dentro de região `aria-live`

- `.forja-head` é `aria-live="polite"` (L606) e contém `.forja-tempo`, que muda a cada 1000ms (L667). O leitor de tela pode anunciar o tempo sem parar.

### 17. Avisos sem anúncio

- `.error` não tem `role="alert"` (L871). A nota `.copiado` não tem `aria-live` (L752–L756).

## Movimento

### 18. Rolagem suave ignora `prefers-reduced-motion`

- `scrollIntoView({ behavior: "smooth" })` (L526) roda mesmo com movimento reduzido. As animações do CSS desligam; essa rolagem não.

## Comportamento visual

### 19. "Ver todas as fontes (N)" conta o que não mostra

- N é o total de fontes, mas o `details` mostra só as que ficaram fora da tabela principal (L372).

### 20. Lista da fila não volta ao vazio

- Se os pedidos voltarem a zero, a condição `if (box && list.length)` (L556) não repõe "Nenhum pedido ainda." e a tabela antiga fica.

### 21. Nota "Copiado" se acumula

- Cada clique em Pesquisar sem banco acrescenta outra `.copiado` depois do botão (L752–L756); nenhuma some.

## Conteúdo

### 22. Texto sem acento e siglas misturadas

- O AR do catalisador sai com a chave crua do JSON: "AR do catalisador: magico 190 · sombrio 166" (L444; captura `aba-feiticos-desktop.png`).
- O plano de exemplo mistura siglas: "+5 · FOR 10" e "DES 18 → 25" (`skills/build-page/example/plano.json` L2062 e L2067, visíveis em `aba-dano-desktop.png`) e "FOR 18 · DES 18 · INT 18", "faltam 8 FOR" (L1327–L1328), enquanto a aba Atributos usa STR e DEX.
- O sinal de menos varia: o texto do plano usa "−" (U+2212); a Diferença negativa do Dano sai com "-" do `Intl` (L420).

### 23. Página inicial do servidor com outra tipografia

- `app/serve.py` L281–L282 desenha a lista de personagens com `font:15px Helvetica,Arial,sans-serif` e `h1` em `Georgia,serif`. A página do plano usa 14px no corpo e Marcellus SC nos títulos.

## Código e documentação fora de sincronia

- `.badge` (L83) está no CSS e nenhum trecho do JS gera essa classe.
- A spec `docs/superpowers/specs/2026-10-06-buildsmith-pagina-v2-design.md` chama o contorno de `--table-edge` (L22); o código usa `--edge` (L16). A mesma spec desenha a seta como `➜` (L9, L41); o código usa `➞` (L278).
- A spec `2026-10-06-buildsmith-progresso-dano-design.md` pede Vivo e Pendente "em texto apagado" (L71); o código usa o selo neutro em `text`.
- A spec `2026-10-07-buildsmith-feiticos-fila-ux-design.md` põe Pesquisar também "em cada item marcado `tem`" (L44); o código só chama `pesq()` dentro de `requisito()` (L248–L253).
- A spec `2026-10-07-buildsmith-forja-design.md` escreve a faixa como "PLANO FORJADO" (L32); o código passa "Plano forjado" (L572) e a caixa alta vem do desenho da Marcellus SC.
- `docs/design-system.md` lista as etapas `.feita`, `.atual` e `.pulada`; o servidor também manda `pendente`, que não tem regra e cai na base.
