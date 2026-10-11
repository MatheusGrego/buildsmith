(function (raiz, fabrica) {
  // O save ao vivo (servidor local, /api/ds2/<personagem>/save): nível, almas, atributos, inventário, equipado e chefes
  // derrotados. Aqui só a leitura do que mudou, sem tocar na página: item do plano no inventário e passo feito no jogo
  // (equipar, chefe, atributo, reforço, compra). O pagina.js pinta; o mapa.js marca os itens que você já tem.
  if (typeof module === "object" && module.exports) module.exports = fabrica();
  else raiz.buildsmithVivo = fabrica();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  const STAT = {
    vgr: "VGR", vigor: "VGR", end: "END", endurance: "END", "fôlego": "END", folego: "END", "resistência": "END",
    vit: "VIT", vitality: "VIT", vitalidade: "VIT", atn: "ATN", attunement: "ATN", sintonia: "ATN",
    str: "STR", strength: "STR", "força": "STR", forca: "STR", dex: "DEX", dexterity: "DEX", destreza: "DEX",
    int: "INT", intelligence: "INT", "inteligência": "INT", inteligencia: "INT", fth: "FTH", faith: "FTH", "fé": "FTH",
    fe: "FTH", adp: "ADP", adaptability: "ADP", adaptabilidade: "ADP",
  };
  const chave = (s) => String(s ?? "").trim().toLowerCase();

  // Índice do save para consultas por nome (sem diferença de maiúscula).
  function indice(vivo) {
    const itens = new Map();
    for (const it of (vivo && vivo.itens) || []) {
      const k = chave(it.nome), atual = itens.get(k) || { qtd: 0, up: null, cat: it.cat };
      atual.qtd += Number(it.qtd) || 0;
      if (it.up != null) atual.up = Math.max(atual.up ?? 0, it.up);
      itens.set(k, atual);
    }
    return { itens, equipado: new Set(((vivo && vivo.equipado) || []).map(chave)),
             chefes: new Set(((vivo && vivo.chefes) || []).map(chave)), stats: (vivo && vivo.stats) || {} };
  }
  const statDe = (nome) => STAT[chave(nome)] || null;
  // "tem 2 → 3", "9 → 20": o número depois da seta; "×3": o número do x.
  function alvoNumero(sub) {
    const m = String(sub ?? "").match(/→\s*\+?(\d+)/) || String(sub ?? "").match(/^[×x]\s*(\d+)/i);
    return m ? Number(m[1]) : null;
  }

  // Item do plano no inventário: { qtd, up } ou null.
  function itemNoSave(nome, ix) {
    const it = ix.itens.get(chave(nome));
    return it && it.qtd > 0 ? it : null;
  }

  // Estado de um passo pelo save: { feito, texto } (feito = o jogo já mostra o passo cumprido) ou null (nada a dizer).
  function estadoPasso(passo, ix) {
    const nos = (passo && passo.fluxo) || [];
    const itens = nos.filter((n) => n && n.tipo === "item");
    if (passo.tipo === "equipar") {
      const entra = itens.filter((n) => /entra/i.test(n.sub || "")), sai = itens.filter((n) => /sai/i.test(n.sub || ""));
      if (!entra.length) return null;
      const ok = entra.every((n) => ix.equipado.has(chave(n.nome))) && sai.every((n) => !ix.equipado.has(chave(n.nome)));
      return ok ? { feito: true, texto: "equipado no jogo" } : null;
    }
    if (passo.tipo === "chefe") {
      const chefes = nos.filter((n) => n && n.tipo === "chefe");
      if (!chefes.length) return null;
      return chefes.every((n) => ix.chefes.has(chave(n.nome))) ? { feito: true, texto: "derrotado no jogo" } : null;
    }
    if (passo.tipo === "nivel") {
      const metas = nos.filter((n) => n && n.tipo === "atributo" && statDe(n.nome) && alvoNumero(n.sub) != null);
      if (!metas.length) return null;
      const falta = metas.filter((n) => (ix.stats[statDe(n.nome)] ?? 0) < alvoNumero(n.sub));
      if (!falta.length) return { feito: true, texto: "atributo no jogo" };
      const n = falta[0], k = statDe(n.nome);
      return { feito: false, texto: `${k} ${ix.stats[k] ?? "?"} de ${alvoNumero(n.sub)}` };
    }
    if (passo.tipo === "upgrade") {  // o item reforçado: o que tem "+N" no sub ("Uchigatana +6")
      const alvo = [...itens].reverse().find((n) => /^\+\d+$/.test(String(n.sub || "").trim()));
      const no = alvo && itemNoSave(alvo.nome, ix);
      if (!no || no.up == null) return null;
      const nivel = Number(String(alvo.sub).trim().slice(1));
      return no.up >= nivel ? { feito: true, texto: `+${no.up} no jogo` } : null;
    }
    // o item que o passo entrega: o último item que você ainda não tinha quando o plano foi feito
    const alvo = [...itens].reverse().find((n) => !n.tem);
    if (!alvo) return null;
    const no = itemNoSave(alvo.nome, ix);
    if (!no) return null;
    const precisa = alvoNumero(alvo.sub);
    if (precisa != null && no.qtd < precisa) return { feito: false, texto: `${alvo.nome}: ${no.qtd} de ${precisa}` };
    const texto = no.qtd > 1 ? `${alvo.nome} ×${no.qtd} no inventário` : `${alvo.nome} no inventário`;
    return { feito: passo.tipo === "compra" || passo.tipo === "troca", texto };
  }

  return { indice, itemNoSave, estadoPasso, _teste: { indice, itemNoSave, estadoPasso, alvoNumero, statDe } };
});
