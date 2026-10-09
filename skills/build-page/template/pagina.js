(function () {
  const STATS = ["VGR", "END", "VIT", "ATN", "STR", "DEX", "INT", "FTH", "ADP"];
  const GRUPO = { equipar: "Equipar", explorar: "Explorar", chefe: "Chefe", troca: "Troca de alma", compra: "Compra",
                  upgrade: "Upgrade", farm: "Farm", nivel: "Nível" };
  const ORDEM_GRUPOS = Object.keys(GRUPO);
  const ACESSO = { agora: ["Agora", "feito"], em_breve: ["Em breve", ""], tarde: ["Tarde", "apagado"] };
  const DESTAQUE = { mais_cedo: "Mais cedo", mais_rentavel: "Mais rentável" };
  const ESTADO_FEITICO = { equipado: "Equipado", tem: "Tem", sugerido: "Sugerido" };
  const SECOES = [
    ["Plano", [["agora", "Agora"], ["passos", "Passos"], ["fases", "Fases"]]],
    ["Coletar", [["onde", "Onde pegar"], ["fila", "Fila"]]],
    ["Combate", [["dano", "Dano"], ["feiticos", "Feitiços"], ["atributos", "Atributos"]]],
    ["Registro", [["ficha", "Ficha"], ["progresso", "Progresso"], ["builds", "Builds"], ["fontes", "Fontes"]]],
  ];
  const state = { db: null, plano: null, feitos: {}, pedidos: {}, selecao: null };
  const ui = { secao: null, passo: null, item: null, fonte: {} };
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
      const swap = () => { const s = document.createElement("span"); s.className = img.classList.contains("ni-ic") ? "ni-ic" : "ini"; s.setAttribute("aria-hidden", "true"); s.textContent = img.dataset.ini; img.replaceWith(s); };
      if (img.complete && img.naturalWidth === 0) swap(); else img.addEventListener("error", swap);
    });
  }

  function node(n) {
    const inner = `${icon(n.icone, n.nome)}<span class="nm">${esc(n.nome)}</span>${n.sub ? `<span class="sub">${esc(n.sub)}</span>` : ""}`;
    const solo = n.sub ? "" : " solo";
    return n.link ? ext(n.link, inner, `node${solo}`) : `<span class="node${solo}">${inner}</span>`;
  }
  const flow = (nodes) => (nodes && nodes.length) ? `<div class="flow">${nodes.map(node).join('<span class="arrow" aria-hidden="true">&#10142;</span>')}</div>` : "";
  // Nó em linha (lista + detalhe): ícone de 20px ou inicial, nome, legenda.
  function noInline(n, semLink) {
    const ic = localIcon(n.icone) ? `<img class="ic ni-ic" src="${esc(n.icone)}" alt="" data-ini="${esc(letter(n.nome))}">` : `<span class="ni-ic" aria-hidden="true">${esc(letter(n.nome))}</span>`;
    const inner = `${ic}<span class="ni-nm">${esc(n.nome)}</span>${n.sub ? `<span class="ni-sub">${esc(n.sub)}</span>` : ""}`;
    return n.link && !semLink ? ext(n.link, inner, "ni") : `<span class="ni ni-sem">${inner}</span>`;
  }
  const fluxoInline = (nodes, semLink) => `<span class="fi">${(nodes || []).map((n, i) => `<span class="fi-passo">${i ? '<span class="arrow" aria-hidden="true">&#10142;</span>' : ""}${noInline(n, semLink)}</span>`).join("")}</span>`;
  const selo = (text, extra) => `<span class="estado${extra ? " " + extra : ""}">${esc(text)}</span>`;

  function rows(lines, heads) {
    if (!lines || !lines.length) return "";
    const body = lines.map((l) => `<tr><td>${esc(l.dado)}</td><td>${esc(l.agora)}</td><td>${esc(l.depois)}</td><td class="${cls(l.sinal)}">${esc(l.efeito)}</td></tr>`).join("");
    return `<div class="tw"><table><thead><tr>${heads.map((h) => `<th>${h}</th>`).join("")}</tr></thead><tbody>${body}</tbody></table></div>`;
  }

  function grid(heads, lines, right = []) {
    const th = heads.map((h, i) => `<th${right.includes(i) ? ' class="r"' : ""}>${h}</th>`).join("");
    const body = lines.map((cells) => `<tr>${cells.map((c, i) => `<td${right.includes(i) ? ' class="r"' : ""}>${c}</td>`).join("")}</tr>`).join("");
    return `<div class="tw"><table><thead><tr>${th}</tr></thead><tbody>${body}</tbody></table></div>`;
  }

  // ---- Cabeçalho ----------------------------------------------------------
  function topo(p) {
    const c = p.personagem;
    return `<header class="topo">
      <div class="topo-pers">
        <div class="retrato" id="retrato" aria-hidden="true">${retratoEquipamento(c.equipado)}</div>
        <div class="topo-id"><p class="meta">${esc(p.jogo)} · atualizado ${when(p.gerado_em)}</p><h1>${esc(c.name)}</h1>
          <button class="trocar" type="button" id="trocar" hidden>Trocar personagem</button></div>
      </div>
      <div class="topo-meta"><span>Nível <b>${fmt.format(c.level)}</b></span><span>Almas <b>${fmt.format(c.souls)}</b></span><span>Soul memory <b>${fmt.format(c.soul_memory)}</b></span>
        <span class="legend"><span class="l-pos">ganho</span><span class="l-neg">perda / falta</span><span class="l-link">link da wiki</span></span></div>
      <div class="acoes" id="forja-acoes" hidden>
        <button class="acao" type="button" data-rodar="plano"><img src="icons/fogueira.png" alt="">Atualizar plano</button>
        <button class="acao" type="button" data-rodar="fila"><img src="icons/fogueira.png" alt="">Responder fila<span class="count" id="forja-fila" hidden></span></button>
      </div>
    </header>
    <div class="forja" id="forja" hidden></div>`;
  }

  // Retrato sem foto: mosaico com os ícones do equipamento (cabeça, peito, mão direita, mão esquerda).
  const ORDEM_RETRATO = [/^cabe/i, /^peito/i, /^R1/, /^L1/];
  function retratoEquipamento(equipado) {
    const lista = Array.isArray(equipado) ? equipado : [];
    const escolhidos = ORDEM_RETRATO.map((re) => lista.find((n) => re.test(String(n.sub || "")))).filter(Boolean);
    const pecas = (escolhidos.length ? escolhidos : lista).slice(0, 4);
    if (!pecas.length) return '<span class="retrato-vazio">Foto</span>';
    return `<span class="mosaico m${pecas.length}">${pecas.map((n) => localIcon(n.icone) ? `<img class="ic" src="${esc(n.icone)}" alt="" data-ini="${esc(letter(n.nome))}">` : initial(n.nome)).join("")}</span>`;
  }

  function menu(p) {
    const counts = {
      passos: p.passos.length, fases: p.fases.length, onde: p.itens.length, dano: (p.dano || []).length || null,
      feiticos: p.feiticos ? p.feiticos.lista.length : null, progresso: p.progresso ? p.progresso.chefes.filter((c) => c.estado === "derrotado").length : null,
      builds: p.comparacao.length, fontes: p.fontes.length, ficha: p.mudancas.length || null,
    };
    return `<nav class="menu" aria-label="Seções">${SECOES.map(([g, itens]) => `<div class="menu-g"><div class="menu-gt">${g}</div>
      ${itens.filter(([id]) => id !== "agora" || p.agora).map(([id, l]) => `<button class="menu-i" type="button" data-secao="${id}">${l}${counts[id] ? `<span class="count">${counts[id]}</span>` : id === "fila" ? '<span class="count" id="menu-fila" hidden></span>' : ""}</button>`).join("")}
    </div>`).join("")}</nav>`;
  }

  // ---- Lista + detalhe ------------------------------------------------------
  function mestreDetalhe(tipo, itens, linha, detalhe, largura) {
    return `<div class="md" style="grid-template-columns:${largura} minmax(0,1fr)">
      <ul class="md-lista">${itens.map((it) => `<li><div class="md-i" role="button" tabindex="0" data-md="${tipo}" data-md-id="${esc(it.id)}">${linha(it)}</div></li>`).join("")}</ul>
      <div class="md-det">${itens.map((it) => `<div class="md-pane" data-md-pane="${tipo}" data-md-id="${esc(it.id)}" hidden>${detalhe(it)}</div>`).join("")}</div>
    </div>`;
  }

  function secaoAgora(p) {
    const a = p.agora;
    if (!a) return '<section><h2>Agora</h2><p class="empty">Este plano não tem ações imediatas.</p></section>';
    const byId = Object.fromEntries(p.passos.map((s) => [s.id, s]));
    const acoes = a.acoes.map((id) => byId[id]).filter(Boolean).map((s) => `<li class="agora2-i">
      ${fogueira("data-passo", s.id, "Marcar como feito")}
      <div><a class="agora2-t" href="#passo-${esc(s.id)}" data-goto-passo="${esc(s.id)}">${esc(s.titulo)}</a>${fluxoInline(s.fluxo)}</div>
    </li>`).join("");
    const faltam = (a.faltam || []).length ? `<span>Faltam:</span>${fluxoInline(a.faltam)}` : "";
    return `<section class="agora2 grande" aria-label="Próximas ações"><h2>Agora</h2><ol>${acoes}</ol>
      <div class="agora2-res">${typeof a.almas === "number" ? `<span>Almas pra essas ações: <span class="${a.almas > 0 ? "neg" : ""}">${fmt.format(a.almas)}</span></span>` : ""}${faltam}</div>
    </section>`;
  }

  function secaoPassos(p) {
    if (!p.passos.length) return '<section><h2>Próximos passos</h2><p class="empty">Nenhum passo pendente.</p></section>';
    const ordenados = [...p.passos].sort((a, b) => ORDEM_GRUPOS.indexOf(a.tipo) - ORDEM_GRUPOS.indexOf(b.tipo));
    const numero = Object.fromEntries(ordenados.map((s, i) => [s.id, i + 1]));
    return `<section><h2>Próximos passos<small id="passos-feitos"></small></h2>${mestreDetalhe("passo", ordenados,
      (s) => `<div class="md-l1"><span class="md-fog">${fogueira("data-passo", s.id, "Marcar como feito")}</span><span class="step-no">${numero[s.id]}</span><span class="md-t">${esc(s.titulo)}</span></div>
        <div class="md-l2"><span class="label">${esc(GRUPO[s.tipo] || s.tipo)}</span><span class="confirmado" data-confirma="${esc(s.id)}"></span></div>`,
      (s) => `<div class="det-head" id="passo-${esc(s.id)}"><span class="det-tit">${esc(s.titulo)}</span>${selo(GRUPO[s.tipo] || s.tipo)}</div>
        ${flow(s.fluxo)}
        <div class="mapa-slot" data-mapa-passo="${esc(s.id)}" hidden></div>
        ${rows(s.dados, ["Dado", "Agora", "Depois", "Efeito"])}`, "21rem")}</section>`;
  }

  function maisCedo(it) {
    return (it.fontes || []).find((f) => (f.destaques || []).includes("mais_cedo")) || (it.fontes || [])[0];
  }

  function secaoOnde(p) {
    if (!p.itens.length) return '<section><h2>Onde pegar</h2><p class="empty">Nenhum item pendente.</p></section>';
    return `<section><h2>Onde pegar<small>mais cedo e mais rentável a partir de onde você está</small></h2>${mestreDetalhe("item", p.itens,
      (it) => {
        const m = maisCedo(it);
        const a = m ? ACESSO[m.acesso] || [m.acesso, ""] : null;
        return `<div class="md-l1">${noInline(it.item, true)}</div>
          <div class="md-l2">${a ? selo(a[0], a[1]) : ""}<span>${esc(m ? m.rendimento || "" : "")}</span><span class="md-fim">${(it.fontes || []).length} fontes</span></div>`;
      },
      (it) => `<div class="det-head" id="item-${esc(it.id)}">${node({ ...it.item, sub: `${(it.fontes || []).length} fontes` })}${it.fonte ? ext(it.fonte, "fonte na wiki", "muted") : ""}</div>
        <div class="mapa-slot" data-mapa-item="${esc(it.id)}" hidden></div>
        <ol class="fontes-v">${(it.fontes || []).map((f, i) => {
          const a = ACESSO[f.acesso] || [f.acesso, ""];
          return `<li class="fonte-v sel" role="button" tabindex="0" data-fonte-item="${esc(it.id)}" data-fonte="${i}">
            <div class="fonte-top"><span class="step-no">${i + 1}</span>${selo(a[0], a[1])}${(f.destaques || []).map((d) => selo(DESTAQUE[d] || d, "destaque")).join("")}<span class="fonte-rend">${esc(f.rendimento || "—")}</span></div>
            ${fluxoInline(f.fluxo)}
            <div class="fonte-req"><span class="label">Requisito</span>${requisito(f.requisito, it.item.nome)}</div>
          </li>`;
        }).join("")}</ol>
        ${rows(it.dados, ["Dado", "Agora", "Com o item", "Efeito"])}`, "18rem")}</section>`;
  }

  function secaoDano(p) {
    const list = p.dano || [];
    if (!list.length) return '<section><h2>Dano</h2><p class="empty">Este plano não tem cálculo de dano.</p></section>';
    const nums = list.flatMap((d) => [d.agora, d.depois]).filter((v) => typeof v === "number");
    const max = Math.max(1, ...nums) * 1.08;
    const pc = (v) => `${(v / max * 100).toFixed(2)}%`;
    const grupos = [];
    list.forEach((d) => {
      const g = grupos.find((x) => x.nome === d.arma.nome);
      if (g) g.linhas.push(d); else grupos.push({ nome: d.arma.nome, arma: d.arma, linhas: [d] });
    });
    return `<section><h2>Dano<small>AR pelas regras do jogo</small></h2><div class="dano">${grupos.map((g) => `<div class="dano-arma">
      <div class="det-head">${node(g.arma)}</div>
      ${g.linhas.map((d) => {
        const num = typeof d.agora === "number" && typeof d.depois === "number";
        const diff = num ? d.depois - d.agora : 0;
        return `<div class="dano-l">
          <span class="dano-rot">${esc(d.detalhe || "—")}</span>
          <div class="dano-bar" role="img" aria-label="${num ? `AR ${d.agora} para ${d.depois}` : "sem cálculo"}">${num ? `<div class="now" style="width:${pc(Math.min(d.agora, d.depois))}"></div>${diff > 0 ? `<div class="ganho" style="left:${pc(d.agora)};width:${pc(diff)}"></div>` : ""}` : ""}</div>
          <span class="dano-val">${num ? `${fmt.format(d.agora)} → <span class="${diff > 0 ? "pos" : diff < 0 ? "neg" : ""}">${fmt.format(d.depois)} (${diff > 0 ? "+" : diff < 0 ? "−" : ""}${fmt.format(Math.abs(diff))})</span>` : "—"}</span>
          ${(d.por_causa || []).length ? `<div class="dano-causa"><span class="label">Por causa de</span>${fluxoInline(d.por_causa)}</div>` : ""}
        </div>`;
      }).join("")}
    </div>`).join("")}</div></section>`;
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

  function builds(p) {
    const list = p.comparacao.map((b) => `<div class="block">
      <div class="block-head"><span class="step-title">${b.link ? ext(b.link, esc(b.build)) : esc(b.build)}</span></div>
      ${rows(b.dados, ["Dado", "Você", "Build", "Diferença"])}
      ${b.ajuste && b.ajuste.length ? `<span class="label">Ajuste sugerido</span>${flow(b.ajuste)}` : ""}
    </div>`).join("");
    return `<section><h2>Outras builds</h2>${list ? `<div class="blocks">${list}</div>` : '<p class="empty">Nenhuma comparação ainda.</p>'}</section>`;
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
    return `<section><h2>Fila de pesquisa<small id="fila-sub">${forja.rodar ? "o botão Responder fila (no topo) responde agora" : "respondida no próximo /buildsmith:build"}</small></h2>
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
  const KEY = "buildsmith-secao";

  function render(p) {
    state.plano = p;
    const secoes = {
      agora: secaoAgora(p), passos: secaoPassos(p), fases: phases(p), onde: secaoOnde(p), fila: queue(),
      dano: secaoDano(p), feiticos: spells(p), atributos: stats(p), ficha: sheet(p) + changes(p), progresso: progress(p),
      builds: builds(p), fontes: sources(p),
    };
    if (!p.agora) delete secoes.agora;
    app.innerHTML = topo(p)
      + `<div class="corpo">${menu(p)}<div class="conteudo" id="conteudo">${Object.entries(secoes).map(([id, html]) => `<div class="secao" data-pane="${id}" hidden>${html}</div>`).join("")}</div></div>`;
    let saved = null;
    try { saved = localStorage.getItem(KEY); } catch (e) { saved = null; }
    const pedida = [location.hash.slice(1), saved, p.agora ? "agora" : "passos"].find((id) => id in secoes);
    ui.passo = ui.passo && p.passos.some((s) => s.id === ui.passo) ? ui.passo : (p.passos[0] || {}).id;
    ui.item = ui.item && p.itens.some((it) => it.id === ui.item) ? ui.item : (p.itens[0] || {}).id;
    mostrar(pedida);
    escolher("passo", ui.passo);
    escolher("item", ui.item);
    p.itens.forEach((it) => marcarFonte(it.id, ui.fonte[it.id] ?? Math.max(0, (it.fontes || []).findIndex((f) => (f.destaques || []).includes("mais_cedo")))));
    if (typeof window.buildsmithMapa === "function") window.buildsmithMapa(app, p);
  }

  function mostrar(id) {
    const panes = [...app.querySelectorAll("[data-pane]")];
    if (!panes.some((el) => el.dataset.pane === id)) id = panes.length ? panes[0].dataset.pane : id;
    ui.secao = id;
    panes.forEach((el) => { el.hidden = el.dataset.pane !== id; });
    app.querySelectorAll(".menu-i").forEach((b) => { if (b.dataset.secao === id) b.setAttribute("aria-current", "page"); else b.removeAttribute("aria-current"); });
    try { localStorage.setItem(KEY, id); } catch (e) { /* armazenamento bloqueado: só não lembra a seção */ }
    if (history.replaceState) history.replaceState(null, "", `#${id}`);
  }

  function escolher(tipo, id) {
    if (!id) return;
    if (tipo === "passo") ui.passo = id; else ui.item = id;
    app.querySelectorAll(`[data-md="${tipo}"]`).forEach((el) => { if (el.dataset.mdId === id) el.setAttribute("aria-current", "true"); else el.removeAttribute("aria-current"); });
    app.querySelectorAll(`[data-md-pane="${tipo}"]`).forEach((el) => { el.hidden = el.dataset.mdId !== id; });
  }

  function marcarFonte(itemId, idx) {
    ui.fonte[itemId] = idx;
    app.querySelectorAll(`[data-fonte-item="${CSS.escape(itemId)}"]`).forEach((el) => {
      if (Number(el.dataset.fonte) === idx) el.setAttribute("aria-current", "true"); else el.removeAttribute("aria-current");
    });
    if (typeof window.buildsmithMapaFonte === "function") window.buildsmithMapaFonte(app, state.plano, itemId, idx);
  }

  function goTo(secao, tipo, id) {
    mostrar(secao);
    if (tipo) escolher(tipo, id);
    const alvo = app.querySelector(".conteudo");
    if (alvo && window.matchMedia("(max-width: 760px)").matches) alvo.scrollIntoView({ block: "start" });
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
    const feitosEl = document.getElementById("passos-feitos");
    if (feitosEl && state.plano) feitosEl.textContent = `${state.plano.passos.filter((s) => state.feitos[s.id] && state.feitos[s.id].marcado).length} de ${state.plano.passos.length} feitos`;
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
    const open = list.filter((ped) => ped.estado !== "respondido").length;
    const contador = document.getElementById("menu-fila");
    if (contador) { contador.hidden = !open; contador.textContent = String(open); }
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
    const outro = !daqui(st) && st.alvo ? st.alvo.personagem.replace(/-/g, " ") : "";
    const titulo = outro && rodando ? `Rodando para ${outro}`
      : rodando ? nomes[0]
      : st.estado === "ok" ? (outro ? `${nomes[1]}: ${outro}` : nomes[1])
      : st.estado === "cancelado" ? "Cancelado" : "A forja apagou";
    box.querySelector(".forja-titulo").textContent = titulo;
    box.querySelector(".forja-etapa").textContent = rodando && atual >= 0 ? `${st.etapas[atual].nome} · ${atual + 1} de ${st.etapas.length}` : "";
    paintClock();
    if (box.dataset.estado !== st.estado) {
      box.dataset.estado = st.estado;
      const abrir = st.estado === "ok" && outro ? `<a class="pesq" href="/p/${esc(st.alvo.jogo)}/${esc(st.alvo.personagem)}/">Abrir página</a>` : "";
      box.querySelector(".forja-botoes").innerHTML = rodando ? '<button class="pesq" type="button" data-forja="cancelar">Cancelar</button>'
        : `${abrir}${st.estado === "ok" ? "" : '<button class="pesq" type="button" data-forja="repetir">Tentar de novo</button>'}<button class="pesq" type="button" data-forja="fechar">Fechar</button>`;
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

  // base: /api/<jogo>/<personagem> do personagem que vai rodar (o desta página ou outro da seleção).
  async function rodar(modo, base = forja.base) {
    if (!base) return;
    Object.assign(forja, { visivel: true, linhas: [], desde: -1, fechou: false });
    const box = document.getElementById("forja");
    if (box) box.innerHTML = "";
    try {
      const r = await fetch(`${base}/rodar`, { method: "POST", headers: HEADERS, body: JSON.stringify({ modo }) });
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
      if (typeof window.buildsmithSelecao === "function") window.buildsmithSelecao.atualizar();
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
        ev.stopPropagation();
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
      const ask = ev.target.closest(".pesq[data-q]");
      if (ask) { enqueue(ask.dataset.q, ask.dataset.origem, ask); return; }
      const sec = ev.target.closest("[data-secao]");
      if (sec) { mostrar(sec.dataset.secao); return; }
      const item = ev.target.closest("[data-goto-item]");
      if (item) { ev.preventDefault(); goTo("onde", "item", item.dataset.gotoItem); return; }
      const step = ev.target.closest("[data-goto-passo]");
      if (step) { ev.preventDefault(); goTo("passos", "passo", step.dataset.gotoPasso); return; }
      if (ev.target.closest("a, button, input")) return;
      const fonte = ev.target.closest("[data-fonte-item]");
      if (fonte) { marcarFonte(fonte.dataset.fonteItem, Number(fonte.dataset.fonte)); return; }
      const md = ev.target.closest("[data-md]");
      if (md) {
        escolher(md.dataset.md, md.dataset.mdId);
        // Lista e detalhe empilhados (tela estreita): leva até o detalhe escolhido.
        const pane = window.matchMedia("(max-width: 1180px)").matches && md.closest(".md").querySelector(".md-det");
        if (pane) pane.scrollIntoView({ block: "start" });
      }
    });
    app.addEventListener("keydown", (ev) => {
      if (ev.key !== "Enter" && ev.key !== " ") return;
      const alvo = ev.target.closest("[data-md], [data-fonte-item]");
      if (!alvo || ev.target !== alvo) return;
      ev.preventDefault();
      alvo.click();
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
    forja.jogo = m[1];
    forja.personagem = m[2];
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
      const sub = document.getElementById("fila-sub");
      if (sub && forja.rodar) sub.textContent = "o botão Responder fila (no topo) responde agora";
      iniciarForja();
      if (typeof window.buildsmithSelecao === "function") window.buildsmithSelecao({ app, forja, rodar, esc, fmt, letter, HEADERS });
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
