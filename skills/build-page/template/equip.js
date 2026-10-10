(function () {
  // Tela Equipamento (como o menu de equipamento do DS2): o que está equipado no save × o melhor do plano, slot por slot.
  // Dados: plano.equipamento (ds2equip.py: números do jogo; prepare_page: ícones e letras de escala da wiki).
  const ICONE_OK = /^icons\/[A-Za-z0-9._-]+$/;
  const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const linkSeguro = (url) => { try { const u = new URL(String(url ?? "")); return u.protocol === "https:" ? u.href : ""; } catch (e) { return ""; } };
  const fmt = new Intl.NumberFormat("pt-BR");
  const ELEM = { magico: "mágico", fogo: "fogo", raio: "raio", sombrio: "sombrio" };
  const ATR = { STR: "FOR", DEX: "DES", INT: "INT", FTH: "FÉ", magico: "mágico", fogo: "fogo", raio: "raio", sombrio: "sombrio" };
  const GRUPOS = [["direita", "Mão direita"], ["esquerda", "Mão esquerda"], ["armadura", "Armadura"], ["aneis", "Anéis"]];
  const MODOS = [["comparar", "Comparar"], ["agora", "Agora"], ["plano", "Plano"]];
  const COM_NIVEL = ["arma", "escudo", "catalisador"];
  const slug = (t) => String(t).normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  const inicial = (n) => (n || "?").trim().replace(/^the\s+/i, "").charAt(0).toUpperCase();

  // ---- funções puras (testadas no node) -------------------------------------------------------------
  const letras = (escala) => (escala && Object.keys(escala).length ? Object.entries(escala).map(([k, v]) => `${ATR[k] || k} ${v}`).join(" · ") : "—");
  function arTexto(ar) {
    if (ar == null) return "—";
    if (typeof ar === "number") return fmt.format(ar);
    return Object.entries(ar).map(([k, v]) => `${ELEM[k] || k} ${fmt.format(v)}`).join(" · ") || "—";
  }
  function numero(p) {
    if (!p || p.ar == null) return null;
    return typeof p.ar === "number" ? p.ar : Math.max(...Object.values(p.ar));
  }
  function partesTexto(partes) {
    if (!partes) return "—";
    if ("base" in partes) return [`peça ${fmt.format(partes.base)}`, ...["STR", "DEX"].filter((k) => partes[k]).map((k) => `${ATR[k]} +${fmt.format(partes[k])}`)].join(" · ");
    return Object.entries(partes).map(([el, x]) => `${ELEM[el] || el}: ${fmt.format(x.base)} + ${fmt.format(x.atributos)} dos atributos`).join(" · ");
  }
  function delta(a, b) {
    const na = numero(a), nb = numero(b);
    return na != null && nb != null ? nb - na : null;
  }
  function requisitoTexto(req) {
    return req && Object.keys(req).length ? Object.entries(req).map(([k, v]) => `${ATR[k] || k} ${v}`).join(" · ") : "—";
  }

  // ---- desenho ------------------------------------------------------------------------------------------
  const ui = { modo: "comparar", slot: null };

  function tile(p, extra) {
    if (!p) return `<span class="eq-tile eq-vazio${extra ? " " + extra : ""}"></span>`;
    const img = ICONE_OK.test(p.icone || "") ? `<img src="${esc(p.icone)}" alt="" data-ini="${esc(inicial(p.nome))}">` : `<span class="eq-ini" aria-hidden="true">${esc(inicial(p.nome))}</span>`;
    const nv = COM_NIVEL.includes(p.tipo) ? `<span class="eq-nv">+${esc(p.nivel || 0)}</span>` : "";
    return `<span class="eq-tile${extra ? " " + extra : ""}${p.aviso ? " eq-aviso" : ""}">${img}${nv}</span>`;
  }

  function slotHtml(s) {
    const lado = ui.modo === "agora" ? s.agora : s.plano;
    const tiles = ui.modo === "comparar" && s.muda
      ? `${tile(s.agora, "eq-antes")}<span class="eq-seta" aria-hidden="true">&#10142;</span>${tile(s.plano, "eq-depois")}`
      : tile(lado);
    const d = delta(s.agora, s.plano);
    const ganho = ui.modo !== "agora" && s.muda && d ? `<span class="eq-d ${d > 0 ? "pos" : "neg"}">${d > 0 ? "+" : "−"}${fmt.format(Math.abs(d))}</span>` : "";
    const rotulo = `${s.nome_slot || s.slot}: ${lado ? lado.nome : "vazio"}`;
    return `<button type="button" class="eq-slot${ui.modo !== "agora" && s.muda ? " eq-muda" : ""}" data-eq-slot="${esc(s.slot)}"
      aria-pressed="${ui.slot === s.slot}" aria-label="${esc(rotulo)}"><span class="eq-tiles">${tiles}</span>
      <span class="eq-rot">${esc(s.nome_slot || s.slot)}${ganho}</span><span class="eq-nome">${esc(lado ? lado.nome : "vazio")}</span></button>`;
  }

  function sintoniaHtml(eq) {
    const s = eq.sintonia || {};
    const lado = ui.modo === "agora" ? s.agora || [] : s.plano || [];
    const antes = Object.fromEntries((s.agora || []).map((f) => [f.nome, f.ar]));
    const usados = lado.reduce((n, f) => n + (f.slots || 1), 0);
    const itens = lado.map((f) => {
      const d = ui.modo !== "agora" && f.ar != null && antes[f.nome] != null ? f.ar - antes[f.nome] : 0;
      const img = ICONE_OK.test(f.icone || "") ? `<img src="${esc(f.icone)}" alt="" data-ini="${esc(inicial(f.nome))}">` : `<span class="eq-ini" aria-hidden="true">${esc(inicial(f.nome))}</span>`;
      return `<li class="eq-feit" title="${esc(f.nome)}"><span class="eq-tile eq-tile-p">${img}</span>
        <span class="eq-fn">${esc(f.nome)}</span><span class="eq-fa">${f.ar != null ? `AR ${fmt.format(f.ar)}` : "—"}${d ? ` <span class="${d > 0 ? "pos" : "neg"}">${d > 0 ? "+" : "−"}${fmt.format(Math.abs(d))}</span>` : ""}</span>
        <span class="eq-fu">${esc(f.usos ?? "—")} usos</span></li>`;
    }).join("");
    return `<div class="eq-g eq-g-sint"><h3>Sintonia<small>${fmt.format(usados)} de ${fmt.format(s.total || usados)} slots</small></h3>
      <ul class="eq-sint">${itens || '<li class="eq-sem">Nenhum feitiço.</li>'}</ul></div>`;
  }

  function detalhe(eq, p, slot) {
    const s = (eq.slots || []).find((x) => x.slot === slot);
    if (!s) return '<p class="empty">Escolha um slot.</p>';
    const col = (x, f) => (x ? f(x) : "vazio");
    const linhas = [
      ["Peça", (x) => { const l = linkSeguro(x.link); return l ? `<a href="${esc(l)}" target="_blank" rel="noopener noreferrer">${esc(x.nome)}</a>` : esc(x.nome); }],
      ["Upgrade", (x) => (COM_NIVEL.includes(x.tipo) ? `+${esc(x.nivel || 0)}` : "—")],
      ["AR", (x) => esc(arTexto(x.ar))],
      ["Vem de", (x) => esc(partesTexto(x.partes))],
      ["Escala", (x) => (x.escala ? `${esc(letras(x.escala))}${x.escala_nivel != null && x.escala_nivel !== (x.nivel || 0) ? ` <span class="muted">(letra do +${esc(x.escala_nivel)})</span>` : ""}` : "—")],
      ["Requisito", (x) => `<span class="${x.requisito_ok === false ? "neg" : ""}">${esc(requisitoTexto(x.requisito))}</span>`],
    ];
    const ids = new Set((p.itens || []).map((it) => it.id));
    const alvo = s.plano && (s.plano.item_id || slug(s.plano.nome));
    const onde = s.plano && s.muda && ids.has(alvo)
      ? `<button type="button" class="pesq" data-goto-item="${esc(alvo)}">Onde pegar ${esc(s.plano.nome)}</button>` : "";
    const avisos = [s.agora, s.plano].filter((x) => x && x.aviso).map((x) => `<p class="eq-alerta">${esc(x.nome)}: ${esc(x.aviso)}</p>`).join("");
    const fonte = [s.agora, s.plano].map((x) => x && linkSeguro(x.escala_fonte)).find(Boolean);
    return `<h3>${esc(s.nome_slot || s.slot)}</h3>
      <div class="tw"><table><thead><tr><th></th><th>Agora</th><th>Plano</th></tr></thead><tbody>
      ${linhas.map(([rot, f]) => `<tr><th scope="row">${rot}</th><td>${col(s.agora, f)}</td><td>${col(s.plano, f)}</td></tr>`).join("")}
      </tbody></table></div>${avisos}${onde}
      <p class="muted eq-nota">AR e "vem de": regras do jogo com seus atributos${(eq.atributos && eq.atributos.aneis_plano || []).length ? ` (${esc(eq.atributos.aneis_plano.join(", "))})` : ""}. Letras: tabela de upgrade da wiki${fonte ? ` · <a href="${esc(fonte)}" target="_blank" rel="noopener noreferrer">fonte</a>` : ""}.</p>`;
  }

  function corpo(eq, p) {
    const grupos = GRUPOS.map(([g, nome]) => {
      const slots = (eq.slots || []).filter((s) => s.grupo === g);
      return `<div class="eq-g eq-g-${g}"><h3>${nome}</h3><div class="eq-linha">${slots.map(slotHtml).join("")}</div></div>`;
    }).join("");
    const resumo = (eq.resumo || []).map((r) => `<tr><td>${esc(r.dado)}</td><td>${esc(r.agora)}</td><td>${esc(r.depois)}</td><td class="${r.sinal === "+" ? "pos" : r.sinal === "-" ? "neg" : ""}">${esc(r.efeito)}</td></tr>`).join("");
    return `<div class="eq-modos" role="group" aria-label="Mostrar">${MODOS.map(([m, l]) => `<button type="button" class="eq-modo" data-eq-modo="${m}" aria-pressed="${ui.modo === m}">${l}</button>`).join("")}</div>
      <div class="eq-tela"><div class="eq-inv">${grupos}${sintoniaHtml(eq)}</div><aside class="eq-det" aria-live="polite">${detalhe(eq, p, ui.slot)}</aside></div>
      ${resumo ? `<h3 class="eq-rt">O que muda</h3><div class="tw"><table><thead><tr><th>Slot</th><th>Agora</th><th>Plano</th><th>Efeito</th></tr></thead><tbody>${resumo}</tbody></table></div>` : ""}`;
  }

  function html(p) {
    const eq = p.equipamento;
    if (!eq) return '<section><h2>Equipamento</h2><p class="empty">Este plano não tem o bloco de equipamento.</p></section>';
    if (!ui.slot || !(eq.slots || []).some((s) => s.slot === ui.slot)) ui.slot = ((eq.slots || []).find((s) => s.muda) || (eq.slots || [])[0] || {}).slot || null;
    return `<section class="eq"><h2>Equipamento<small>agora × melhor do plano</small></h2><div class="eq-app">${corpo(eq, p)}</div></section>`;
  }

  function ligar(raiz, p) {
    if (!raiz || !p.equipamento) return;
    const app = raiz.querySelector(".eq-app");
    const redesenhar = () => { app.innerHTML = corpo(p.equipamento, p); trocaImagens(app); };
    trocaImagens(app);
    app.addEventListener("click", (ev) => {
      const m = ev.target.closest("[data-eq-modo]");
      if (m) { ui.modo = m.dataset.eqModo; redesenhar(); return; }
      const s = ev.target.closest("[data-eq-slot]");
      if (s) { ui.slot = s.dataset.eqSlot; redesenhar(); const b = app.querySelector(`[data-eq-slot="${CSS.escape(ui.slot)}"]`); if (b) b.focus(); }
    });
  }

  function trocaImagens(raiz) {
    raiz.querySelectorAll(".eq-tile img").forEach((img) => {
      const troca = () => { const s = document.createElement("span"); s.className = "eq-ini"; s.textContent = img.dataset.ini || "?"; img.replaceWith(s); };
      if (img.complete && img.naturalWidth === 0) troca(); else img.addEventListener("error", troca);
    });
  }

  window.buildsmithEquip = { html, ligar, _teste: { letras, arTexto, numero, partesTexto, delta, requisitoTexto } };
})();
