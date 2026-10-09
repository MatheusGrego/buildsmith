(function () {
  const STATS = ["VGR", "END", "VIT", "ATN", "STR", "DEX", "INT", "FTH", "ADP"];
  const GRUPOS = [["equipar", "Equipar"], ["explorar", "Explorar"], ["chefe", "Chefes"], ["troca", "Trocas de alma"],
                  ["compra", "Compras"], ["upgrade", "Upgrades"], ["farm", "Farms"], ["nivel", "Nível"]];
  const ACESSO = { agora: "Agora", em_breve: "Em breve", tarde: "Tarde" };
  const DESTAQUE = { mais_cedo: "Mais cedo", mais_rentavel: "Mais rentável" };
  const ESTADO_FEITICO = { equipado: "Equipado", tem: "Tem", sugerido: "Sugerido" };
  const state = { db: null, plano: null, feitos: {}, pedidos: {}, selecao: null };
  const slug = (text) => String(text).normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 180) || "pedido";
  const fogueira = (attr, value, label) => `<button class="fogueira" type="button" ${attr}="${esc(value)}" aria-pressed="false" aria-label="${esc(label)}" title="${esc(label)}" hidden><img src="icons/fogueira.png" alt=""></button>`;
  const pesq = (texto, origem) => `<button class="pesq" type="button" data-q="${esc(texto)}" data-origem="${esc(origem)}">Pesquisar</button>`;
  function requisito(req, origem) {
    if (!req) return "—";
    if (typeof req === "object" && req.item) return `<a class="req-link" href="#item-${esc(req.item)}" data-goto-item="${esc(req.item)}">${esc(req.texto)}</a>`;
    const text = typeof req === "object" ? req.texto : req;
    return `${esc(text)}${pesq(text, origem)}`;
  }
  const fmt = new Intl.NumberFormat("pt-BR");
  const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  // Link só http(s) absoluto: javascript:, data: e afins viram texto sem link.
  const safeUrl = (url) => { try { const u = new URL(String(url ?? "")); return u.protocol === "https:" || u.protocol === "http:" ? u.href : ""; } catch (e) { return ""; } };
  const ext = (url, inner, cls = "") => { const href = safeUrl(url); return href ? `<a class="${cls}" href="${esc(href)}" target="_blank" rel="noopener noreferrer">${inner}</a>` : `<span class="${cls}">${inner}</span>`; };
  const cls = (sinal) => sinal === "+" ? "pos" : sinal === "-" ? "neg" : "";
  const when = (iso) => { const d = new Date(iso); return isNaN(d) ? esc(iso) : d.toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" }); };
  const letter = (name) => (name || "?").trim().replace(/^the\s+/i, "").charAt(0).toUpperCase();
  const initial = (name) => `<span class="ini" aria-hidden="true">${esc(letter(name))}</span>`;
  // Ícone só local (o prepare_page baixa para icons/): imagem de fora avisaria um terceiro que a página abriu.
  const localIcon = (src) => typeof src === "string" && /^icons\/[A-Za-z0-9._-]+$/.test(src);
  const icon = (src, name) => localIcon(src) ? `<img class="ic" src="${esc(src)}" alt="" data-ini="${esc(letter(name))}">` : initial(name);
  function fallbackIcons(root) {
    root.querySelectorAll("img.ic").forEach((img) => {
      const swap = () => { const s = document.createElement("span"); s.className = "ini"; s.setAttribute("aria-hidden", "true"); s.textContent = img.dataset.ini; img.replaceWith(s); };
      if (img.complete && img.naturalWidth === 0) swap(); else img.addEventListener("error", swap);
    });
  }

  function node(n) {
    const inner = `${icon(n.icone, n.nome)}<span class="nm">${esc(n.nome)}</span>${n.sub ? `<span class="sub">${esc(n.sub)}</span>` : ""}`;
    const solo = n.sub ? "" : " solo";
    return n.link ? ext(n.link, inner, `node${solo}`) : `<span class="node${solo}">${inner}</span>`;
  }
  const flow = (nodes) => (nodes && nodes.length) ? `<div class="flow">${nodes.map(node).join('<span class="arrow" aria-hidden="true">&#10142;</span>')}</div>` : "";

  function rows(lines, heads) {
    if (!lines || !lines.length) return "";
    const body = lines.map((l) => `<tr><td>${esc(l.dado)}</td><td>${esc(l.agora)}</td><td>${esc(l.depois)}</td><td class="${cls(l.sinal)}">${esc(l.efeito)}</td></tr>`).join("");
    return `<div class="tw"><table><thead><tr>${heads.map((h) => `<th>${h}</th>`).join("")}</tr></thead><tbody>${body}</tbody></table></div>`;
  }

  function top(p) {
    const c = p.personagem;
    return `<header class="top">
      <p class="meta">${esc(p.jogo)} · atualizado ${when(p.gerado_em)}</p>
      <h1>${esc(c.name)}</h1>
      <div class="legend"><span class="l-pos">ganho</span><span class="l-neg">perda / falta</span><span class="l-link">link da wiki</span></div>
      <div class="acoes" id="forja-acoes" hidden>
        <button class="acao" type="button" data-rodar="plano"><img src="icons/fogueira.png" alt="">Atualizar plano</button>
        <button class="acao" type="button" data-rodar="fila"><img src="icons/fogueira.png" alt="">Responder fila<span class="count" id="forja-fila" hidden></span></button>
      </div>
      <div class="forja" id="forja" hidden></div>
    </header>`;
  }

  function sheet(p) {
    const c = p.personagem;
    return `<section><h2>Ficha</h2>
      <div class="tw"><table><thead><tr><th>Nível</th><th class="r">Almas em mãos</th><th class="r">Soul memory</th><th>Objetivo</th></tr></thead>
        <tbody><tr><td><span class="cell-ic"><img src="icons/almas.png" alt="" onerror="this.remove()">${fmt.format(c.level)}</span></td><td class="r">${fmt.format(c.souls)}</td><td class="r">${fmt.format(c.soul_memory)}</td><td>${esc(p.objetivo)}</td></tr></tbody></table></div>
      <div class="equipped">${(c.equipado || []).map(node).join("")}</div>
    </section>`;
  }

  function changes(p) {
    return `<section><h2>Desde a última vez</h2>${p.mudancas.length ? rows(p.mudancas, ["Dado", "Antes", "Agora", "Efeito"]) : '<p class="empty">Primeira leitura do save.</p>'}</section>`;
  }

  function steps(p) {
    const groups = GRUPOS.map(([tipo, titulo]) => [titulo, p.passos.filter((s) => s.tipo === tipo)]).filter(([, list]) => list.length);
    if (!groups.length) return '<section><h2>Próximos passos</h2><p class="empty">Nenhum passo pendente.</p></section>';
    return `<section><h2>Próximos passos</h2>${groups.map(([titulo, list]) => `<div class="grupo">
      <h3>${titulo}<small>${list.length}</small></h3>
      <ol class="steps">${list.map((s, i) => `<li class="step">
        <div class="step-head" id="passo-${esc(s.id)}">${fogueira("data-passo", s.id, "Marcar como feito")}<span class="step-no">${i + 1}</span><span class="step-title">${esc(s.titulo)}</span><span class="confirmado" data-confirma="${esc(s.id)}"></span></div>
        ${flow(s.fluxo)}
        ${rows(s.dados, ["Dado", "Agora", "Depois", "Efeito"])}
      </li>`).join("")}</ol>
    </div>`).join("")}</section>`;
  }

  function stats(p) {
    const now = p.personagem.stats, goal = p.alvo_stats;
    const list = STATS.map((k) => {
      const a = now[k], b = goal[k], pct = (v) => Math.min(v, 99) / 99 * 100;
      return `<div class="stat">
        <img src="icons/stat-${k}.png" alt="" onerror="this.style.visibility='hidden'">
        <span class="abbr">${k}</span>
        <div class="bar" role="img" aria-label="${k}: ${a} de 99, alvo ${b}"><div class="now" style="width:${pct(a)}%"></div>${b > a ? `<div class="goal" style="left:calc(${pct(b)}% - 1px)"></div>` : ""}</div>
        <span class="val">${a}${b > a ? ` <span class="pos">→ ${b}</span>` : ""}</span>
      </div>`;
    }).join("");
    return `<section><h2>Atributos</h2><div class="stats">${list}</div></section>`;
  }

  function phases(p) {
    if (!p.fases.length) return `<section><h2>Fases de nível</h2><p class="empty">Sem fases planejadas.</p></section>`;
    let acc = 0;
    const body = p.fases.map((f) => {
      acc += f.almas;
      return `<tr><td><span class="cell-ic"><img src="icons/stat-${esc(f.atributo)}.png" alt="" onerror="this.remove()">${esc(f.nome)}</span></td><td>${f.de} → ${f.ate}</td><td class="r neg">${fmt.format(f.almas)}</td><td class="r">${fmt.format(acc)}</td></tr>`;
    }).join("");
    const last = p.fases[p.fases.length - 1].ate;
    return `<section><h2>Fases de nível</h2><div class="tw"><table>
      <thead><tr><th>Fase</th><th>Nível</th><th class="r">Custo (almas)</th><th class="r">Acumulado</th></tr></thead>
      <tbody>${body}</tbody>
      <tfoot><tr><td colspan="3">Total até o nível ${last}</td><td class="r">${fmt.format(acc)}</td></tr></tfoot>
    </table></div></section>`;
  }

  function items(p) {
    const selo = (text, cls) => `<span class="estado ${cls}">${esc(text)}</span>`;
    const list = p.itens.map((it) => {
      const line = (f, i) => [
        String(i + 1),
        flow(f.fluxo),
        requisito(f.requisito, it.item.nome),
        selo(ACESSO[f.acesso] || f.acesso, f.acesso === "agora" ? "feito" : f.acesso === "tarde" ? "apagado" : ""),
        esc(f.rendimento || "—"),
        (f.destaques || []).map((d) => selo(DESTAQUE[d] || d, "destaque")).join("") || "",
      ];
      const heads = ["#", "Como", "Requisito", "Acesso", "Rendimento", "Destaque"];
      const fontes = (it.fontes || []).map((f, i) => [f, i]);
      const top = fontes.filter(([f]) => (f.destaques || []).length);
      const rest = fontes.filter(([f]) => !(f.destaques || []).length);
      const fix = (html) => html.replace(/<td>(<span class="estado)/g, '<td class="selos">$1');
      const table = fix(grid(heads, (top.length ? top : fontes).map(([f, i]) => line(f, i))))
        + (top.length && rest.length ? `<details class="mais"><summary>Ver todas as fontes (${fontes.length})</summary>${fix(grid(heads, rest.map(([f, i]) => line(f, i))))}</details>` : "");
      return `<div class="block" id="item-${esc(it.id)}">
        <div class="block-head">${node(it.item)}${it.fonte ? ext(it.fonte, "fonte", "muted") : ""}</div>
        ${table}
        ${rows(it.dados, ["Dado", "Agora", "Com o item", "Efeito"])}
      </div>`;
    }).join("");
    return `<section><h2>Onde pegar<small>mais cedo e mais rentável a partir de onde você está</small></h2>${list ? `<div class="blocks">${list}</div>` : '<p class="empty">Nenhum item pendente.</p>'}</section>`;
  }

  function builds(p) {
    const list = p.comparacao.map((b) => `<div class="block">
      <div class="block-head"><span class="step-title">${b.link ? ext(b.link, esc(b.build)) : esc(b.build)}</span></div>
      ${rows(b.dados, ["Dado", "Você", "Build", "Diferença"])}
      ${b.ajuste && b.ajuste.length ? `<span class="label">Ajuste sugerido</span>${flow(b.ajuste)}` : ""}
    </div>`).join("");
    return `<section><h2>Outras builds</h2>${list ? `<div class="blocks">${list}</div>` : '<p class="empty">Nenhuma comparação ainda.</p>'}</section>`;
  }

  function grid(heads, lines, right = []) {
    const th = heads.map((h, i) => `<th${right.includes(i) ? ' class="r"' : ""}>${h}</th>`).join("");
    const body = lines.map((cells) => `<tr>${cells.map((c, i) => `<td${right.includes(i) ? ' class="r"' : ""}>${c}</td>`).join("")}</tr>`).join("");
    return `<div class="tw"><table><thead><tr>${th}</tr></thead><tbody>${body}</tbody></table></div>`;
  }

  const ESTADO = { derrotado: "Derrotado", vivo: "Vivo", feito: "Feito", pendente: "Pendente" };
  const estado = (value) => `<span class="estado${value === "derrotado" || value === "feito" ? " feito" : ""}">${esc(ESTADO[value] || value)}</span>`;

  function progress(p) {
    const pr = p.progresso;
    if (!pr) return '<section><h2>Progresso</h2><p class="empty">Este plano não tem dados de progresso.</p></section>';
    const killed = pr.chefes.filter((c) => c.estado === "derrotado").length;
    const bosses = pr.chefes.length ? grid(["Chefe", "Estado"], pr.chefes.map((c) => [node(c.no), estado(c.estado)])) : '<p class="empty">Nenhum chefe listado.</p>';
    const buys = pr.compras.length ? grid(["Loja", "Item", "Qtd"], pr.compras.map((c) => [node(c.loja), node(c.item), fmt.format(c.qtd)]), [2]) : '<p class="empty">Nenhuma compra registrada.</p>';
    const events = pr.eventos && pr.eventos.length
      ? grid(["Evento", "Estado"], pr.eventos.map((e) => [esc(e.nome), estado(e.estado)]))
      : '<p class="empty">Nenhum evento aprendido. Rode /buildsmith:build ds2 antes e depois do evento, contando o que aconteceu.</p>';
    return `<section><h2>Chefes<small>${killed} de ${pr.chefes.length} derrotados</small></h2>${bosses}</section>
      <section><h2>Compras<small>${pr.compras.length}</small></h2>${buys}</section>
      <section><h2>Eventos</h2>${events}</section>`;
  }

  function damage(p) {
    const list = p.dano || [];
    if (!list.length) return '<section><h2>Dano</h2><p class="empty">Este plano não tem cálculo de dano.</p></section>';
    const value = (v) => typeof v === "number" ? fmt.format(v) : "—";
    const lines = list.map((d) => {
      const diff = typeof d.agora === "number" && typeof d.depois === "number" ? d.depois - d.agora : null;
      const shown = diff === null ? "—" : `<span class="${diff > 0 ? "pos" : diff < 0 ? "neg" : ""}">${diff > 0 ? "+" : ""}${fmt.format(diff)}</span>`;
      return [node(d.arma), value(d.agora), value(d.depois), shown, esc(d.detalhe || ""), flow(d.por_causa) || "—"];
    });
    return `<section><h2>Dano<small>AR físico pelas regras do jogo</small></h2>${grid(["Arma", "Agora", "Depois", "Diferença", "Mudança", "Por causa de"], lines, [1, 2, 3])}</section>`;
  }

  function nowPanel(p) {
    const a = p.agora;
    if (!a) return "";
    const byId = Object.fromEntries(p.passos.map((s) => [s.id, s]));
    const acoes = a.acoes.map((id) => byId[id]).filter(Boolean).map((s) => `<div class="agora-acao">
      ${fogueira("data-passo", s.id, "Marcar como feito")}
      <a class="step-title" href="#passo-${esc(s.id)}" data-goto-passo="${esc(s.id)}">${esc(s.titulo)}</a>
      ${flow(s.fluxo)}
    </div>`).join("");
    const faltam = (a.faltam || []).length ? `<span>Faltam:</span>${flow(a.faltam)}` : "";
    return `<section class="agora" aria-label="Próximas ações"><h2>Agora</h2>${acoes}
      <div class="agora-resumo">${typeof a.almas === "number" ? `<span>Almas pra essas ações: <span class="neg">${fmt.format(a.almas)}</span></span>` : ""}${faltam}</div>
    </section>`;
  }

  function spells(p) {
    const f = p.feiticos;
    if (!f) return '<section><h2>Feitiços</h2><p class="empty">Este plano não tem feitiços.</p></section>';
    const ar = Object.entries(f.ar || {}).map(([k, v]) => `${k} ${fmt.format(v)}`).join(" · ");
    const lines = f.lista.map((sp) => [
      fogueira("data-feitico", sp.id, "Selecionar para sintonizar"),
      node(sp.no),
      `<span class="estado${sp.estado === "equipado" ? " feito" : sp.estado === "sugerido" ? " destaque" : ""}">${esc(ESTADO_FEITICO[sp.estado] || sp.estado)}</span>`,
      esc(sp.elemento || "—"),
      typeof sp.ar === "number" ? fmt.format(sp.ar) : "—",
      fmt.format(sp.usos),
      fmt.format(sp.slots),
      `<span class="${sp.requisito_ok ? "" : "neg"}">${esc(sp.requisito || "—")}</span>`,
    ]);
    return `<section><h2>Feitiços<small>AR calculado pelas regras do jogo</small></h2>
      <div class="block-head">${node(f.catalisador)}<span class="muted">AR do catalisador: ${esc(ar)}</span></div>
      <p class="slots">Slots selecionados: <span id="slots-usados">—</span> de ${fmt.format(f.slots.total)}</p>
      ${grid(["", "Feitiço", "Estado", "Elemento", "AR", "Usos", "Slots", "Requisito"], lines, [4, 5, 6]).replace(/<td>(<span class="estado)/g, '<td class="selos">$1')}
    </section>`;
  }

  function queue() {
    return `<section><h2>Fila de pesquisa<small>${forja.rodar ? "o botão Responder fila (no topo) responde agora" : "respondida no próximo /buildsmith:build"}</small></h2>
      <form class="fila-form" id="fila-form">
        <label class="sr-only" for="fila-texto">O que você quer saber</label>
        <input id="fila-texto" type="text" maxlength="120" placeholder="Onde farmar Bonfire Ascetic" autocomplete="off">
        <button type="submit">Pesquisar</button>
      </form>
      <div id="fila-lista"><p class="empty">Nenhum pedido ainda.</p></div>
    </section>`;
  }

  function sources(p) {
    return `<section><h2>Fontes</h2>${p.fontes.length ? `<ul class="sources">${p.fontes.map((f) => `<li>${f.url ? ext(f.url, esc(f.titulo)) : esc(f.titulo)}${f.data ? ` <span class="muted">· ${esc(f.data)}</span>` : ""}</li>`).join("")}</ul>` : '<p class="empty">Sem fontes.</p>'}</section>`;
  }

  const app = document.getElementById("app");
  const KEY = "buildsmith-aba";

  function render(p) {
    const tabs = [
      { id: "ficha", label: "Ficha", count: p.mudancas.length || null, html: sheet(p) + changes(p) },
      { id: "passos", label: "Passos", count: p.passos.length, html: steps(p) },
      { id: "progresso", label: "Progresso", count: p.progresso ? p.progresso.chefes.filter((c) => c.estado === "derrotado").length : null, html: progress(p) },
      { id: "dano", label: "Dano", count: (p.dano || []).length || null, html: damage(p) },
      { id: "feiticos", label: "Feitiços", count: p.feiticos ? p.feiticos.lista.length : null, html: spells(p) },
      { id: "atributos", label: "Atributos", count: null, html: stats(p) },
      { id: "fases", label: "Fases", count: p.fases.length, html: phases(p) },
      { id: "onde", label: "Onde pegar", count: p.itens.length, html: items(p) },
      { id: "builds", label: "Builds", count: p.comparacao.length, html: builds(p) },
      { id: "fila", label: "Fila", count: null, html: queue() },
      { id: "fontes", label: "Fontes", count: p.fontes.length, html: sources(p) },
    ];
    let saved = null;
    try { saved = localStorage.getItem(KEY); } catch (e) { saved = null; }
    const fromHash = location.hash.slice(1);
    const start = [fromHash, saved, "passos"].find((id) => tabs.some((t) => t.id === id));
    state.plano = p;
    app.innerHTML = top(p) + nowPanel(p)
      + `<nav class="tabs" role="tablist" aria-label="Seções">${tabs.map((t) => `<button class="tab" role="tab" id="aba-${t.id}" aria-controls="painel-${t.id}" aria-selected="${t.id === start}" data-tab="${t.id}">${t.label}${t.count ? `<span class="count">${t.count}</span>` : ""}</button>`).join("")}</nav>`
      + tabs.map((t) => `<div class="tab-panel" role="tabpanel" id="painel-${t.id}" aria-labelledby="aba-${t.id}"${t.id === start ? "" : " hidden"}>${t.html}</div>`).join("");
    app.querySelector(".tabs").addEventListener("click", (ev) => {
      const btn = ev.target.closest(".tab");
      if (!btn) return;
      select(btn.dataset.tab);
    });
    app.querySelector(".tabs").addEventListener("keydown", (ev) => {
      if (ev.key !== "ArrowRight" && ev.key !== "ArrowLeft") return;
      const list = [...app.querySelectorAll(".tab")];
      const i = list.indexOf(document.activeElement);
      const next = list[(i + (ev.key === "ArrowRight" ? 1 : list.length - 1)) % list.length];
      next.focus();
      select(next.dataset.tab);
    });
  }

  function select(id) {
    app.querySelectorAll(".tab").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.tab === id)));
    app.querySelectorAll(".tab-panel").forEach((panel) => { panel.hidden = panel.id !== `painel-${id}`; });
    try { localStorage.setItem(KEY, id); } catch (e) { /* armazenamento bloqueado: só não lembra a aba */ }
    if (history.replaceState) history.replaceState(null, "", `#${id}`);
  }
  function goTo(tab, targetId) {
    select(tab);
    const el = document.getElementById(targetId);
    if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function selectedSpells() {
    if (state.selecao) return state.selecao;
    return (state.plano.feiticos ? state.plano.feiticos.lista : []).filter((sp) => sp.estado === "equipado").map((sp) => sp.id);
  }

  function applyState() {
    app.querySelectorAll("[data-passo]").forEach((b) => {
      const f = state.feitos[b.dataset.passo];
      b.setAttribute("aria-pressed", String(Boolean(f && f.marcado)));
    });
    app.querySelectorAll("[data-confirma]").forEach((el) => {
      const f = state.feitos[el.dataset.confirma];
      el.textContent = f && f.marcado ? (f.confirmado === true ? "confirmado pelo save" : f.confirmado === false ? "o save ainda não mostra" : "confirma no próximo /build") : "";
    });
    const chosen = selectedSpells();
    app.querySelectorAll("[data-feitico]").forEach((b) => b.setAttribute("aria-pressed", String(chosen.includes(b.dataset.feitico))));
    const used = (state.plano.feiticos ? state.plano.feiticos.lista : []).filter((sp) => chosen.includes(sp.id)).reduce((n, sp) => n + sp.slots, 0);
    const slotsEl = document.getElementById("slots-usados");
    if (slotsEl && state.plano.feiticos) slotsEl.innerHTML = `<span class="${used > state.plano.feiticos.slots.total ? "neg" : "pos"}">${used}</span>`;
    app.querySelectorAll(".pesq[data-q]").forEach((b) => {
      const ped = state.pedidos[slug(b.dataset.q)];
      if (!state.db) return;
      b.disabled = Boolean(ped);
      b.textContent = !ped ? "Pesquisar" : ped.estado === "respondido" ? "Respondido" : "Na fila";
    });
    const list = Object.values(state.pedidos).sort((a, b) => String(b.criado_em).localeCompare(String(a.criado_em)));
    const box = document.getElementById("fila-lista");
    if (box && list.length) {
      box.innerHTML = grid(["Pedido", "De onde", "Estado", "Resposta"], list.map((ped) => [
        esc(ped.texto), esc(ped.origem || "—"),
        `<span class="estado${ped.estado === "respondido" ? " feito" : ""}">${ped.estado === "respondido" ? "Respondido" : "Na fila"}</span>`,
        ped.item_id ? `<a class="req-link" href="#item-${esc(ped.item_id)}" data-goto-item="${esc(ped.item_id)}">ver em Onde pegar</a>` : "—",
      ])).replace(/<td>(<span class="estado)/g, '<td class="selos">$1');
    }
    const tab = document.querySelector('[data-tab="fila"]');
    const open = list.filter((ped) => ped.estado !== "respondido").length;
    if (tab) tab.innerHTML = `Fila${open ? `<span class="count">${open}</span>` : ""}`;
    paintActions();
  }

  // Forja: os botões rodam a skill sem janela (POST rodar no servidor local) e a página acompanha (GET execucao).
  const forja = { base: null, rodar: false, status: null, desde: -1, linhas: [], visivel: false, poll: null, relogio: null, recebido: 0, fechou: true, seguir: true };
  const HEADERS = { "Content-Type": "application/json", "X-Buildsmith": "1" };
  const TITULO = { plano: ["Forjando o plano", "Plano forjado"], fila: ["Respondendo a fila", "Fila respondida"] };
  const tempo = (s) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;
  const usd = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "USD" });
  const daqui = (st) => !st.alvo || location.pathname.startsWith(`/p/${st.alvo.jogo}/${st.alvo.personagem}/`);
  const pendentes = () => Object.values(state.pedidos).filter((ped) => ped.estado !== "respondido").length
    + Object.values(state.feitos).filter((f) => f.marcado && f.confirmado == null).length;

  function paintActions() {
    const acoes = document.getElementById("forja-acoes");
    if (!acoes) return;
    acoes.hidden = !forja.rodar;
    const busy = Boolean(forja.status && forja.status.estado === "rodando");
    const n = pendentes();
    acoes.querySelectorAll("[data-rodar]").forEach((b) => { b.disabled = busy || (b.dataset.rodar === "fila" && !n); });
    const count = document.getElementById("forja-fila");
    if (count) { count.hidden = !n; count.textContent = String(n); }
  }

  function linha(e, nova) {
    const el = document.createElement("div");
    el.className = `linha linha-${e.tipo}${nova ? " nova" : ""}`;
    el.innerHTML = `<span class="t">${tempo(e.t)}</span><span class="x">${esc(e.texto)}</span>`;
    return el;
  }

  function paintForja(novos = []) {
    paintActions();
    const box = document.getElementById("forja");
    const st = forja.status;
    if (!box) return;
    if (!st || !forja.visivel || !st.etapas || !st.etapas.length) { box.hidden = true; return; }
    box.hidden = false;
    let log = box.querySelector(".microtexto");
    if (!log) {
      box.innerHTML = `<div class="forja-head" aria-live="polite"><span class="forja-titulo"></span><span class="forja-etapa"></span><span class="forja-tempo"></span><span class="forja-botoes"></span></div>
        <ol class="etapas" style="--n:${st.etapas.length}">${st.etapas.map((e) => `<li class="etapa" data-etapa="${esc(e.id)}"><span class="seg"></span><span class="rotulo">${esc(e.nome)}</span></li>`).join("")}</ol>
        <div class="microtexto" role="log" aria-live="off" aria-label="O que o Claude está fazendo" tabindex="0"></div>
        <p class="forja-msg" hidden></p>`;
      log = box.querySelector(".microtexto");
      log.append(...forja.linhas.map((e) => linha(e, false)));
      log.scrollTop = log.scrollHeight;
      delete box.dataset.estado;
      forja.seguir = true;
      const parar = () => { forja.seguir = false; };
      log.addEventListener("wheel", parar, { passive: true });
      log.addEventListener("touchstart", parar, { passive: true });
      log.addEventListener("scroll", () => { if (log.scrollHeight - log.scrollTop - log.clientHeight < 8) forja.seguir = true; }, { passive: true });
    } else if (novos.length) {
      log.append(...novos.map((e) => linha(e, true)));
      while (log.childElementCount > 200) log.firstElementChild.remove();
      if (forja.seguir) log.scrollTop = log.scrollHeight;  // direto: rolagem suave para em aba de fundo; a linha nova já entra animada
    }
    st.etapas.forEach((e) => {
      const li = box.querySelector(`[data-etapa="${e.id}"]`);
      if (!li) return;
      li.className = `etapa ${e.estado}`;
      if (e.estado === "atual") li.setAttribute("aria-current", "step"); else li.removeAttribute("aria-current");
    });
    const rodando = st.estado === "rodando";
    const atual = st.etapas.findIndex((e) => e.estado === "atual");
    box.classList.toggle("erro", st.estado === "erro" || st.estado === "cancelado");
    const nomes = TITULO[st.modo] || TITULO.plano;
    const titulo = !daqui(st) && rodando ? `Rodando para ${st.alvo.personagem.replace(/-/g, " ")}`
      : rodando ? nomes[0]
      : st.estado === "ok" ? nomes[1]
      : st.estado === "cancelado" ? "Cancelado" : "A forja apagou";
    box.querySelector(".forja-titulo").textContent = titulo;
    box.querySelector(".forja-etapa").textContent = rodando && atual >= 0 ? `${st.etapas[atual].nome} · ${atual + 1} de ${st.etapas.length}` : "";
    paintClock();
    if (box.dataset.estado !== st.estado) {
      box.dataset.estado = st.estado;
      box.querySelector(".forja-botoes").innerHTML = rodando ? '<button class="pesq" type="button" data-forja="cancelar">Cancelar</button>'
        : `${st.estado === "ok" ? "" : '<button class="pesq" type="button" data-forja="repetir">Tentar de novo</button>'}<button class="pesq" type="button" data-forja="fechar">Fechar</button>`;
      const msg = box.querySelector(".forja-msg");
      msg.textContent = rodando ? "" : st.estado === "ok" ? (st.resposta || "") : (st.mensagem || "");
      msg.hidden = !msg.textContent;
    }
  }

  function paintClock() {
    const st = forja.status;
    const el = document.querySelector("#forja .forja-tempo");
    if (!st || !el) return;
    el.textContent = st.estado === "rodando"
      ? tempo(st.segundos + (Date.now() - forja.recebido) / 1000)
      : tempo(st.segundos || 0) + (typeof st.custo_usd === "number" ? ` · ${usd.format(st.custo_usd)}` : "");
  }

  function ingest(st) {
    const novos = (st.eventos || []).filter((e) => e.i > forja.desde);
    novos.forEach((e) => { forja.linhas.push(e); forja.desde = e.i; });
    forja.linhas.splice(0, Math.max(0, forja.linhas.length - 200));
    forja.status = st;
    forja.recebido = Date.now();
    clearInterval(forja.relogio);
    if (st.estado === "rodando") forja.relogio = setInterval(paintClock, 1000);
    paintForja(novos);
  }

  async function poll() {
    clearTimeout(forja.poll);
    try {
      const r = await fetch(`${forja.base}/execucao?desde=${forja.desde}`, { cache: "no-store" });
      if (r.ok) ingest(await r.json());
    } catch (e) { /* servidor ocupado: tenta no próximo ciclo */ }
    if (forja.status && forja.status.estado === "rodando") forja.poll = setTimeout(poll, 700);
    else terminou();
  }

  async function rodar(modo) {
    if (!forja.base) return;
    Object.assign(forja, { visivel: true, linhas: [], desde: -1, fechou: false });
    const box = document.getElementById("forja");
    if (box) box.innerHTML = "";
    try {
      const r = await fetch(`${forja.base}/rodar`, { method: "POST", headers: HEADERS, body: JSON.stringify({ modo }) });
      ingest(await r.json());
    } catch (e) {
      ingest({ estado: "erro", modo, mensagem: "O servidor local não respondeu. Abra pelo atalho Forja de Build.", etapas: [{ id: "fim", nome: "Concluído", estado: "pendente" }], eventos: [], segundos: 0 });
      return;
    }
    poll();
  }

  async function terminou() {
    const st = forja.status;
    if (!st || forja.fechou) return;
    forja.fechou = true;
    if (st.estado !== "ok" || !daqui(st)) return;
    faixa((TITULO[st.modo] || TITULO.plano)[1]);
    try {
      const r = await fetch("plano.json", { cache: "no-store" });
      if (!r.ok) return;
      render(await r.json());
      fallbackIcons(app);
      if (state.db) app.querySelectorAll(".fogueira").forEach((b) => { b.hidden = false; });
      applyState();
      paintForja();
    } catch (e) { /* plano novo ilegível: a página antiga continua */ }
  }

  function faixa(texto) {
    const el = document.getElementById("faixa");
    if (!el) return;
    const span = el.firstElementChild;
    span.textContent = texto;
    span.style.animation = "none";
    void span.offsetWidth;
    span.style.animation = "";
    el.hidden = false;
    clearTimeout(faixa.t);
    faixa.t = setTimeout(() => { el.hidden = true; }, 2900);
  }

  async function iniciarForja() {
    paintActions();
    try {
      const r = await fetch(`${forja.base}/execucao`, { cache: "no-store" });
      if (!r.ok) return;
      const st = await r.json();
      if (st.estado !== "rodando") { forja.desde = st.ultimo; return; }
      Object.assign(forja, { visivel: true, fechou: false });
      ingest(st);
      poll();
    } catch (e) { /* sem forja: os botões ficam, o progresso aparece no próximo clique */ }
  }


  // Texto de pedido vira termo de busca para o Claude (fila ou comando copiado): uma linha, caracteres de nome
  // de item e no máximo 120. Um requisito vindo da wiki com várias linhas não chega inteiro a lugar nenhum.
  const limpaPedido = (texto, max = 120) => String(texto ?? "")
    .replace(/[\u0000-\u001f\u007f-\u009f\u2028\u2029]/g, " ")
    .replace(/[^\p{L}\p{N} '&+,.()\-]/gu, "")
    .replace(/\s+/g, " ").trim().slice(0, max).trim();

  async function enqueue(texto, origem, button) {
    const text = limpaPedido(texto);
    if (!text) return;
    if (!state.db) {
      const cmd = `/buildsmith:build ds2 onde pegar: ${text}`;
      const note = document.createElement("span");
      note.className = "copiado";
      try { await navigator.clipboard.writeText(cmd); note.textContent = `Copiado: ${cmd}`; }
      catch (e) { note.textContent = cmd; }
      (button || document.getElementById("fila-form")).after(note);
      return;
    }
    const id = slug(text);
    if (state.pedidos[id]) return;
    if (button) button.disabled = true;
    try {
      await state.db.doc(`pedidos/${id}`).set({ texto: text, origem: limpaPedido(origem || "fila", 80) || "fila", estado: "na_fila", criado_em: new Date().toISOString() });
    } catch (e) {
      if (button) button.disabled = false;
    }
  }

  function wire() {
    app.addEventListener("click", async (ev) => {
      const passo = ev.target.closest("[data-passo]");
      if (passo && state.db) {
        const id = passo.dataset.passo;
        const cur = state.feitos[id];
        passo.disabled = true;
        try { await state.db.doc(`feitos/${id}`).set({ marcado: !(cur && cur.marcado), em: new Date().toISOString(), confirmado: null }); }
        finally { passo.disabled = false; }
        return;
      }
      const spell = ev.target.closest("[data-feitico]");
      if (spell && state.db) {
        const chosen = selectedSpells();
        const id = spell.dataset.feitico;
        const next = chosen.includes(id) ? chosen.filter((x) => x !== id) : [...chosen, id];
        spell.disabled = true;
        try { await state.db.doc("config/feiticos").set({ selecionados: next, em: new Date().toISOString() }); }
        finally { spell.disabled = false; }
        return;
      }
      const run = ev.target.closest("[data-rodar]");
      if (run) { rodar(run.dataset.rodar); return; }
      const ctl = ev.target.closest("[data-forja]");
      if (ctl) {
        const what = ctl.dataset.forja;
        if (what === "cancelar") { ctl.disabled = true; fetch(`${forja.base}/cancelar`, { method: "POST", headers: HEADERS, body: "{}" }).catch(() => {}); }
        else if (what === "repetir") rodar(forja.status ? forja.status.modo : "plano");
        else { forja.visivel = false; paintForja(); }
        return;
      }
      const ask = ev.target.closest(".pesq");
      if (ask) { enqueue(ask.dataset.q, ask.dataset.origem, ask); return; }
      const item = ev.target.closest("[data-goto-item]");
      if (item) { ev.preventDefault(); goTo("onde", `item-${item.dataset.gotoItem}`); return; }
      const step = ev.target.closest("[data-goto-passo]");
      if (step) { ev.preventDefault(); goTo("passos", `passo-${step.dataset.gotoPasso}`); }
    });
    app.addEventListener("submit", (ev) => {
      if (ev.target.id !== "fila-form") return;
      ev.preventDefault();
      const input = document.getElementById("fila-texto");
      enqueue(input.value, "fila", null).then(() => { input.value = ""; });
    });
  }

  // Servidor local do buildsmith (app/serve.py): mesma interface mínima do banco do Artifact.
  async function localDb() {
    const m = location.pathname.match(/^\/p\/([a-z0-9._-]+)\/([a-z0-9._-]+)\/?/);
    if (!m) return null;
    try {
      const ping = await fetch("/api/ping", { cache: "no-store" });
      const info = ping.ok ? await ping.json() : {};
      if (info.app !== "buildsmith") return null;
      forja.rodar = Boolean(info.rodar);
    } catch (e) { return null; }
    const base = `/api/${m[1]}/${m[2]}`;
    forja.base = base;
    const listeners = [];
    let last = null;
    const publish = (st) => { last = st; listeners.forEach((fn) => fn(st)); };
    const refresh = () => fetch(`${base}/estado`, { cache: "no-store" }).then((r) => r.ok ? r.json() : null).then((st) => { if (st) publish(st); }).catch(() => {});
    setInterval(refresh, 2000);
    refresh();
    const docsOf = (obj) => Object.entries(obj || {}).map(([id, data]) => ({ id, exists: true, data: () => data }));
    const listen = (fn) => { listeners.push(fn); if (last) fn(last); return () => {}; };
    return {
      collection: (name) => ({ onSnapshot: (next) => listen((st) => next({ docs: docsOf(st[name]) })) }),
      doc: (path) => {
        const [col, id] = path.split("/");
        return {
          set: async (data) => {
            const r = await fetch(`${base}/${col}/${id}`, { method: "POST", headers: HEADERS, body: JSON.stringify(data) });
            if (!r.ok) throw new Error(String(r.status));
            publish(await r.json());
          },
          onSnapshot: (next) => listen((st) => { const d = (st[col] || {})[id]; next({ exists: d !== undefined, data: () => d }); }),
        };
      },
    };
  }

  async function connect() {
    const use = window.claude && typeof window.claude.use === "function" ? window.claude.use.bind(window.claude) : null;
    const db = (use ? await use("db").catch(() => null) : null) || await localDb();
    if (!db) { applyState(); return; }
    state.db = db;
    app.querySelectorAll(".fogueira").forEach((b) => { b.hidden = false; });
    if (forja.base) {
      const sub = document.querySelector("#painel-fila h2 small");
      if (sub && forja.rodar) sub.textContent = "o botão Responder fila (no topo) responde agora";
      iniciarForja();
    }
    const fail = () => { /* sem banco: a página segue só leitura */ };
    db.collection("feitos").onSnapshot((snap) => { state.feitos = Object.fromEntries(snap.docs.map((d) => [d.id, d.data()])); applyState(); }, fail);
    db.collection("pedidos").onSnapshot((snap) => { state.pedidos = Object.fromEntries(snap.docs.map((d) => [d.id, d.data()])); applyState(); }, fail);
    db.doc("config/feiticos").onSnapshot((snap) => { state.selecao = snap.exists ? (snap.data().selecionados || []) : null; applyState(); }, fail);
  }

  fetch("plano.json", { cache: "no-store" })
    .then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); })
    .then((p) => { render(p); fallbackIcons(app); wire(); applyState(); connect(); })
    .catch(() => { app.innerHTML = '<p class="error">Não consegui ler o plano.json publicado junto com a página. Rode o /buildsmith:build de novo para republicar.</p>'; });
})();
