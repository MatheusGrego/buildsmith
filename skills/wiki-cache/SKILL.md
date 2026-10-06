---
name: wiki-cache
description: Busca informação de jogo (onde pegar item, requisitos, builds de outros players) na wiki e guarda em cache local por 30 dias. Use antes de qualquer WebFetch sobre itens, locais, chefes ou builds de um jogo suportado pelo buildsmith.
---

# wiki-cache

Cache em `~/.buildsmith/cache/<jogo>/<slug>.md` (no Windows, `C:\Users\<usuário>\.buildsmith\...`).

## Passos

1. **Slug:** minúsculas, sem acento, espaços e símbolos viram `-`. Ex.: `Magic Stone` → `magic-stone`; builds → `builds-int-dex`.
2. **Ler o cache:** se o arquivo existe e `data` tem menos de 30 dias, use-o e não busque na web.
3. **Buscar:** para DS2 use `https://darksouls2.wiki.fextralife.com/<Nome+Com+Mais>` com WebFetch, pedindo só os fatos necessários (local exato, requisitos, preço, efeito). Se a página tiver tabela grande, abra no navegador embutido e extraia a tabela com JavaScript; não confie em resumo de tabela.
4. **Gravar** o arquivo:
   ~~~markdown
   ---
   assunto: Magic Stone
   fonte: https://darksouls2.wiki.fextralife.com/Magic+Stone
   data: 2026-10-06
   ---
   - Troca de Smooth & Silky Stone com Dyna & Tillo (Things Betwixt), entre outras recompensas.
   - Drop de Gyrm Warriors, Desert Sorceresses e Leydia Witches.
   ~~~
   Escreva só fatos com fonte, em listas curtas. Sem opinião.
5. **Wiki fora do ar:** use o cache mesmo vencido e marque na resposta "dados de DD/MM, podem estar desatualizados". Sem cache e sem wiki: diga que não achou; não chute local de item.

## Builds de outros players

Slug `builds-<arquetipo>`. Para cada build guarde: nome, nível alvo, atributos, armas, catalisador, magias, anéis e URL. Fontes: `PvE+Builds` da wiki e páginas de build individuais.
