(function () {
  // Mapa geral da área (estilo The Division): vista de cima por andar, zonas de fogueira em sequência, chefes, NPCs,
  // todos os itens com ícone, grade, régua, zoom e arrastar, filtros, painel "Rota da área" e "Ver no mapa".
  // Dados: mapas/indice.json + mapas/<area>.json, gerados por script a partir dos arquivos do jogo.
  const AREA_OK = /^m\d\d_\d\d_\d\d_\d\d$/;
  const ICONE_OK = /^icons\/[A-Za-z0-9._-]+$/;
  const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const linkSeguro = (url) => { try { const u = new URL(String(url ?? "")); return u.protocol === "https:" ? u.href : ""; } catch (e) { return ""; } };
  const fmt = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 0 });
  const NS = "http://www.w3.org/2000/svg";
  const MIN_S = 0.6, MAX_S = 40;  // pixels por metro
  const FILTROS = [["zonas", "Zonas"], ["fogueiras", "Fogueiras"], ["chefes", "Chefes"], ["npcs", "NPCs"],
                   ["plano", "Itens do plano"], ["outros", "Outros itens"], ["inimigos", "Inimigos"]];

  // ---- funções puras (testadas no node) ------------------------------------------------------------
  function caixa(pontos) {
    const xs = pontos.map((p) => p[0]), zs = pontos.map((p) => p[1]);
    return { x0: Math.min(...xs), x1: Math.max(...xs), z0: Math.min(...zs), z1: Math.max(...zs) };
  }
  function ajustar(cx, w, h, minimo = 30) {
    const larg = Math.max(cx.x1 - cx.x0, minimo), alt = Math.max(cx.z1 - cx.z0, minimo);
    const s = Math.min(MAX_S, Math.max(MIN_S, Math.min(w / larg, h / alt) * 0.9));
    return { cx: (cx.x0 + cx.x1) / 2, cz: (cx.z0 + cx.z1) / 2, s };
  }
  function regua(s) {
    const alvo = 100 / s;
    return [1, 2, 5, 10, 20, 25, 50, 100, 200, 500].find((m) => m >= alvo * 0.7) || 500;
  }
  const metros = (h) => { const r = Math.round(h); return r === 0 ? "0 m" : `${r > 0 ? "+" : "−"}${fmt.format(Math.abs(r))} m`; };
  const tamanhoIcone = (s) => Math.round(Math.min(34, Math.max(16, 12 + s * 2.2)));
  function estadoAndar(andarPonto, andarSel) {
    if (andarSel === "todos" || andarPonto == null || andarPonto === andarSel) return "cheio";
    return "apagado";
  }
  // Escala sequencial da zona 1 (dourado claro) até a última (brasa escura).
  function corZona(ordem, total) {
    const t = total > 1 ? (ordem - 1) / (total - 1) : 0;
    const h = Math.round(46 - t * 38), sat = Math.round(62 + t * 10), l = Math.round(62 - t * 24);
    return `hsl(${h} ${sat}% ${l}%)`;
  }

  // ---- estado ------------------------------------------------------------------------------------
  const st = { raiz: null, plano: null, indice: null, docs: {}, doc: null, andar: "todos", vista: null, rota: null,
               destaque: null, zonaSel: null, pop: null,
               filtros: { zonas: true, fogueiras: true, chefes: true, npcs: true, plano: true, outros: true, inimigos: false } };

  function carregar(url) {
    return fetch(url, { cache: "no-store" }).then((r) => (r.ok ? r.json() : null)).catch(() => null);
  }
  function doc(area) {
    if (!AREA_OK.test(area)) return Promise.resolve(null);
    if (!st.docs[area]) st.docs[area] = carregar(`mapas/${area}.json`);
    return st.docs[area];
  }
  const zonas = () => (st.doc && st.doc.zonas ? st.doc.zonas.lista : []);
  const corDe = (ordem) => corZona(ordem, zonas().length);
  const nomeZona = (ordem) => { const z = zonas().find((x) => x.ordem === ordem); return z ? `${z.ordem} · ${z.nome}` : "—"; };
  const nomeAndar = (id) => { const a = st.doc.planta.andares.find((x) => x.id === id); return a ? metros(a.altura) : "—"; };

  function montar(raiz, plano) {
    if (st.raiz === raiz) return Promise.resolve();
    st.raiz = raiz;
    st.plano = plano;
    raiz.innerHTML = `<div class="mp">
      <div class="mp-barra">
        <label class="mp-campo">Área <select class="mp-area" aria-label="Área do mapa"></select></label>
        <div class="mp-filtros" role="group" aria-label="Mostrar no mapa">
          ${FILTROS.map(([k, l]) => `<button type="button" class="mp-filtro" data-filtro="${k}" aria-pressed="${st.filtros[k]}">${l}</button>`).join("")}
        </div>
      </div>
      <div class="mp-corpo">
        <div class="mp-tela" tabindex="0" aria-label="Mapa: arraste para mover, roda ou pinça para zoom">
          <svg class="mp-svg" xmlns="${NS}"><g class="mp-mundo"><g class="mp-grade"></g><g class="mp-chao"></g><g class="mp-zonas-chao"></g><g class="mp-paredes"></g><g class="mp-trilha"></g></g><g class="mp-pontos"></g></svg>
          <div class="mp-zoom"><button type="button" data-zoom="mais" aria-label="Aproximar">+</button><button type="button" data-zoom="menos" aria-label="Afastar">&#8722;</button><button type="button" data-zoom="tudo" aria-label="Ver a área inteira">&#9635;</button></div>
          <div class="mp-regua"><span class="mp-regua-barra"></span><span class="mp-regua-txt"></span></div>
          <div class="mp-pop" hidden></div>
          <p class="mp-vazio" hidden></p>
        </div>
        <aside class="mp-lado">
          <h3 class="mp-tit">Andar</h3>
          <ol class="mp-andares" aria-label="Andar"></ol>
          <h3 class="mp-tit">Rota da área</h3>
          <ol class="mp-zonas" aria-label="Zonas de fogueira em ordem"></ol>
          <p class="mp-nota"></p>
        </aside>
      </div>
      <p class="mp-leg"><span class="mp-k mp-k-zonas"></span>zona 1 → última <span class="mp-k mp-k-chefe"></span>chefe <span class="mp-k mp-k-npc"></span>NPC <span class="mp-k mp-k-plano"></span>do plano <span class="mp-k mp-k-outro"></span>item <span class="mp-k mp-k-rota"></span>rota <span class="mp-aviso">rota pelo chão; portas e alavancas não aparecem</span></p>
    </div>`;
    ligar(raiz);
    return carregar("mapas/indice.json").then((indice) => {
      st.indice = Array.isArray(indice) ? indice.filter((a) => AREA_OK.test(a.area)) : [];
      const sel = raiz.querySelector(".mp-area");
      sel.innerHTML = st.indice.map((a) => `<option value="${esc(a.area)}">${esc(a.nome)}${a.itens_plano ? ` (${a.itens_plano})` : ""}</option>`).join("");
      if (!st.indice.length) return vazio("Mapa indisponível. Rode o /buildsmith:build com o DS2 SotFS instalado.");
      return abrirArea(st.indice[0].area);
    });
  }

  function vazio(texto) {
    const el = st.raiz.querySelector(".mp-vazio");
    el.textContent = texto;
    el.hidden = !texto;
  }

  async function abrirArea(area, opcoes = {}) {
    const d = await doc(area);
    if (!d) { vazio("Não consegui ler o mapa desta área."); return; }
    vazio("");
    st.doc = d;
    st.raiz.querySelector(".mp-area").value = area;
    st.rota = opcoes.rota || null;
    st.destaque = opcoes.destaque || null;
    st.zonaSel = null;
    st.pop = null;
    st.raiz.querySelector(".mp-pop").hidden = true;
    const andares = d.planta.andares;
    const contagem = (id) => d.itens.filter((p) => p.andar === id && (p.plano || (st.destaque && p.item_id === st.destaque))).length;
    st.andar = opcoes.andar != null ? opcoes.andar
      : andares.length > 1 ? andares.reduce((m, a) => (contagem(a.id) > contagem(m.id) ? a : m), andares[0]).id : "todos";
    st.raiz.querySelector(".mp-andares").innerHTML = [...andares].sort((a, b) => b.altura - a.altura).map((a) => {
      const n = d.itens.filter((p) => p.andar === a.id && p.plano).length;
      return `<li><button type="button" data-andar="${a.id}">${metros(a.altura)}${n ? `<span class="mp-n">${n}</span>` : ""}</button></li>`;
    }).join("") + '<li><button type="button" data-andar="todos">Todos</button></li>';
    desenharRotaArea();
    desenharChao();
    const tela = st.raiz.querySelector(".mp-tela");
    const pts = opcoes.foco && opcoes.foco.length ? opcoes.foco : todosPontosChao();
    st.vista = ajustar(caixa(pts), tela.clientWidth || 600, tela.clientHeight || 400, opcoes.foco ? 30 : 10);
    atualizar();
  }

  function todosPontosChao() {
    const pts = [];
    st.doc.planta.andares.forEach((a) => a.poligonos.forEach((pol) => pol.forEach((p) => pts.push(p))));
    return pts.length ? pts : st.doc.itens.map((p) => [p.pos[0], p.pos[2]]);
  }

  // Painel "Rota da área": zonas em ordem com o que há em cada uma.
  function desenharRotaArea() {
    const d = st.doc;
    const lista = zonas();
    st.raiz.querySelector(".mp-zonas").innerHTML = lista.map((z) => {
      const itens = d.itens.filter((p) => p.zona === z.ordem && p.plano).length;
      const npcs = (d.npcs || []).filter((n) => n.zona === z.ordem && n.plano);
      const chefes = (d.chefes || []).filter((c) => c.zona === z.ordem);
      const resumo = [itens ? `${itens} ${itens === 1 ? "item" : "itens"} do plano` : "", ...npcs.map((n) => n.nome)].filter(Boolean).join(" · ");
      return `<li><button type="button" class="mp-zona-i" data-zona="${z.ordem}" aria-pressed="${st.zonaSel === z.ordem}">
        <span class="mp-zn" style="background:${corDe(z.ordem)}">${z.ordem}</span>
        <span class="mp-zt">${esc(z.nome)}${resumo ? `<span class="mp-zr">${esc(resumo)}</span>` : ""}${chefes.map((c) => `<span class="mp-zchefe${c.estado === "derrotado" ? " derrotado" : ""}">Chefe: ${esc(c.nome)}</span>`).join("")}</span>
      </button></li>`;
    }).join("") || '<li class="mp-sem">Área sem fogueira.</li>';
    const por = d.zonas ? d.zonas.ordem_por : "nenhuma";
    st.raiz.querySelector(".mp-nota").textContent = por === "inicio" ? "Ordem: distância a pé desde a entrada da área. Portas e atalhos podem mudar o caminho."
      : por === "id" ? "Ordem pelo número da fogueira no jogo." : "";
  }

  // ---- desenho -----------------------------------------------------------------------------------
  const caminho = (pol) => "M" + pol.map((p) => `${p[0]} ${-p[1]}`).join("L") + "Z";

  function desenharChao() {
    const g = st.raiz.querySelector(".mp-chao");
    const andares = [...st.doc.planta.andares].sort((a, b) => a.altura - b.altura);
    const sel = st.andar === "todos" ? null : andares.find((a) => a.id === st.andar);
    const visiveis = [];
    g.innerHTML = andares.map((a) => {
      const classe = !sel ? "mp-andar" : a.id === sel.id ? "mp-andar mp-atual" : a.altura < sel.altura ? "mp-andar mp-baixo" : null;
      if (!classe || !a.poligonos.length) return "";
      if (!sel || a.id === sel.id) visiveis.push(a);
      return `<path class="${classe}" fill-rule="evenodd" vector-effect="non-scaling-stroke" d="${a.poligonos.map(caminho).join("")}"/>`;
    }).join("");
    const zg = st.raiz.querySelector(".mp-zonas-chao");
    zg.innerHTML = st.filtros.zonas ? zonas().map((z) => {
      const polys = visiveis.flatMap((a) => z.poligonos[String(a.id)] || []);
      if (!polys.length) return "";
      const foco = st.zonaSel == null ? "" : st.zonaSel === z.ordem ? " mp-zona-sel" : " mp-zona-fora";
      return `<path class="mp-zona${foco}" fill="${corDe(z.ordem)}" fill-rule="evenodd" d="${polys.map(caminho).join("")}"/>`;
    }).join("") : "";
    st.raiz.querySelector(".mp-paredes").innerHTML = visiveis.map((a) => `<path class="mp-parede${sel ? "" : " mp-parede-todos"}" fill-rule="evenodd" vector-effect="non-scaling-stroke" d="${a.poligonos.map(caminho).join("")}"/>`).join("");
    st.raiz.querySelectorAll("[data-andar]").forEach((b) => b.setAttribute("aria-pressed", String(String(st.andar) === b.dataset.andar)));
    st.raiz.querySelectorAll("[data-zona]").forEach((b) => b.setAttribute("aria-pressed", String(st.zonaSel === Number(b.dataset.zona))));
    const cx = caixa(todosPontosChao());
    const linhas = [];
    for (let x = Math.floor(cx.x0 / 10) * 10; x <= cx.x1 + 10; x += 10) linhas.push(`<line class="${x % 50 ? "mp-g10" : "mp-g50"}" vector-effect="non-scaling-stroke" x1="${x}" y1="${-(cx.z1 + 10)}" x2="${x}" y2="${-(cx.z0 - 10)}"/>`);
    for (let z = Math.floor(cx.z0 / 10) * 10; z <= cx.z1 + 10; z += 10) linhas.push(`<line class="${z % 50 ? "mp-g10" : "mp-g50"}" vector-effect="non-scaling-stroke" x1="${cx.x0 - 10}" y1="${-z}" x2="${cx.x1 + 10}" y2="${-z}"/>`);
    st.raiz.querySelector(".mp-grade").innerHTML = linhas.join("");
    st.raiz.querySelector(".mp-trilha").innerHTML = st.rota ? st.rota.trechos.filter(Boolean).map((t) => `<polyline class="mp-rota" vector-effect="non-scaling-stroke" points="${t.map((p) => `${p[0]},${-p[2]}`).join(" ")}"/>`).join("") : "";
  }

  function paraTela(x, z) {
    const tela = st.raiz.querySelector(".mp-tela");
    const v = st.vista;
    return [(x - v.cx) * v.s + tela.clientWidth / 2, (v.cz - z) * v.s + tela.clientHeight / 2];
  }

  function atualizar() {
    if (!st.doc || !st.vista) return;
    const tela = st.raiz.querySelector(".mp-tela");
    const w = tela.clientWidth, h = tela.clientHeight, v = st.vista;
    st.raiz.querySelector(".mp-mundo").setAttribute("transform", `translate(${w / 2 - v.cx * v.s} ${h / 2 + v.cz * v.s}) scale(${v.s})`);
    st.raiz.querySelector(".mp-grade").classList.toggle("mp-longe", v.s < 2);
    const tam = tamanhoIcone(v.s), nomes = v.s >= 4;
    const partes = [], clips = [];
    const dentro = (sx, sy) => sx > -50 && sy > -50 && sx < w + 50 && sy < h + 50;
    const f1 = (n) => n.toFixed(1);
    const retrato = (k, sx, sy, r, src, classe, titulo, rotulo, dados) => {
      const id = `mp-c${k}`;
      clips.push(`<clipPath id="${id}"><circle cx="${f1(sx)}" cy="${f1(sy)}" r="${f1(r)}"/></clipPath>`);
      const img = src && ICONE_OK.test(src) ? `<image href="${esc(src)}" x="${f1(sx - r)}" y="${f1(sy - r)}" width="${f1(2 * r)}" height="${f1(2 * r)}" clip-path="url(#${id})" preserveAspectRatio="xMidYMin slice"/>`
        : `<text class="mp-ini" x="${f1(sx)}" y="${f1(sy + 4)}">${esc(titulo.trim().replace(/^the\s+/i, "").charAt(0))}</text>`;
      return `<g class="${classe}" ${dados} tabindex="0"><title>${esc(titulo)}</title><circle class="mp-fundo" cx="${f1(sx)}" cy="${f1(sy)}" r="${f1(r)}"/>${img}<circle class="mp-aro" cx="${f1(sx)}" cy="${f1(sy)}" r="${f1(r)}"/>${rotulo ? `<text class="mp-rotulo" x="${f1(sx)}" y="${f1(sy + r + 12)}">${esc(rotulo)}</text>` : ""}</g>`;
    };
    if (st.filtros.inimigos) st.doc.inimigos.forEach((e) => {
      const [sx, sy] = paraTela(e.pos[0], e.pos[2]);
      if (dentro(sx, sy)) partes.push(`<circle class="mp-inimigo ${estadoAndar(e.andar, st.andar)}" cx="${f1(sx)}" cy="${f1(sy)}" r="3"/>`);
    });
    st.doc.itens.forEach((p, i) => {
      const destaque = p.plano || (st.destaque && p.item_id === st.destaque);
      if (destaque ? !st.filtros.plano : !st.filtros.outros) return;
      const [sx, sy] = paraTela(p.pos[0], p.pos[2]);
      if (!dentro(sx, sy)) return;
      const estado = estadoAndar(p.andar, st.andar);
      const t = estado === "cheio" ? (destaque ? tam + 4 : tam) : Math.max(12, tam - 8);
      const img = p.icone && ICONE_OK.test(p.icone) ? `<image href="${esc(p.icone)}" x="${f1(sx - t / 2)}" y="${f1(sy - t / 2)}" width="${t}" height="${t}"/>` : `<rect class="mp-losango" x="${f1(sx - t / 4)}" y="${f1(sy - t / 4)}" width="${t / 2}" height="${t / 2}" transform="rotate(45 ${f1(sx)} ${f1(sy)})"/>`;
      const nome = p.itens[0] ? `${p.itens[0].nome}${p.itens[0].qtd > 1 ? ` ×${p.itens[0].qtd}` : ""}${p.itens.length > 1 ? ` +${p.itens.length - 1}` : ""}` : "";
      partes.push(`<g class="mp-item ${destaque ? "mp-do-plano" : ""} ${estado}" data-tipo="item" data-i="${i}" tabindex="0"><title>${esc(nome)}</title><rect class="mp-moldura" x="${f1(sx - t / 2 - 2)}" y="${f1(sy - t / 2 - 2)}" width="${t + 4}" height="${t + 4}" rx="3"/>${img}${nomes && estado === "cheio" ? `<text class="mp-rotulo" x="${f1(sx)}" y="${f1(sy + t / 2 + 12)}">${esc(nome)}</text>` : ""}</g>`);
    });
    if (st.filtros.fogueiras) st.doc.fogueiras.forEach((f) => {
      const [sx, sy] = paraTela(f.pos[0], f.pos[2]);
      if (!dentro(sx, sy)) return;
      const estado = estadoAndar(f.andar, st.andar), t = estado === "cheio" ? tam + 2 : Math.max(12, tam - 8);
      const badge = f.zona && st.filtros.zonas ? `<circle class="mp-badge" cx="${f1(sx - t / 2)}" cy="${f1(sy - t / 2)}" r="8" fill="${corDe(f.zona)}"/><text class="mp-badge-n" x="${f1(sx - t / 2)}" y="${f1(sy - t / 2 + 3.5)}">${f.zona}</text>` : "";
      partes.push(`<g class="mp-fog ${estado}"><title>${esc(f.zona ? nomeZona(f.zona) : f.nome)}</title><image href="icons/fogueira.png" x="${f1(sx - t / 2)}" y="${f1(sy - t / 2)}" width="${t}" height="${t}"/>${badge}${(nomes || v.s >= 1.5) && estado === "cheio" ? `<text class="mp-rotulo mp-rotulo-fog" x="${f1(sx)}" y="${f1(sy - t / 2 - 5)}">${esc(f.zona ? `${f.zona} · ${f.nome}` : f.nome)}</text>` : ""}</g>`);
    });
    if (st.filtros.npcs) (st.doc.npcs || []).forEach((n, i) => {
      const [sx, sy] = paraTela(n.pos[0], n.pos[2]);
      if (!dentro(sx, sy)) return;
      const estado = estadoAndar(n.andar, st.andar);
      const r = (estado === "cheio" ? tam + (n.plano ? 6 : 2) : Math.max(12, tam - 8)) / 2;
      partes.push(retrato(`n${i}`, sx, sy, r, n.retrato, `mp-npc ${n.plano ? "mp-do-plano" : ""} ${estado}`, n.nome,
        (n.plano || v.s >= 3) && estado === "cheio" ? n.nome : "", `data-tipo="npc" data-i="${i}"`));
    });
    if (st.filtros.chefes) (st.doc.chefes || []).forEach((c, i) => {
      const [sx, sy] = paraTela(c.pos[0], c.pos[2]);
      if (!dentro(sx, sy)) return;
      const estado = estadoAndar(c.andar, st.andar);
      const r = (estado === "cheio" ? tam + 12 : Math.max(14, tam - 4)) / 2;
      partes.push(retrato(`c${i}`, sx, sy, r, c.retrato, `mp-chefe ${c.estado === "derrotado" ? "derrotado" : ""} ${estado}`, c.nome,
        estado === "cheio" ? c.nome : "", `data-tipo="chefe" data-i="${i}"`));
    });
    if (st.rota) st.rota.pontos.forEach((p) => {
      const [sx, sy] = paraTela(p.pos[0], p.pos[2]);
      partes.push(`<g class="mp-passo ${estadoAndar(p.andar, st.andar)}"><title>${esc(`${p.n}. ${p.nome}`)}</title><circle cx="${f1(sx)}" cy="${f1(sy - tam / 2 - 10)}" r="9"/><text x="${f1(sx)}" y="${f1(sy - tam / 2 - 6.5)}">${p.n}</text></g>`);
    });
    st.raiz.querySelector(".mp-pontos").innerHTML = `<defs>${clips.join("")}</defs>${partes.join("")}`;
    const m = regua(v.s);
    st.raiz.querySelector(".mp-regua-barra").style.width = `${Math.round(m * v.s)}px`;
    st.raiz.querySelector(".mp-regua-txt").textContent = `${m} m`;
    if (st.pop) mostrarPop(st.pop.tipo, st.pop.i);
  }

  function mostrarPop(tipo, i) {
    const pop = st.raiz.querySelector(".mp-pop");
    const lista = tipo === "npc" ? st.doc.npcs : tipo === "chefe" ? st.doc.chefes : st.doc.itens;
    const p = (lista || [])[i];
    if (!p) { pop.hidden = true; st.pop = null; return; }
    st.pop = { tipo, i };
    const meta = `<p class="mp-pop-meta">andar ${nomeAndar(p.andar)}${p.zona ? ` · zona ${esc(nomeZona(p.zona))}` : ""}</p>`;
    let corpo;
    if (tipo === "npc") {
      corpo = `<p class="mp-pop-tit">${esc(p.nome)}</p>${p.precisa && p.precisa.length
        ? `<p class="mp-pop-sub">O plano precisa:</p><ul>${p.precisa.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>` : '<p class="mp-pop-sub">Nada do plano.</p>'}`;
    } else if (tipo === "chefe") {
      const link = linkSeguro(p.wiki);
      corpo = `<p class="mp-pop-tit">${esc(p.nome)}</p><p><span class="estado${p.estado === "derrotado" ? " feito" : ""}">${p.estado === "derrotado" ? "Derrotado" : p.estado === "vivo" ? "Vivo" : "—"}</span></p>${link ? `<a href="${esc(link)}" target="_blank" rel="noopener noreferrer">página na wiki</a>` : ""}`;
    } else {
      corpo = `<ul>${p.itens.map((it) => `<li>${esc(it.nome)}${it.qtd > 1 ? ` <span class="mp-qtd">×${it.qtd}</span>` : ""}</li>`).join("")}</ul>${p.item_id ? `<a class="req-link" href="#item-${esc(p.item_id)}" data-goto-item="${esc(p.item_id)}">ver em Onde pegar</a>` : ""}`;
    }
    pop.innerHTML = `<button type="button" class="mp-pop-x" aria-label="Fechar">&#10005;</button>${corpo}${meta}`;
    const [sx, sy] = paraTela(p.pos[0], p.pos[2]);
    const tela = st.raiz.querySelector(".mp-tela");
    pop.style.left = `${Math.min(Math.max(8, sx + 16), tela.clientWidth - 240)}px`;
    pop.style.top = `${Math.min(Math.max(8, sy - 20), tela.clientHeight - 150)}px`;
    pop.hidden = false;
  }

  function fecharPop() {
    st.pop = null;
    st.raiz.querySelector(".mp-pop").hidden = true;
  }

  function focarZona(ordem) {
    if (st.zonaSel === ordem) { st.zonaSel = null; desenharChao(); atualizar(); return; }
    const z = zonas().find((x) => x.ordem === ordem);
    if (!z) return;
    st.zonaSel = ordem;
    const fog = st.doc.fogueiras.find((f) => f.id === z.fogueira);
    if (fog && fog.andar != null) st.andar = fog.andar;
    const pts = Object.values(z.poligonos).flat().flat();
    const tela = st.raiz.querySelector(".mp-tela");
    if (pts.length) st.vista = ajustar(caixa(pts), tela.clientWidth, tela.clientHeight, 30);
    desenharChao();
    atualizar();
  }

  // ---- interação ---------------------------------------------------------------------------------
  function zoom(fator, ox, oy) {
    const tela = st.raiz.querySelector(".mp-tela");
    const v = st.vista;
    const w = tela.clientWidth, h = tela.clientHeight;
    ox = ox ?? w / 2; oy = oy ?? h / 2;
    const mx = v.cx + (ox - w / 2) / v.s, mz = v.cz - (oy - h / 2) / v.s;
    const s = Math.min(MAX_S, Math.max(MIN_S, v.s * fator));
    st.vista = { s, cx: mx - (ox - w / 2) / s, cz: mz + (oy - h / 2) / s };
    atualizar();
  }

  function mover(dx, dz) {
    st.vista = { ...st.vista, cx: st.vista.cx + dx, cz: st.vista.cz + dz };
    atualizar();
  }

  function ligar(raiz) {
    const tela = raiz.querySelector(".mp-tela");
    const toques = new Map();
    let arrasto = null, pinca = null, moveu = false;
    tela.addEventListener("wheel", (ev) => {
      ev.preventDefault();
      const r = tela.getBoundingClientRect();
      zoom(ev.deltaY < 0 ? 1.2 : 1 / 1.2, ev.clientX - r.left, ev.clientY - r.top);
    }, { passive: false });
    tela.addEventListener("pointerdown", (ev) => {
      if (ev.target.closest(".mp-zoom, .mp-pop")) return;
      toques.set(ev.pointerId, [ev.clientX, ev.clientY]);
      tela.setPointerCapture(ev.pointerId);
      moveu = false;
      if (toques.size === 1) arrasto = { x: ev.clientX, y: ev.clientY, v: { ...st.vista } };
      if (toques.size === 2) {
        const [a, b] = [...toques.values()];
        pinca = { d: Math.hypot(a[0] - b[0], a[1] - b[1]), s: st.vista.s };
        arrasto = null;
      }
    });
    tela.addEventListener("pointermove", (ev) => {
      if (!toques.has(ev.pointerId) || !st.vista) return;
      toques.set(ev.pointerId, [ev.clientX, ev.clientY]);
      if (pinca && toques.size === 2) {
        const [a, b] = [...toques.values()];
        const r = tela.getBoundingClientRect();
        zoom((pinca.s * Math.hypot(a[0] - b[0], a[1] - b[1]) / pinca.d) / st.vista.s, (a[0] + b[0]) / 2 - r.left, (a[1] + b[1]) / 2 - r.top);
        moveu = true;
      } else if (arrasto) {
        const dx = ev.clientX - arrasto.x, dy = ev.clientY - arrasto.y;
        if (Math.abs(dx) + Math.abs(dy) > 3) moveu = true;
        st.vista = { ...arrasto.v, cx: arrasto.v.cx - dx / arrasto.v.s, cz: arrasto.v.cz + dy / arrasto.v.s };
        atualizar();
      }
    });
    const soltar = (ev) => {
      toques.delete(ev.pointerId);
      if (toques.size < 2) pinca = null;
      if (!toques.size) arrasto = null;
    };
    tela.addEventListener("pointerup", (ev) => {
      soltar(ev);
      if (moveu) return;
      const alvo = document.elementFromPoint(ev.clientX, ev.clientY);
      const marca = alvo && alvo.closest("[data-tipo]");
      if (marca) mostrarPop(marca.dataset.tipo, Number(marca.dataset.i));
      else if (!alvo || !alvo.closest(".mp-pop")) fecharPop();
    });
    tela.addEventListener("pointercancel", soltar);
    tela.addEventListener("keydown", (ev) => {
      const passo = 40 / (st.vista ? st.vista.s : 1);
      const acoes = { "+": () => zoom(1.25), "=": () => zoom(1.25), "-": () => zoom(0.8), ArrowLeft: () => mover(-passo, 0),
                      ArrowRight: () => mover(passo, 0), ArrowUp: () => mover(0, passo), ArrowDown: () => mover(0, -passo), Escape: fecharPop };
      if (acoes[ev.key]) { ev.preventDefault(); acoes[ev.key](); }
      const marca = ev.target.closest && ev.target.closest("[data-tipo]");
      if ((ev.key === "Enter" || ev.key === " ") && marca) { ev.preventDefault(); mostrarPop(marca.dataset.tipo, Number(marca.dataset.i)); }
    });
    raiz.addEventListener("click", (ev) => {
      const z = ev.target.closest("[data-zoom]");
      if (z) {
        if (z.dataset.zoom === "tudo") { st.vista = ajustar(caixa(todosPontosChao()), tela.clientWidth, tela.clientHeight, 10); atualizar(); }
        else zoom(z.dataset.zoom === "mais" ? 1.4 : 1 / 1.4);
        return;
      }
      const a = ev.target.closest("[data-andar]");
      if (a) { st.andar = a.dataset.andar === "todos" ? "todos" : Number(a.dataset.andar); desenharChao(); atualizar(); return; }
      const zona = ev.target.closest("[data-zona]");
      if (zona) { focarZona(Number(zona.dataset.zona)); return; }
      const f = ev.target.closest("[data-filtro]");
      if (f) {
        st.filtros[f.dataset.filtro] = !st.filtros[f.dataset.filtro];
        f.setAttribute("aria-pressed", String(st.filtros[f.dataset.filtro]));
        if (f.dataset.filtro === "zonas") desenharChao();
        atualizar();
        return;
      }
      if (ev.target.closest(".mp-pop-x")) fecharPop();
    });
    raiz.querySelector(".mp-area").addEventListener("change", (ev) => abrirArea(ev.target.value));
    if (window.ResizeObserver) new ResizeObserver(() => atualizar()).observe(tela);
  }

  // "Ver no mapa": rota de uma fonte/passo, ou todos os pontos de um item do plano.
  async function ver(alvo) {
    if (!st.raiz || !st.indice) return;
    if (alvo.mapa && AREA_OK.test(alvo.mapa.area)) {
      const r = alvo.mapa;
      const foco = r.pontos.map((p) => [p.pos[0], p.pos[2]]).concat(...r.trechos.filter(Boolean).map((t) => t.map((p) => [p[0], p[2]])));
      await abrirArea(r.area, { rota: r, foco, andar: r.pontos.length ? r.pontos[r.pontos.length - 1].andar : undefined });
      return;
    }
    if (alvo.item_id) {
      for (const a of st.indice) {
        const d = await doc(a.area);
        const pts = d ? d.itens.filter((p) => p.item_id === alvo.item_id) : [];
        if (pts.length) {
          await abrirArea(a.area, { destaque: alvo.item_id, foco: pts.map((p) => [p.pos[0], p.pos[2]]), andar: pts[0].andar });
          return;
        }
      }
      vazio("Este item não aparece no chão das áreas do mapa (pode ser de loja, troca ou drop).");
    }
  }

  window.buildsmithMapa = { montar, ver, _teste: { caixa, ajustar, regua, tamanhoIcone, estadoAndar, corZona } };
})();
