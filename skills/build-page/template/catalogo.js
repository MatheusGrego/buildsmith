(function (raiz, fabrica) {
  // Catálogo (servidor local, /api/ds2/catalogo): todos os itens do jogo com categoria, requisito e quantas fontes de
  // cada tipo. O jogador marca (★, coleção "quero") e "Onde pegar" e "Passos" dos marcados saem por código
  // (/api/ds2/<personagem>/fontes, ds2fontes), sem IA, junto com os itens e passos do plano, se houver plano.
  // Aqui só a parte sem tela (filtro, junção com o plano, textos); o pagina.js pinta.
  if (typeof module === "object" && module.exports) module.exports = fabrica();
  else raiz.buildsmithCatalogo = fabrica();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  // Categorias do índice (ds2itens) na ordem dos filtros; "outros" junta consumível, material, chave e munição.
  const CATEGORIAS = [["arma", "Armas"], ["escudo", "Escudos"], ["catalisador", "Catalisadores"], ["feitico", "Feitiços"],
                      ["milagre", "Milagres"], ["hex", "Hexes"], ["piromancia", "Piromancias"], ["armadura", "Armaduras"],
                      ["anel", "Anéis"], ["outros", "Outros"]];
  const NOME_CAT = { arma: "arma", escudo: "escudo", catalisador: "catalisador", feitico: "feitiço", milagre: "milagre",
                     hex: "hex", piromancia: "piromancia", armadura: "armadura", anel: "anel", consumivel: "consumível",
                     material: "material", chave: "chave", municao: "munição", outro: "outro" };
  const PRINCIPAIS = new Set(CATEGORIAS.map((c) => c[0]).filter((c) => c !== "outros"));
  const FONTE = { compra: ["loja", "lojas"], troca: ["troca", "trocas"], chao: ["no chão", "no chão"], drop: ["drop", "drops"],
                  recompensa: ["chefe", "chefes"] };
  const LIMITE = 200;  // linhas pintadas de uma vez (o resto pede para refinar a busca)

  const grupo = (cat) => (PRINCIPAIS.has(cat) ? cat : "outros");
  const sem = (t) => String(t ?? "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().trim();

  // IDs (texto) dos itens marcados na coleção "quero".
  function marcados(quero) {
    return Object.entries(quero || {}).filter(([id, d]) => /^\d{1,10}$/.test(id) && d && d.marcado === true).map(([id]) => id);
  }

  function filtrar(itens, { cat = "", busca = "", quero = null, soMarcados = false } = {}) {
    const termo = sem(busca);
    const marc = new Set(marcados(quero));
    return (itens || []).filter((it) => (!cat || grupo(it.cat) === cat) && (!termo || sem(it.nome).includes(termo))
                                         && (!soMarcados || marc.has(String(it.id))));
  }

  // "2 lojas · 1 troca · 3 no chão": quantas fontes de cada tipo o jogo dá ("sem fonte no jogo" quando nenhuma).
  function resumoFontes(fontes) {
    const partes = Object.keys(FONTE).filter((t) => (fontes || {})[t] > 0)
      .map((t) => `${fontes[t]} ${FONTE[t][fontes[t] > 1 ? 1 : 0]}`);
    return partes.length ? partes.join(" · ") : "sem fonte no jogo";
  }

  const reqTexto = (req) => Object.entries(req || {}).map(([k, v]) => `${k} ${v}`).join(" · ");

  // Plano + marcados: os itens e passos do plano vêm primeiro; o marcado que o plano já tem (mesmo nome) não repete,
  // nem os passos dele (o plano já tem os seus para esse item).
  function juntar(plano, extras) {
    const itens = [...(plano.itens || [])], passos = [...(plano.passos || [])];
    const nomes = new Set(itens.map((it) => sem(it.item && it.item.nome)));
    const ids = new Set(passos.map((s) => s.id));
    for (const e of extras || []) {
      if (!e || !e.item || !e.item.item || nomes.has(sem(e.item.item.nome))) continue;
      itens.push({ ...e.item, marcado: true });
      nomes.add(sem(e.item.item.nome));
      for (const s of e.passos || []) {
        if (s && s.id && !ids.has(s.id)) { passos.push({ ...s, marcado: true }); ids.add(s.id); }
      }
    }
    return { ...plano, itens, passos };
  }

  // Ordem dos filtros (arma, escudo, catalisador...), depois o nome.
  const ORDEM = Object.fromEntries(CATEGORIAS.map(([id], i) => [id, i]));
  const ordenar = (itens) => [...(itens || [])].sort((a, b) => (ORDEM[grupo(a.cat)] - ORDEM[grupo(b.cat)]) || String(a.nome).localeCompare(String(b.nome)));

  // Entrada de "Onde pegar" do item: a do plano quando ele já tem o item (mesmo nome), senão a do marcado.
  function idNoPlano(plano, item) {
    const achada = ((plano && plano.itens) || []).find((it) => it.item && sem(it.item.nome) === sem(item.nome));
    return achada ? achada.id : `quero-${item.id}`;
  }

  // ID do item do jogo de uma entrada marcada ("quero-61140000" -> "61140000").
  const idDoItem = (entrada) => { const m = /^quero-(\d{1,10})$/.exec(String(entrada && entrada.id)); return m ? m[1] : null; };

  return { CATEGORIAS, NOME_CAT, LIMITE, grupo, marcados, filtrar, resumoFontes, reqTexto, juntar, idDoItem, idNoPlano, ordenar };
});
