# Legenda

A `.legend` escreve no cabeçalho o que cada cor quer dizer, com um quadrado e uma palavra: `pos` é ganho, `neg` é perda ou falta, `link` é link da wiki.

## Quando usar

- Use uma vez, no Cabecalho, logo abaixo do `h1`.
- Mantenha as três entradas, nesta ordem: ganho, perda / falta, link da wiki.

## Quando não usar

- Não crie legenda local para uma tabela ou seção. As cores valem para a página inteira.
- Não acrescente cor que a página não usa com esse sentido.

## O que entra

Texto fixo (`skills/build-page/template/index.html` L291). Nada do `plano.json`.

## Anatomia

```html
<div class="legend"><span class="l-pos">ganho</span><span class="l-neg">perda / falta</span><span class="l-link">link da wiki</span></div>
```

- `.legend` (L47): flex com `flex-wrap: wrap`, `gap` `legend-gap-y` `legend-gap-x`, 13px (`pequeno`).
- `.legend span::before` (L48): `content: "■ "`, na cor do texto ao lado.
- `.l-pos`, `.l-neg`, `.l-link` (L49–L51): cor `pos`, `neg` e `link`.
- O preview põe embaixo o passo Trocar anel, que usa as três cores: nós com link em `link`, "+25 p.p." em `.pos`, "−12,5%" em `.neg`.

## Estados e variantes

Nenhum. A legenda é fixa e não é interativa.

## Regras de conteúdo

- Escreva em minúsculas, sem ponto: "ganho", "perda / falta", "link da wiki".
- Cumpra o que a legenda promete: `pos` só em ganho e destaque ("+25 p.p.", "+13"), `neg` só em perda, falta e erro ("−12,5%", "faltam 2.500"), `link` só em link e feito.
- Ponha sinal ou palavra junto da cor: "+", "−", "faltam", "economia".

## Acessibilidade

- O sentido está na palavra. O quadrado é reforço.
- Contraste sobre `panel`: `pos` 9.65:1, `neg` 6.69:1, `link` 6.19:1.
- `pos` e `neg` são âmbar e azul, fora do eixo vermelho e verde, mas a diferença de luminância entre eles é só 1.44:1. Mantenha o sinal e a palavra.

## Tokens usados

- Cor: `pos`, `neg`, `link`.
- Espaço: `legend-gap-y`, `legend-gap-x`.
- Tipo: `pequeno`.

## Problemas conhecidos

- A legenda não diz que `link` também marca feito: selo `.feito`, aba ativa e etapa feita da Forja usam a mesma cor.
