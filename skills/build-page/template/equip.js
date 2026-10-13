(function () {
  // Tela Equipamento (como o menu de equipamento do DS2): o que está equipado no save × o melhor do plano, slot por slot.
  // Dados: plano.equipamento (ds2equip.py: números do jogo; prepare_page: ícones e letras de escala da wiki).
  const ICONE_OK = /^icons\/[A-Za-z0-9._-]+$/;
  const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const linkSeguro = (url) => { try { const u = new URL(String(url ?? "")); return u.protocol === "https:" ? u.href : ""; } catch (e) { return ""; } };
  const fmt = new Intl.NumberFormat("pt-BR");
  const ELEM = { fisico: "físico", magico: "mágico", fogo: "fogo", raio: "raio", sombrio: "sombrio" };
  const ATR = { STR: "FOR", DEX: "DES", INT: "INT", FTH: "FÉ", magico: "mágico", fogo: "fogo", raio: "raio", sombrio: "sombrio" };
  const GRUPOS = [["direita", "Mão direita"], ["esquerda", "Mão esquerda"], ["armadura", "Armadura"], ["aneis", "Anéis"]];
  const MODOS = [["comparar", "Comparar"], ["agora", "Agora"], ["plano", "Plano"]];
  // De onde vem a coluna da direita (ds2combate): as trocas do plano da IA ou o melhor por código.
  const DESTINO = { plano: "plano", "melhor que dá para pegar agora": "melhor que dá para pegar", "o que você tem": "melhor do que você tem" };
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
    const fis = (x) => [`peça ${fmt.format(x.base)}`, ...["STR", "DEX"].filter((k) => x[k]).map((k) => `${ATR[k]} +${fmt.format(x[k])}`)].join(" · ");
    if ("base" in partes) return fis(partes);
    return Object.entries(partes).map(([el, x]) => (el === "fisico" ? `físico: ${fis(x)}` : `${ELEM[el] || el}: ${fmt.format(x.base)} + ${fmt.format(x.atributos)} dos atributos`)).join(" · ");
  }
  function delta(a, b) {
    const na = numero(a), nb = numero(b);
    return na != null && nb != null ? nb - na : null;
  }
  function requisitoTexto(req) {
    return req && Object.keys(req).length ? Object.entries(req).map(([k, v]) => `${ATR[k] || k} ${v}`).join(" · ") : "—";
  }
  // Simulador (servidor local, /simular e coleção metas): reforço e infusão de uma arma, calculados por código.
  const metaTexto = (m) => `+${m.nivel}${m.infusao ? ` ${m.infusao_nome || `infusão ${m.infusao}`}` : ""}`;
  function faltaTexto(f) {
    const partes = (f.materiais || []).map((m) => `${fmt.format(m.qtd)} ${m.item} (tem ${fmt.format(m.tem)})`);
    if (f.almas) partes.push(`${fmt.format(f.almas)} almas (tem ${fmt.format(f.almas_tem || 0)})`);
    return partes.length ? partes.join(" · ") : "nada: já está assim";
  }
  const infusaoOpcoes = (lista) => (lista || []).map((i) => ({ k: i.k, rotulo: i.pedra ? `${i.nome} · ${i.pedra}` : i.nome }));
  function total(p) {
    if (!p || p.ar == null) return null;
    return typeof p.ar === "number" ? p.ar : Object.values(p.ar).reduce((a, b) => a + b, 0);
  }

  // ---- desenho ------------------------------------------------------------------------------------------
  // sim: o que está nos seletores do Simular (slot, item, nivel, infusao); res: a última resposta do /simular.
  const ui = { modo: "comparar", slot: null, sim: null, res: null, erro: null, carregando: false, pedido: 0 };
  let ctx = null; // servidor local: { base, headers, atualizar }; sem ele (página publicada) não há Simular nem metas

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
    const meta = s.meta ? `<span class="eq-meta-t">meta ${esc(metaTexto(s.meta))}</span>` : "";
    const rotulo = `${s.nome_slot || s.slot}: ${lado ? lado.nome : "vazio"}${s.meta ? `, meta ${metaTexto(s.meta)}` : ""}`;
    return `<button type="button" class="eq-slot${ui.modo !== "agora" && s.muda ? " eq-muda" : ""}" data-eq-slot="${esc(s.slot)}"
      aria-pressed="${ui.slot === s.slot}" aria-label="${esc(rotulo)}"><span class="eq-tiles">${tiles}</span>
      <span class="eq-rot">${esc(s.nome_slot || s.slot)}${ganho}</span><span class="eq-nome">${esc(lado ? lado.nome : "vazio")}</span>${meta}</button>`;
  }

  function sintoniaHtml(eq) {
    const s = eq.sintonia || {};
    const lado = ui.modo === "agora" ? s.agora || [] : s.plano || [];
    const antes = Object.fromEntries((s.agora || []).map((f) => [f.nome, f.ar]));
    const usados = lado.reduce((n, f) => n + (f.slots || 1), 0);
    const total = ui.modo === "agora" && s.total_agora ? s.total_agora : s.total;
    const itens = lado.map((f) => {
      const d = ui.modo !== "agora" && f.ar != null && antes[f.nome] != null ? f.ar - antes[f.nome] : 0;
      const img = ICONE_OK.test(f.icone || "") ? `<img src="${esc(f.icone)}" alt="" data-ini="${esc(inicial(f.nome))}">` : `<span class="eq-ini" aria-hidden="true">${esc(inicial(f.nome))}</span>`;
      return `<li class="eq-feit" title="${esc(f.nome)}"><span class="eq-tile eq-tile-p">${img}</span>
        <span class="eq-fn">${esc(f.nome)}</span><span class="eq-fa">${f.ar != null ? `AR ${fmt.format(f.ar)}` : "—"}${d ? ` <span class="${d > 0 ? "pos" : "neg"}">${d > 0 ? "+" : "−"}${fmt.format(Math.abs(d))}</span>` : ""}</span>
        <span class="eq-fu">${esc(f.usos ?? "—")} usos</span></li>`;
    }).join("");
    return `<div class="eq-g eq-g-sint"><h3>Sintonia<small>${fmt.format(usados)} de ${fmt.format(total || usados)} slots</small></h3>
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
      <p class="muted eq-nota">AR e "vem de": regras do jogo com seus atributos${(eq.atributos && eq.atributos.aneis_plano || []).length ? ` (${esc(eq.atributos.aneis_plano.join(", "))})` : ""}. Letras: tabela de upgrade da wiki${fonte ? ` · <a href="${esc(fonte)}" target="_blank" rel="noopener noreferrer">fonte</a>` : ""}.</p>
      ${metaHtml(s)}${simHtml(s, p)}`;
  }

  // Resultado do simulador (meta do slot ou o que está nos seletores): AR e diferença para a cópia que você tem.
  function resultadoLinhas(r) {
    const d = r.agora ? total(r.peca) - total(r.agora) : null;
    const dif = d ? ` <span class="${d > 0 ? "pos" : "neg"}">${d > 0 ? "+" : "−"}${fmt.format(Math.abs(d))}</span>` : "";
    const linhas = [
      ["AR", `${esc(arTexto(r.peca.ar))}${dif}`],
      ["Você tem", r.agora ? `${esc(metaTexto(r.agora))} · ${esc(arTexto(r.agora.ar))}` : "não está no inventário"],
      ["Requisito", `<span class="${r.peca.requisito_ok === false ? "neg" : ""}">${esc(requisitoTexto(r.peca.requisito))}</span>`],
      ["Falta", esc(faltaTexto(r.falta))],
      ["Onde", esc(r.falta.ferreiro || "—")],
    ];
    const avisos = (r.falta.avisos || []).map((a) => `<p class="eq-alerta">${esc(a)}</p>`).join("");
    const conf = r.conferido ? "" : '<p class="eq-alerta">Calculado pela tabela do jogo, ainda não conferido no menu.</p>';
    return `<div class="tw"><table><tbody>${linhas.map(([k, v]) => `<tr><th scope="row">${k}</th><td>${v}</td></tr>`).join("")}</tbody></table></div>${avisos}${conf}`;
  }

  function metaHtml(s) {
    if (!s.meta) return "";
    return `<div class="eq-bloco"><h3>Meta<small>${esc(s.meta.item.nome)} ${esc(metaTexto(s.meta))}</small></h3>${resultadoLinhas(s.meta)}</div>`;
  }

  function simHtml(s, p) {
    if (!ctx || !["direita", "esquerda"].includes(s.grupo) || !ui.sim || ui.sim.slot !== s.slot) return "";
    const armas = p.armas || [];
    const sim = ui.sim;
    const res = ui.res && ui.res.item.id === sim.item ? ui.res : null;
    const opcao = (v, rot, sel) => `<option value="${esc(v)}"${sel ? " selected" : ""}>${esc(rot)}</option>`;
    const itens = armas.map((a) => opcao(a.id, `${a.nome} ${metaTexto(a)}`, a.id === sim.item)).join("");
    const maximo = res ? res.nivel_max : Math.max(sim.nivel, 10);
    const niveis = Array.from({ length: maximo + 1 }, (_, n) => opcao(n, `+${n}`, n === sim.nivel)).join("");
    const infs = infusaoOpcoes(res ? res.infusoes : [{ k: sim.infusao, nome: "…" }]).map((i) => opcao(i.k, i.rotulo, i.k === sim.infusao)).join("");
    const ligada = (p.metas || []).find((m) => m.item_id === sim.item);
    const igual = ligada && ligada.nivel === sim.nivel && ligada.infusao === sim.infusao;
    const botao = igual
      ? '<button type="button" class="pesq" data-meta="tirar">Tirar meta</button>'
      : `<button type="button" class="pesq" data-meta="virar"${res ? "" : " disabled"}>${ligada ? `Trocar meta (era ${esc(metaTexto(ligada))})` : "Virar meta"}</button>`;
    const corpoRes = ui.erro ? `<p class="eq-alerta">${esc(ui.erro)}</p>` : ui.carregando && !res ? '<p class="muted">calculando…</p>' : res ? resultadoLinhas(res) : "";
    return `<div class="eq-bloco eq-sim"><h3>Simular<small>reforço e infusão, pelas regras do jogo</small></h3>
      <div class="eq-sim-campos">
        <label>Arma<select data-sim="item">${itens}</select></label>
        <label>Reforço<select data-sim="nivel">${niveis}</select></label>
        <label>Infusão<select data-sim="infusao">${infs}</select></label>
      </div>${corpoRes}${botao}</div>`;
  }

  function metasHtml(p) {
    const lista = p.metas || [];
    if (!ctx || !lista.length) return "";
    const itens = lista.map((m) => {
      const r = m.resultado;
      const nome = r ? r.item.nome : m.nome;
      const info = r ? `AR ${arTexto(r.peca.ar)} · falta: ${faltaTexto(r.falta)}` : m.erro;
      return `<li><span class="eq-mn">${esc(nome)} <b>${esc(metaTexto(r || m))}</b></span><span class="eq-mi">${esc(info)}</span>
        <button type="button" class="pesq" data-meta-tirar="${esc(m.item_id)}">Tirar</button></li>`;
    }).join("");
    return `<h3 class="eq-rt">Metas</h3><ul class="eq-metas">${itens}</ul>`;
  }

  function corpo(eq, p) {
    const grupos = GRUPOS.map(([g, nome]) => {
      const slots = (eq.slots || []).filter((s) => s.grupo === g);
      return `<div class="eq-g eq-g-${g}"><h3>${nome}</h3><div class="eq-linha">${slots.map(slotHtml).join("")}</div></div>`;
    }).join("");
    const resumo = (eq.resumo || []).map((r) => `<tr><td>${esc(r.dado)}</td><td>${esc(r.agora)}</td><td>${esc(r.depois)}</td><td class="${r.sinal === "+" ? "pos" : r.sinal === "-" ? "neg" : ""}">${esc(r.efeito)}</td></tr>`).join("");
    const futuro = eq.origem && eq.origem !== "plano" ? "Melhor" : "Plano";
    return `<div class="eq-modos" role="group" aria-label="Mostrar">${MODOS.map(([m, l]) => `<button type="button" class="eq-modo" data-eq-modo="${m}" aria-pressed="${ui.modo === m}">${m === "plano" ? futuro : l}</button>`).join("")}</div>
      <div class="eq-tela"><div class="eq-inv">${grupos}${sintoniaHtml(eq)}</div><aside class="eq-det" aria-live="polite">${detalhe(eq, p, ui.slot)}</aside></div>
      ${resumo ? `<h3 class="eq-rt">O que muda</h3><div class="tw"><table><thead><tr><th>Slot</th><th>Agora</th><th>${futuro}</th><th>Efeito</th></tr></thead><tbody>${resumo}</tbody></table></div>` : ""}
      ${metasHtml(p)}`;
  }

  function html(p) {
    const eq = p.equipamento;
    if (!eq) return '<section><h2>Equipamento</h2><p class="empty">Sem dados de equipamento (pelo Buildsmith.exe ele vem do save).</p></section>';
    if (!ui.slot || !(eq.slots || []).some((s) => s.slot === ui.slot)) ui.slot = ((eq.slots || []).find((s) => s.muda) || (eq.slots || [])[0] || {}).slot || null;
    return `<section class="eq"><h2>Equipamento<small>agora × ${esc(DESTINO[eq.origem] || "plano")}</small></h2><div class="eq-app">${corpo(eq, p)}</div></section>`;
  }

  // Simular: começa com a arma do slot (na meta dela, se houver) e refaz a conta a cada mudança de seletor.
  function iniciarSim(eq, p) {
    const s = (eq.slots || []).find((x) => x.slot === ui.slot);
    if (!ctx || !s || !["direita", "esquerda"].includes(s.grupo)) return false;
    if (ui.sim && ui.sim.slot === s.slot) return false;
    const base = s.agora && (p.armas || []).find((a) => a.id === s.agora.id) || (p.armas || [])[0];
    if (!base) return false;
    const meta = s.meta && s.meta.item.id === base.id ? s.meta : null;
    ui.sim = { slot: s.slot, item: base.id, nivel: meta ? meta.nivel : base.nivel, infusao: meta ? meta.infusao : base.infusao };
    ui.res = null; ui.erro = null;
    return true;
  }

  function ligar(raiz, p, contexto) {
    if (!raiz || !p.equipamento) return;
    if (contexto !== undefined) ctx = contexto;
    const app = raiz.querySelector(".eq-app");
    const redesenhar = () => {
      const foco = document.activeElement && document.activeElement.dataset ? document.activeElement.dataset.sim : null;
      app.innerHTML = corpo(p.equipamento, p);
      trocaImagens(app);
      if (foco) { const el = app.querySelector(`[data-sim="${foco}"]`); if (el) el.focus(); }
    };
    const simular = async () => {
      const { item, nivel, infusao } = ui.sim;
      const pedido = ++ui.pedido;
      ui.carregando = true; ui.erro = null;
      try {
        const r = await fetch(`${ctx.base}/simular?item=${item}&nivel=${nivel}&infusao=${infusao}`, { cache: "no-store" });
        const j = await r.json().catch(() => ({}));
        if (pedido !== ui.pedido) return;
        if (r.ok) ui.res = j; else { ui.res = null; ui.erro = j.erro || `erro ${r.status}`; }
      } catch (e) {
        if (pedido === ui.pedido) ui.erro = "servidor fora do ar";
      }
      ui.carregando = false;
      redesenhar();
    };
    const gravar = async (item, nivel, infusao, ativa) => {
      try {
        const r = await fetch(`${ctx.base}/metas/${item}`, { method: "POST", headers: ctx.headers,
          body: JSON.stringify({ item_id: item, nivel, infusao, ativa, desde: new Date().toISOString() }) });
        if (!r.ok) { ui.erro = r.status === 409 ? "metas demais: tire uma antes" : "não consegui gravar a meta"; redesenhar(); return; }
        ctx.atualizar();
      } catch (e) { ui.erro = "servidor fora do ar"; redesenhar(); }
    };
    if (iniciarSim(p.equipamento, p)) simular();
    redesenhar();
    app.addEventListener("click", (ev) => {
      const m = ev.target.closest("[data-eq-modo]");
      if (m) { ui.modo = m.dataset.eqModo; redesenhar(); return; }
      const s = ev.target.closest("[data-eq-slot]");
      if (s) {
        ui.slot = s.dataset.eqSlot;
        if (iniciarSim(p.equipamento, p)) simular();
        redesenhar();
        const b = app.querySelector(`[data-eq-slot="${CSS.escape(ui.slot)}"]`); if (b) b.focus();
        return;
      }
      const meta = ev.target.closest("[data-meta]");
      if (meta && ui.sim) { gravar(ui.sim.item, ui.sim.nivel, ui.sim.infusao, meta.dataset.meta === "virar"); return; }
      const tirar = ev.target.closest("[data-meta-tirar]");
      if (tirar) {
        const id = Number(tirar.dataset.metaTirar);
        const m2 = (p.metas || []).find((x) => x.item_id === id);
        if (m2) gravar(id, m2.nivel, m2.infusao, false);
      }
    });
    app.addEventListener("change", (ev) => {
      const sel = ev.target.closest("[data-sim]");
      if (!sel || !ui.sim) return;
      const v = Number(sel.value);
      if (sel.dataset.sim === "item") {
        const a = (p.armas || []).find((x) => x.id === v);
        ui.sim = { ...ui.sim, item: v, nivel: a ? a.nivel : 0, infusao: a ? a.infusao : 0 };
      } else ui.sim = { ...ui.sim, [sel.dataset.sim]: v };
      simular();
      redesenhar();
    });
  }

  function trocaImagens(raiz) {
    raiz.querySelectorAll(".eq-tile img").forEach((img) => {
      const troca = () => { const s = document.createElement("span"); s.className = "eq-ini"; s.textContent = img.dataset.ini || "?"; img.replaceWith(s); };
      if (img.complete && img.naturalWidth === 0) troca(); else img.addEventListener("error", troca);
    });
  }

  window.buildsmithEquip = { html, ligar, _teste: { letras, arTexto, numero, partesTexto, delta, requisitoTexto, metaTexto, faltaTexto, infusaoOpcoes, total } };
})();
