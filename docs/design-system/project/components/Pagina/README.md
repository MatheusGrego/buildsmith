# Pagina

`.page` e `.panel` formam a casca da Forja de Build: uma coluna central com margem lateral e um painel único no estilo da wiki, onde entra todo o resto.

## Quando usar

- Use uma `.page` por documento, como `<main class="page">`, com um só `.panel` dentro (`id="app"` na página real).
- Ponha no painel, nesta ordem: Cabecalho (`header.top`), Agora (`section.agora`, só se o plano tiver `agora`), Abas (`nav.tabs`) e um `.tab-panel` por aba.

## Quando não usar

- Não ponha um `.panel` dentro de outro. As caixas internas são `.agora` e `.forja`: fundo `th`, borda `line` e canto reto.
- Não abra um segundo painel para separar seções. Separe com `h2` (TituloSecao) e com o `gap` do painel.

## O que entra

- Nada do `plano.json` vai direto na casca. O JS busca o `plano.json` com `cache: "no-store"` (`skills/build-page/template/index.html` L868) e troca o conteúdo do `#app` (L499–L501).
- Enquanto carrega, o painel mostra `<p class="empty">Carregando o plano…</p>` (L233).
- Se a leitura falhar, o painel inteiro vira `.error` (L871).

## Anatomia

HTML estático (L233):

```html
<main class="page"><div class="panel" id="app"><p class="empty">Carregando o plano…</p></div></main>
```

Depois de `render(p)`:

```
main.page
└─ div.panel#app
   ├─ header.top                      Cabecalho
   ├─ section.agora                   Agora (opcional)
   ├─ nav.tabs[role=tablist]          Abas
   └─ div.tab-panel[role=tabpanel]    um por aba; só o ativo sem hidden
      └─ section > h2 + conteúdo
```

- `body` (L30): fundo `bg`, texto `text`, estilo `corpo` (14px/1.6 `body`).
- `.page` (L31): `max-width` `page-max-width`, `margin: 0 auto`, `padding-inline` `gutter`, `padding-block` `page-pad-top` `page-pad-bottom`.
- `.panel` (L32): fundo `panel`, borda `border-hair` em `line`, raio `radius-panel`, padding `panel-pad-top` `panel-pad-x` `panel-pad-bottom`, `display: grid`, `gap` `panel-gap`.
- `section` (L39) e `.tab-panel` (L112) são grids: `section-gap` entre título e conteúdo, `tab-panel-gap` entre seções da mesma aba. O painel de aba oculto tem `display: none` (L113) e não conta no `gap`.
- O preview usa `<div class="page">` e mostra a página montada na aba Fases, sem o Agora. Os ícones de atributo das Fases não estão no sistema; a página real também os remove quando falham (`onerror="this.remove()"`, L345).

## Estados e variantes

| Estado | Conteúdo do `#app` | Origem |
|---|---|---|
| Carregando | `<p class="empty">Carregando o plano…</p>` | L233 |
| Montada | cabeçalho, Agora, abas e painéis | `render(p)`, L480–L515 |
| Erro | `<p class="error">Não consegui ler o plano.json publicado junto com a página. Rode o /buildsmith:build de novo para republicar.</p>` | L871 |

O erro aparece quando o `plano.json` não chega, volta com status de erro ou não é JSON válido, e também quando o próprio `render` falha (L868–L871).

## Regras de conteúdo

- Mantenha uma coluna só. Tabela larga rola dentro do `.tw`; a página não rola na horizontal.
- O texto de carregando termina com reticências ("…"). O texto de erro diz o que fazer: "Rode o /buildsmith:build de novo para republicar."
- Só o painel tem raio. Tudo dentro dele tem canto reto.

## Acessibilidade

- `.page` é o `<main>`, landmark principal. Dentro dele vêm um `<header>` e uma `<section>` por bloco de conteúdo.
- A casca precisa de `<!doctype html>`, `<html lang="pt-BR">`, `<meta charset="utf-8">` e `<meta name="viewport" content="width=device-width,initial-scale=1">`. O template não traz nenhum deles; o servidor local põe na frente da página (`app/serve.py` L48).
- Contraste sobre `panel`: `text` 8.40:1, `head` 17.76:1, `neg` 6.69:1 (erro). O painel sobre `bg` dá 1.07:1: a borda `line` e o raio desenham o cartão.

## Tokens usados

- Cor: `bg`, `panel`, `line`, `text`, `head`, `neg`.
- Espaço: `gutter`, `page-pad-top`, `page-pad-bottom`, `panel-pad-top`, `panel-pad-x`, `panel-pad-bottom`, `panel-gap`, `tab-panel-gap`, `section-gap`.
- Tamanho e borda: `page-max-width`, `radius-panel`, `border-hair`.
- Tipo: `corpo`, `vazio`.

## Problemas conhecidos

- `body` não zera `margin` (L30): fica a margem padrão de 8px do navegador somada ao `gutter` (ver Problemas conhecidos, item 6).
- Sem a casca do servidor (arquivo aberto direto do disco), a página fica sem viewport e o breakpoint de 560px não dispara no celular.
- `.error` não tem `role="alert"` (L871): o leitor de tela não anuncia a falha (item 17).
