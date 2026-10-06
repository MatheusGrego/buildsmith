---
name: wiki-cache
description: Busca informação de jogo (onde pegar item, requisitos, efeitos numéricos, ícone, builds de outros players) na wiki e guarda em cache local por 30 dias. Use antes de qualquer WebFetch sobre itens, locais, chefes, NPCs ou builds de um jogo suportado pelo buildsmith.
---

# wiki-cache

Cache em `~/.buildsmith/cache/<jogo>/<slug>.md` (no Windows, `C:\Users\<usuário>\.buildsmith\...`).

## Passos

1. **Slug:** minúsculas, sem acento, espaços e símbolos viram `-`. Ex.: `Magic Stone` → `magic-stone`; builds → `builds-int-dex`.
2. **Ler o cache:** se o arquivo existe e `data` tem menos de 30 dias, use-o e não busque na web.
3. **Buscar:** página `https://darksouls2.wiki.fextralife.com/<Nome+Com+Mais>`. O jeito mais confiável é o navegador embutido: abra qualquer página da wiki e rode JavaScript com `fetch('/<Pagina>')` + `DOMParser`, lendo:
   - ícone: `src` de `.infobox img` (URL em `static0.fextralifeimages.com`);
   - efeitos, requisitos, preço: itens de lista e células de tabela do conteúdo.
   WebFetch serve para texto curto; nunca confie em resumo de tabela.
4. **Gravar** só fatos, de preferência números:
   ~~~markdown
   ---
   assunto: Ring of Binding
   fonte: https://darksouls2.wiki.fextralife.com/Ring+of+Binding
   icone: https://static0.fextralifeimages.com/file/darksouls2/4/46/Ring_of_binding.png
   data: 2026-10-06
   ---
   - PV máx. em Hollow: piso 50% → 75%
   - Peso: 0,2 · Durabilidade: 130
   - Onde: (fluxo) Lost Bastille ➜ ...
   ~~~
5. **Wiki fora do ar:** use o cache mesmo vencido e marque "dados de DD/MM". Sem cache e sem wiki: escreva `"—"` no dado; nunca chute.

## Builds de outros players

Slug `builds-<arquetipo>`. Para cada build: nome, nível alvo, atributos (números), armas, catalisador, magias, anéis e URL.
