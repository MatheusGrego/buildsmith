(function () {
  // Mapa geral da área (estilo The Division): vista de cima por andar, zonas de fogueira em sequência, chefes, NPCs,
  // todos os itens com ícone, grade, régua, zoom e arrastar, filtros, painel "Rota da área" e "Ver no mapa".
  // Dados: mapas/indice.json + mapas/<area>.json, gerados por script a partir dos arquivos do jogo.
  // Pelo servidor local (/p/<jogo>/<personagem>/): você no mapa (posição do save), "Rota até aqui" pelo chão e a vista
  // 3D (iso.js) com o cenário do jogo, com os mesmos marcadores, filtros, andares e rota projetados por cima.
  const AREA_OK = /^m\d\d_\d\d_\d\d_\d\d$/;
  const ICONE_OK = /^icons\/[A-Za-z0-9._-]+$/;
  const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const linkSeguro = (url) => { try { const u = new URL(String(url ?? "")); return u.protocol === "https:" ? u.href : ""; } catch (e) { return ""; } };
  const fmt = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 0 });
  const NS = "http://www.w3.org/2000/svg";
  const PAG = typeof location === "undefined" ? null : location.pathname.match(/^\/p\/(ds2)\/([a-z0-9._-]+)\/?/);
  const API = PAG ? `/api/${PAG[1]}` : null;
  const POLL_MS = 5000;
  const MIN_S = 0.6, MAX_S = 40;  // pixels por metro
  const FILTROS = [["zonas", "Zonas"], ["fogueiras", "Fogueiras"], ["chefes", "Chefes"], ["npcs", "NPCs"],
                   ["plano", "Itens do plano"], ["outros", "Outros itens"], ["inimigos", "Inimigos"]];
  const Iso = () => (typeof window !== "undefined" && window.MapaIsometrico) || null;

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
  // Andar de uma altura: o que contém a altura (com 1 m de folga), senão o de altura mais perto.
  function andarDe(andares, y) {
    if (!andares || !andares.length) return null;
    const a = andares.find((x) => y >= x.min - 1 && y <= x.max + 1);
    return (a || andares.reduce((m, x) => (Math.abs(x.altura - y) < Math.abs(m.altura - y) ? x : m), andares[0])).id;
  }
  // Escala sequencial da zona 1 (dourado claro) até a última (brasa escura). As paradas da rota usam a mesma escala.
  function corZona(ordem, total) {
    const t = total > 1 ? (ordem - 1) / (total - 1) : 0;
    const h = Math.round(46 - t * 38), sat = Math.round(62 + t * 10), l = Math.round(62 - t * 24);
    return `hsl(${h} ${sat}% ${l}%)`;
  }
  // Número da parada legível em cima da cor dela: escuro nas claras (começo), claro nas escuras (fim).
  const tintaParada = (ordem, total) => (total > 1 && (ordem - 1) / (total - 1) > 0.5 ? "#fff4e6" : "#1a1206");
  // Pino de parada com a ponta em (x, y): bolha de raio 10 com o centro 18 px acima.
  const pino = (x, y) => `M${x.toFixed(1)} ${y.toFixed(1)}L${(x - 7.5).toFixed(1)} ${(y - 11.4).toFixed(1)}A10 10 0 1 1 ${(x + 7.5).toFixed(1)} ${(y - 11.4).toFixed(1)}Z`;
  // Trechos da rota na tela (3D): partes contíguas de pontos visíveis (fora do corte de interior), em pixels.
  function trechosTela(pontos, projetar) {
    const out = [];
    let atual = [];
    for (const p of pontos) {
      const [sx, sy, vis, extra] = projetar(p);
      if (!vis || (extra && extra.cortado)) { if (atual.length > 1) out.push(atual); atual = []; continue; }
      atual.push([sx, sy]);
    }
    if (atual.length > 1) out.push(atual);
    return out;
  }

  // ---- estado ------------------------------------------------------------------------------------
  const st = { raiz: null, plano: null, indice: null, docs: {}, doc: null, andar: "todos", vista: null, rota: null,
               destaque: null, zonaSel: null, pop: null, jogador: null, tipoSel: null, poll: null,
               modo: "2d", iso: null, interior: false, foco: true,
               filtros: { zonas: true, fogueiras: true, chefes: true, npcs: true, plano: true, outros: true, inimigos: false } };
  const em3d = () => st.modo === "iso" && st.iso;

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
  const nomeArea = (area) => { const a = (st.indice || []).find((x) => x.area === area); return a ? a.nome : "outra área"; };
  const tipoInimigo = (t) => (st.doc && st.doc.tipos_inimigo && st.doc.tipos_inimigo[t]) || {};
  // No 3D sem interior tudo aparece inteiro (nada está "em outro andar" sem o corte).
  const andarVisivel = () => (st.modo === "iso" && !st.interior ? "todos" : st.andar);
  const motivoSem3d = () => (!API ? "A vista 3D só abre pelo servidor local (o cenário vem dos arquivos do jogo)."
    : !Iso() || !Iso().suportado() ? "Este navegador não tem WebGL 2: a vista 3D não abre." : "");

  function montar(raiz, plano) {
    if (st.raiz === raiz) return Promise.resolve();
    st.raiz = raiz;
    st.plano = plano;
    const sem3d = motivoSem3d();
    raiz.innerHTML = `<div class="mp">
      <div class="mp-barra">
        <label class="mp-campo">Área <select class="mp-area" aria-label="Área do mapa"></select></label>
        <div class="mp-modo-toggle" role="group" aria-label="Vista do mapa">
          <button type="button" class="mp-modo" data-modo="2d" aria-pressed="true">2D</button>
          <button type="button" class="mp-modo" data-modo="iso" aria-pressed="false"${sem3d ? ` disabled title="${esc(sem3d)}"` : ' title="Cenário do jogo em 3D"'}>3D</button>
        </div>
        <div class="mp-filtros" role="group" aria-label="Mostrar no mapa">
          ${FILTROS.map(([k, l]) => `<button type="button" class="mp-filtro" data-filtro="${k}" aria-pressed="${st.filtros[k]}">${l}</button>`).join("")}
        </div>
      </div>
      <div class="mp-corpo">
        <div class="mp-tela" tabindex="0" aria-label="Mapa: arraste para mover, roda ou pinça para zoom">
          <div class="mp-iso-container" hidden></div>
          <div class="mp-iso-sombra" hidden></div>
          <svg class="mp-svg" xmlns="${NS}"><defs class="mp-defs"></defs><g class="mp-mundo"><g class="mp-grade"></g><g class="mp-chao"></g><g class="mp-zonas-chao"></g><g class="mp-paredes"></g><g class="mp-trilha"></g></g><g class="mp-trilha-tela"></g><g class="mp-pontos"></g></svg>
          <div class="mp-info"><p class="mp-onde" hidden></p><p class="mp-rota-info" role="status" hidden></p></div>
          <div class="mp-zoom"><button type="button" data-zoom="mais" aria-label="Aproximar">+</button><button type="button" data-zoom="menos" aria-label="Afastar">&#8722;</button><button type="button" data-zoom="tudo" aria-label="Ver a área inteira">&#9635;</button></div>
          <div class="mp-iso-ui" hidden>
            <div class="mp-iso-ctrl" role="toolbar" aria-label="Câmera 3D">
              <button type="button" data-iso="esq" title="Girar para a esquerda (segure Q)" aria-label="Girar para a esquerda">&#10226;</button>
              <button type="button" class="mp-bussola" data-iso="norte" title="Norte para cima (N)" aria-label="Norte para cima"><span>N</span></button>
              <button type="button" data-iso="dir" title="Girar para a direita (segure E)" aria-label="Girar para a direita">&#10227;</button>
              <button type="button" class="mp-iso-tg" data-iso="topo" aria-pressed="false" title="Olhar de cima ou de lado (T); segure R/F para inclinar">De cima</button>
              <button type="button" class="mp-iso-tg" data-iso="interior" aria-pressed="false" title="Cortar o que está acima do andar para ver dentro de cavernas e prédios (I); PgUp/PgDn trocam o andar">Interior</button>
              <button type="button" class="mp-iso-tg" data-iso="foco" aria-pressed="true" title="Escurecer o que está longe do centro da vista (O)">Foco</button>
            </div>
            <p class="mp-iso-ajuda"><kbd>WASD</kbd> andar · <kbd>Q</kbd><kbd>E</kbd> girar · <kbd>R</kbd><kbd>F</kbd> inclinar · <kbd>Shift</kbd> rápido · botão direito arrasta: girar · roda: zoom</p>
          </div>
          <p class="mp-iso-status" role="status" hidden></p>
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
      <p class="mp-leg"><span class="mp-k mp-k-zonas"></span>zona 1 → última <span class="mp-k mp-k-chefe"></span>chefe <span class="mp-k mp-k-npc"></span>NPC <span class="mp-k mp-k-plano"></span>do plano <span class="mp-k mp-k-outro"></span>item <span class="mp-k mp-k-rota"></span>rota <span class="mp-k mp-k-parada"></span>paradas 1 → última <span class="mp-k mp-k-eu"></span>você <span class="mp-k mp-k-inimigo"></span>inimigo <span class="mp-aviso">rota pelo chão; portas e alavancas não aparecem</span></p>
    </div>`;
    ligar(raiz);
    return carregar("mapas/indice.json").then((indice) => {
      st.indice = Array.isArray(indice) ? indice.filter((a) => AREA_OK.test(a.area)) : [];
      const sel = raiz.querySelector(".mp-area");
      sel.innerHTML = st.indice.map((a) => `<option value="${esc(a.area)}">${esc(a.nome)}${a.itens_plano ? ` (${a.itens_plano})` : ""}</option>`).join("");
      if (!st.indice.length) return vazio("Mapa indisponível. Rode o /buildsmith:build com o DS2 SotFS instalado.");
      if (API && !st.poll) {
        st.poll = setInterval(() => { if (!document.hidden && st.raiz.offsetParent !== null) buscarJogador(); }, POLL_MS);
      }
      return abrirArea(st.indice[0].area).then(() => (API ? buscarJogador() : null));
    });
  }

  // Você no mapa: posição da última gravação do save (o servidor relê o arquivo quando ele muda).
  async function buscarJogador() {
    let j = null;
    try {
      const r = await fetch(`${API}/${PAG[2]}/posicao`, { cache: "no-store" });
      j = r.ok ? await r.json() : null;
    } catch (e) { j = null; }
    const novo = j && AREA_OK.test(j.area) && Array.isArray(j.pos) && j.pos.length === 3 ? j : null;
    const chave = (x) => (x ? `${x.area}|${x.pos.join(",")}` : "");
    if (chave(novo) === chave(st.jogador)) return;
    st.jogador = novo;
    mostrarOnde();
    atualizar();
  }

  function mostrarOnde() {
    const el = st.raiz.querySelector(".mp-onde");
    const j = st.jogador;
    if (!j) { el.hidden = true; return; }
    const aqui = (st.indice || []).some((a) => a.area === j.area);
    el.innerHTML = aqui
      ? `<span class="mp-eu-k"></span>Você: ${esc(nomeArea(j.area))} <button type="button" class="pesq" data-eu>Onde estou</button>`
      : `<span class="mp-eu-k"></span>Você está fora das áreas deste mapa. Atualize o plano para incluir a área atual.`;
    el.hidden = false;
  }

  async function irParaJogador() {
    const j = st.jogador;
    if (!j) return;
    if (!st.doc || st.doc.area !== j.area) await abrirArea(j.area);
    if (!st.doc || st.doc.area !== j.area) return;
    const tela = st.raiz.querySelector(".mp-tela");
    st.andar = andarDe(st.doc.planta.andares, j.pos[1]) ?? "todos";
    st.vista = { ...ajustar(caixa([[j.pos[0], j.pos[2]]]), tela.clientWidth, tela.clientHeight, 40) };
    desenharChao();
    if (em3d()) {
      sincronizarAndarIso();
      st.iso.focar(j.pos, tela.clientHeight / st.vista.s);
    }
    atualizar();
  }

  function statusRota(texto) {
    const el = st.raiz.querySelector(".mp-rota-info");
    el.innerHTML = texto ? `${texto} <button type="button" class="mp-x" data-limpar-rota aria-label="Apagar rota">&#10005;</button>` : "";
    el.hidden = !texto;
  }

  // "Rota até aqui": daqui (você na mesma área) ou da fogueira da zona do alvo (você em outra área).
  async function rotaAte() {
    const alvo = alvoDoPop();
    if (!alvo || !API) return;
    const area = st.doc.area;
    let de, nomeDe, aviso;
    if (st.jogador && st.jogador.area === area) {
      de = st.jogador.pos; nomeDe = "Você"; aviso = "Daqui:";
    } else {
      const fog = st.doc.fogueiras.find((f) => alvo.zona != null && f.zona === alvo.zona) || null;
      if (!fog) { statusRota("Sem fogueira na zona do alvo para começar a rota."); return; }
      de = fog.pos; nomeDe = fog.nome;
      aviso = st.jogador ? `Você está em ${esc(nomeArea(st.jogador.area))}: viaje até a fogueira ${esc(fog.nome)} e siga a rota.`
        : `Da fogueira ${esc(fog.nome)}:`;
    }
    statusRota("Calculando a rota…");
    let j = null;
    try {
      const q = `area=${area}&de=${de.join(",")}&ate=${alvo.pos.join(",")}`;
      const r = await fetch(`${API}/rota?${q}`, { cache: "no-store" });
      j = r.ok ? await r.json() : null;
    } catch (e) { j = null; }
    if (!j) { statusRota("O servidor local não respondeu."); return; }
    if (!j.rota) { statusRota("Não achei caminho pelo chão até aí (pode ter queda, porta, elevador ou alavanca no meio)."); return; }
    const andares = st.doc.planta.andares;
    st.rota = { area, trechos: [j.rota.pontos], metros: j.rota.metros,
                pontos: [{ n: 1, pos: de, andar: andarDe(andares, de[1]), nome: nomeDe },
                         { n: 2, pos: alvo.pos, andar: alvo.andar ?? andarDe(andares, alvo.pos[1]), nome: alvo.nome }] };
    const tela = st.raiz.querySelector(".mp-tela");
    st.vista = ajustar(caixa(j.rota.pontos.map((p) => [p[0], p[2]])), tela.clientWidth, tela.clientHeight, 30);
    fecharPop();
    desenharChao();
    vistaParaIso(true);
    atualizar();
    statusRota(`${aviso} ${fmt.format(j.rota.metros)} m pelo chão até ${esc(alvo.nome)}.`);
  }

  function alvoDoPop() {
    if (!st.pop) return null;
    const { tipo, i } = st.pop;
    const p = (listaDe(tipo) || [])[i];
    if (!p) return null;
    const nome = tipo === "item" ? (p.itens[0] ? p.itens[0].nome : "item") : tipo === "inimigo" ? (tipoInimigo(p.tipo).nome || "inimigo") : p.nome;
    return { pos: p.pos, andar: p.andar, zona: p.zona, nome };
  }

  function listaDe(tipo) {
    return { npc: st.doc.npcs, chefe: st.doc.chefes, item: st.doc.itens, inimigo: st.doc.inimigos, fogueira: st.doc.fogueiras }[tipo];
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
    st.tipoSel = null;
    st.pop = null;
    st.interior = false;  // no 3D, cada área abre inteira; o corte é escolha de quem está olhando
    st.raiz.querySelector(".mp-pop").hidden = true;
    statusRota("");
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
    if (em3d()) await abrirIso();
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
  const ultimaParada = () => (st.rota && st.rota.pontos.length ? Math.max(...st.rota.pontos.map((p) => p.n)) : 1);

  // Gradiente da linha da rota (cor da 1ª parada até a da última), do início ao fim de cada trecho.
  function gradienteRota(id, a, b) {
    const total = ultimaParada();
    return `<linearGradient id="${id}" gradientUnits="userSpaceOnUse" x1="${a[0].toFixed(1)}" y1="${a[1].toFixed(1)}" x2="${b[0].toFixed(1)}" y2="${b[1].toFixed(1)}"><stop offset="0" stop-color="${corZona(1, total)}"/><stop offset="1" stop-color="${corZona(total, total)}"/></linearGradient>`;
  }
  const linhaRota = (pts, id) => {
    const p = pts.map((q) => `${q[0].toFixed(1)},${q[1].toFixed(1)}`).join(" ");
    return `<polyline class="mp-rota-base" vector-effect="non-scaling-stroke" points="${p}"/><polyline class="mp-rota" vector-effect="non-scaling-stroke" stroke="url(#${id})" points="${p}"/>`;
  };

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
    marcarAndares();
    st.raiz.querySelectorAll("[data-zona]").forEach((b) => b.setAttribute("aria-pressed", String(st.zonaSel === Number(b.dataset.zona))));
    const cx = caixa(todosPontosChao());
    const linhas = [];
    for (let x = Math.floor(cx.x0 / 10) * 10; x <= cx.x1 + 10; x += 10) linhas.push(`<line class="${x % 50 ? "mp-g10" : "mp-g50"}" vector-effect="non-scaling-stroke" x1="${x}" y1="${-(cx.z1 + 10)}" x2="${x}" y2="${-(cx.z0 - 10)}"/>`);
    for (let z = Math.floor(cx.z0 / 10) * 10; z <= cx.z1 + 10; z += 10) linhas.push(`<line class="${z % 50 ? "mp-g10" : "mp-g50"}" vector-effect="non-scaling-stroke" x1="${cx.x0 - 10}" y1="${-z}" x2="${cx.x1 + 10}" y2="${-z}"/>`);
    st.raiz.querySelector(".mp-grade").innerHTML = linhas.join("");
    st.raiz.querySelector(".mp-trilha").innerHTML = st.rota ? st.rota.trechos.filter((t) => t && t.length > 1).map((t, i) => {
      const pts = t.map((p) => [p[0], -p[2]]);
      return gradienteRota(`mp-rg2-${i}`, pts[0], pts[pts.length - 1]) + linhaRota(pts, `mp-rg2-${i}`);
    }).join("") : "";
  }

  function marcarAndares() {
    const vis = andarVisivel();
    st.raiz.querySelectorAll("[data-andar]").forEach((b) => b.setAttribute("aria-pressed", String(String(vis) === b.dataset.andar)));
  }

  // ---- vista 3D ------------------------------------------------------------------------------------
  function statusIso(texto) {
    const el = st.raiz.querySelector(".mp-iso-status");
    el.textContent = texto || "";
    el.hidden = !texto || st.modo !== "iso";
  }

  async function abrirIso() {
    const area = st.doc.area;
    const v = st.vista;
    await st.iso.iniciar();
    st.iso.redimensionar();
    const cena = await st.iso.abrir(area);
    if (!cena || !em3d() || st.doc.area !== area) return;
    sincronizarAndarIso();
    st.iso.verComo2D(v.cx, v.cz, v.s);
    atualizar();
  }

  // Leva o enquadramento do 2D (st.vista) para a câmera 3D, mantendo giro e inclinação.
  function vistaParaIso(animar) {
    if (!em3d() || !st.iso.cena || !st.vista) return;
    st.iso.verComo2D(st.vista.cx, st.vista.cz, st.vista.s, undefined, animar);
  }

  function sincronizarAndarIso() {
    marcarAndares();
    const ui = st.raiz.querySelector(".mp-iso-ui");
    ui.querySelector('[data-iso="interior"]').setAttribute("aria-pressed", String(st.interior && st.andar !== "todos"));
    if (!em3d()) return;
    const a = st.interior && st.andar !== "todos" ? st.doc.planta.andares.find((x) => x.id === st.andar) : null;
    st.iso.setCorte(a ? { min: a.min, max: a.max, altura: a.altura } : null);
  }

  // Interior: corta acima do andar de onde a vista está (o seu, se você estiver perto do centro); PgUp/PgDn trocam.
  function alternarInterior(ligar = !st.interior) {
    st.interior = ligar;
    if (ligar) {
      const alvo = st.iso.alvo, j = st.jogador && st.jogador.area === st.doc.area ? st.jogador.pos : null;
      const y = j && Math.hypot(j[0] - alvo[0], j[2] - alvo[2]) < st.iso.vista * 0.6 ? j[1] : alvo[1];
      st.andar = andarDe(st.doc.planta.andares, y) ?? "todos";
      if (st.andar === "todos") st.interior = false;
    }
    desenharChao();
    sincronizarAndarIso();
    atualizar();
  }

  function trocarAndar(dir) {
    const ord = [...st.doc.planta.andares].sort((a, b) => a.altura - b.altura);
    if (!ord.length) return;
    let i = ord.findIndex((a) => a.id === st.andar);
    if (i < 0 || !st.interior) i = ord.findIndex((a) => a.id === andarDe(ord, st.iso.alvo[1]));
    else i = Math.min(ord.length - 1, Math.max(0, i + dir));
    st.andar = ord[i].id;
    st.interior = true;
    desenharChao();
    sincronizarAndarIso();
    atualizar();
  }

  async function mudarModo(novo) {
    if (st.modo === novo || (novo === "iso" && motivoSem3d())) return;
    const raiz = st.raiz;
    if (novo === "iso" && !st.iso) {
      st.iso = new (Iso())(raiz.querySelector(".mp-iso-container"), { onMudar: atualizar, onStatus: statusIso });
      st.iso.setFoco(st.foco);
    }
    if (st.modo === "iso" && st.iso && st.iso.cena) {
      const v = st.iso.comoVista2D();
      st.vista = { cx: v.cx, cz: v.cz, s: Math.min(MAX_S, Math.max(MIN_S, v.s)) };
    }
    st.modo = novo;
    raiz.querySelectorAll(".mp-modo").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.modo === novo)));
    const tres = novo === "iso";
    raiz.querySelector(".mp-iso-container").hidden = !tres;
    raiz.querySelector(".mp-iso-ui").hidden = !tres;
    raiz.querySelector(".mp-iso-sombra").hidden = !tres || !st.foco;
    raiz.querySelector(".mp-mundo").style.display = tres ? "none" : "";
    raiz.querySelector(".mp-tela").classList.toggle("mp-3d", tres);
    st.iso && st.iso.setAtivo(tres);
    statusIso(null);
    desenharChao();
    sincronizarAndarIso();
    atualizar();
    if (tres) {
      raiz.querySelector(".mp-tela").focus({ preventScroll: true });
      await abrirIso();
    }
  }

  function paraTela(x, z, y) {
    if (em3d()) return st.iso.projetar(x, y ?? 0, z);
    const tela = st.raiz.querySelector(".mp-tela");
    const v = st.vista;
    return [(x - v.cx) * v.s + tela.clientWidth / 2, (v.cz - z) * v.s + tela.clientHeight / 2, true, null];
  }

  // Escala em pixels por metro (no 3D ortográfico, a da vista no plano da tela).
  const escala = (h) => (em3d() ? h / st.iso.vista : st.vista ? st.vista.s : 5);

  function atualizar() {
    if (!st.doc || !st.vista) return;
    const tela = st.raiz.querySelector(".mp-tela");
    const w = tela.clientWidth, h = tela.clientHeight, v = st.vista, tres = em3d();
    if (!tres) {
      st.raiz.querySelector(".mp-mundo").setAttribute("transform", `translate(${w / 2 - v.cx * v.s} ${h / 2 + v.cz * v.s}) scale(${v.s})`);
      st.raiz.querySelector(".mp-grade").classList.toggle("mp-longe", v.s < 2);
    }
    if (tres && !st.iso.cena) {  // cenário ainda carregando: nada projetado numa câmera sem lugar
      st.raiz.querySelector(".mp-pontos").innerHTML = "";
      st.raiz.querySelector(".mp-trilha-tela").innerHTML = "";
      return;
    }
    const s = escala(h), andarSel = andarVisivel();
    const tam = tamanhoIcone(s), nomes = s >= 4;
    const partes = [], clips = [], defs = [];
    const dentro = (sx, sy) => sx > -50 && sy > -50 && sx < w + 50 && sy < h + 50;
    const f1 = (n) => n.toFixed(1);
    // projeção + o que esconder: fora da tela, acima do corte de interior; "longe" do foco fica apagado
    const ver = (pos) => {
      const [sx, sy, vis, extra] = paraTela(pos[0], pos[2], pos[1]);
      if (!vis || !dentro(sx, sy) || (extra && extra.cortado)) return null;
      return [sx, sy, extra && extra.longe ? " mp-fora-foco" : ""];
    };
    const retrato = (k, sx, sy, r, src, classe, titulo, rotulo, dados) => {
      const id = `mp-c${k}`;
      clips.push(`<clipPath id="${id}"><circle cx="${f1(sx)}" cy="${f1(sy)}" r="${f1(r)}"/></clipPath>`);
      const img = src && ICONE_OK.test(src) ? `<image href="${esc(src)}" x="${f1(sx - r)}" y="${f1(sy - r)}" width="${f1(2 * r)}" height="${f1(2 * r)}" clip-path="url(#${id})" preserveAspectRatio="xMidYMin slice"/>`
        : `<text class="mp-ini" x="${f1(sx)}" y="${f1(sy + 4)}">${esc(titulo.trim().replace(/^the\s+/i, "").charAt(0))}</text>`;
      return `<g class="${classe}" ${dados} tabindex="0"><title>${esc(titulo)}</title><circle class="mp-fundo" cx="${f1(sx)}" cy="${f1(sy)}" r="${f1(r)}"/>${img}<circle class="mp-aro" cx="${f1(sx)}" cy="${f1(sy)}" r="${f1(r)}"/>${rotulo ? `<text class="mp-rotulo" x="${f1(sx)}" y="${f1(sy + r + 12)}">${esc(rotulo)}</text>` : ""}</g>`;
    };
    if (st.filtros.inimigos) st.doc.inimigos.forEach((e, i) => {
      const p = ver(e.pos);
      if (!p) return;
      const [sx, sy, longe] = p;
      const t = tipoInimigo(e.tipo), igual = st.tipoSel && e.tipo === st.tipoSel;
      const classe = `mp-inimigo ${estadoAndar(e.andar, andarSel)}${longe}${igual ? " mp-inimigo-sel" : st.tipoSel ? " mp-inimigo-fora" : ""}`;
      partes.push(`<circle class="${classe}" data-tipo="inimigo" data-i="${i}" tabindex="0" cx="${f1(sx)}" cy="${f1(sy)}" r="${igual ? 6 : 4.5}"><title>${esc(t.nome || "Inimigo (nome não confirmado)")}</title></circle>`);
    });
    st.doc.itens.forEach((p, i) => {
      const destaque = p.plano || (st.destaque && p.item_id === st.destaque);
      if (destaque ? !st.filtros.plano : !st.filtros.outros) return;
      const q = ver(p.pos);
      if (!q) return;
      const [sx, sy, longe] = q;
      const estado = estadoAndar(p.andar, andarSel);
      const t = estado === "cheio" ? (destaque ? tam + 4 : tam) : Math.max(12, tam - 8);
      const img = p.icone && ICONE_OK.test(p.icone) ? `<image href="${esc(p.icone)}" x="${f1(sx - t / 2)}" y="${f1(sy - t / 2)}" width="${t}" height="${t}"/>` : `<rect class="mp-losango" x="${f1(sx - t / 4)}" y="${f1(sy - t / 4)}" width="${t / 2}" height="${t / 2}" transform="rotate(45 ${f1(sx)} ${f1(sy)})"/>`;
      const nome = p.itens[0] ? `${p.itens[0].nome}${p.itens[0].qtd > 1 ? ` ×${p.itens[0].qtd}` : ""}${p.itens.length > 1 ? ` +${p.itens.length - 1}` : ""}` : "";
      partes.push(`<g class="mp-item ${destaque ? "mp-do-plano" : ""} ${estado}${longe}" data-tipo="item" data-i="${i}" tabindex="0"><title>${esc(nome)}</title><rect class="mp-moldura" x="${f1(sx - t / 2 - 2)}" y="${f1(sy - t / 2 - 2)}" width="${t + 4}" height="${t + 4}" rx="3"/>${img}${nomes && estado === "cheio" && !longe ? `<text class="mp-rotulo" x="${f1(sx)}" y="${f1(sy + t / 2 + 12)}">${esc(nome)}</text>` : ""}</g>`);
    });
    if (st.filtros.fogueiras) st.doc.fogueiras.forEach((f, i) => {
      const q = ver(f.pos);
      if (!q) return;
      const [sx, sy, longe] = q;
      const estado = estadoAndar(f.andar, andarSel), t = estado === "cheio" ? tam + 2 : Math.max(12, tam - 8);
      const badge = f.zona && st.filtros.zonas ? `<circle class="mp-badge" cx="${f1(sx - t / 2)}" cy="${f1(sy - t / 2)}" r="8" fill="${corDe(f.zona)}"/><text class="mp-badge-n" x="${f1(sx - t / 2)}" y="${f1(sy - t / 2 + 3.5)}">${f.zona}</text>` : "";
      partes.push(`<g class="mp-fog ${estado}${longe}" data-tipo="fogueira" data-i="${i}" tabindex="0"><title>${esc(f.zona ? nomeZona(f.zona) : f.nome)}</title><image href="icons/fogueira.png" x="${f1(sx - t / 2)}" y="${f1(sy - t / 2)}" width="${t}" height="${t}"/>${badge}${(nomes || s >= 1.5) && estado === "cheio" && !longe ? `<text class="mp-rotulo mp-rotulo-fog" x="${f1(sx)}" y="${f1(sy - t / 2 - 5)}">${esc(f.zona ? `${f.zona} · ${f.nome}` : f.nome)}</text>` : ""}</g>`);
    });
    if (st.filtros.npcs) (st.doc.npcs || []).forEach((n, i) => {
      const q = ver(n.pos);
      if (!q) return;
      const [sx, sy, longe] = q;
      const estado = estadoAndar(n.andar, andarSel);
      const r = (estado === "cheio" ? tam + (n.plano ? 6 : 2) : Math.max(12, tam - 8)) / 2;
      partes.push(retrato(`n${i}`, sx, sy, r, n.retrato, `mp-npc ${n.plano ? "mp-do-plano" : ""} ${estado}${longe}`, n.nome,
        (n.plano || s >= 3) && estado === "cheio" && !longe ? n.nome : "", `data-tipo="npc" data-i="${i}"`));
    });
    if (st.filtros.chefes) (st.doc.chefes || []).forEach((c, i) => {
      const q = ver(c.pos);
      if (!q) return;
      const [sx, sy, longe] = q;
      const estado = estadoAndar(c.andar, andarSel);
      const r = (estado === "cheio" ? tam + 12 : Math.max(14, tam - 4)) / 2;
      partes.push(retrato(`c${i}`, sx, sy, r, c.retrato, `mp-chefe ${c.estado === "derrotado" ? "derrotado" : ""} ${estado}${longe}`, c.nome,
        estado === "cheio" && !longe ? c.nome : "", `data-tipo="chefe" data-i="${i}"`));
    });
    // rota no 3D: a linha é projetada aqui (no 2D ela fica no mundo, em desenharChao)
    let trilha = "";
    if (tres && st.rota) {
      st.rota.trechos.filter((t) => t && t.length > 1).forEach((t, i) => {
        trechosTela(t, (p) => st.iso.projetar(p[0], p[1] + 0.3, p[2])).forEach((pts, k) => {
          const id = `mp-rg3-${i}-${k}`;
          defs.push(gradienteRota(id, pts[0], pts[pts.length - 1]));
          trilha += linhaRota(pts, id);
        });
      });
    }
    st.raiz.querySelector(".mp-trilha-tela").innerHTML = trilha;
    // paradas da rota: pinos numerados na cor da ordem (dourado na 1ª até brasa na última)
    if (st.rota) {
      const total = ultimaParada();
      const eu = st.jogador && st.jogador.area === st.doc.area ? st.jogador.pos : null;
      st.rota.pontos.forEach((p) => {
        if (eu && Math.hypot(p.pos[0] - eu[0], p.pos[1] - eu[1], p.pos[2] - eu[2]) < 0.5) return;  // a parada é você: vale o seu marcador
        const q = ver(p.pos);
        if (!q) return;
        const [sx, sy, longe] = q;
        const cor = corZona(p.n, total), fim = p.n === total && total > 1;
        partes.push(`<g class="mp-passo ${estadoAndar(p.andar, andarSel)}${longe}${fim ? " mp-passo-fim" : ""}"><title>${esc(`${p.n}. ${p.nome}`)}</title><circle class="mp-passo-chao" cx="${f1(sx)}" cy="${f1(sy)}" r="3"/><path class="mp-passo-pino" d="${pino(sx, sy)}" fill="${cor}"/><text x="${f1(sx)}" y="${f1(sy - 14.2)}" fill="${tintaParada(p.n, total)}">${p.n}</text></g>`);
      });
    }
    const j = st.jogador;
    if (j && j.area === st.doc.area) {
      const [sx, sy, vis, extra] = paraTela(j.pos[0], j.pos[2], j.pos[1]);
      if (vis && dentro(sx, sy) && !(extra && extra.cortado)) {
        const estado = estadoAndar(andarDe(st.doc.planta.andares, j.pos[1]), andarSel);
        partes.push(`<g class="mp-eu ${estado}"><title>Você (última gravação do save)</title><circle class="mp-eu-pulso" cx="${f1(sx)}" cy="${f1(sy)}" r="9"/><circle class="mp-eu-ponto" cx="${f1(sx)}" cy="${f1(sy)}" r="7"/><text class="mp-rotulo mp-rotulo-eu" x="${f1(sx)}" y="${f1(sy - 13)}">Você</text></g>`);
      }
    }
    st.raiz.querySelector(".mp-defs").innerHTML = defs.join("");
    st.raiz.querySelector(".mp-pontos").innerHTML = `<defs>${clips.join("")}</defs>${partes.join("")}`;
    const m = regua(s);
    st.raiz.querySelector(".mp-regua-barra").style.width = `${Math.round(m * s)}px`;
    st.raiz.querySelector(".mp-regua-txt").textContent = `${m} m`;
    if (tres) {
      const ui = st.raiz.querySelector(".mp-iso-ui");
      ui.querySelector(".mp-bussola span").style.transform = `rotate(${(-st.iso.giro).toFixed(3)}rad)`;
      ui.querySelector('[data-iso="topo"]').setAttribute("aria-pressed", String(st.iso.deCima()));
    }
    if (st.pop) posicionarPop();
  }

  function mostrarPop(tipo, i) {
    const pop = st.raiz.querySelector(".mp-pop");
    const p = (listaDe(tipo) || [])[i];
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
    } else if (tipo === "inimigo") {
      const t = tipoInimigo(p.tipo), link = linkSeguro(t.wiki);
      const numeros = [t.hp != null ? `HP ${fmt.format(t.hp)}` : "", t.almas ? `${fmt.format(t.almas)} almas` : ""].filter(Boolean).join(" · ");
      corpo = `<p class="mp-pop-tit">${t.nome ? esc(t.nome) : "Inimigo"}</p>
        ${t.nome ? "" : '<p class="mp-pop-sub">Nome não confirmado: o jogo não guarda nome de inimigo comum e a wiki não bateu com um só.</p>'}
        ${numeros ? `<p class="mp-pop-sub">${numeros} <span class="mp-fonte">(jogo)</span></p>` : ""}
        ${t.drops && t.drops.length ? `<p class="mp-pop-sub">Drops (jogo): ${esc(t.drops.join(", "))}</p>` : ""}
        ${t.prova ? `<p class="mp-prova">Nome pela wiki: ${esc(t.prova)}</p>` : ""}
        <p><button type="button" class="pesq" data-iguais="${esc(p.tipo)}">${st.tipoSel === p.tipo ? "Parar de destacar" : `Destacar os ${fmt.format(t.n || 1)} iguais`}</button></p>
        ${link ? `<a href="${esc(link)}" target="_blank" rel="noopener noreferrer">página na wiki</a>` : ""}`;
    } else if (tipo === "fogueira") {
      corpo = `<p class="mp-pop-tit">${esc(p.nome)}</p><p class="mp-pop-sub">Fogueira${p.zona ? ` da zona ${esc(nomeZona(p.zona))}` : ""}</p>`;
    } else {
      corpo = `<ul>${p.itens.map((it) => `<li>${esc(it.nome)}${it.qtd > 1 ? ` <span class="mp-qtd">×${it.qtd}</span>` : ""}</li>`).join("")}</ul>${p.item_id ? `<a class="req-link" href="#item-${esc(p.item_id)}" data-goto-item="${esc(p.item_id)}">ver em Onde pegar</a>` : ""}`;
    }
    const rota = API ? '<p><button type="button" class="pesq" data-rota-ate>Rota até aqui</button></p>' : "";
    pop.innerHTML = `<button type="button" class="mp-pop-x" aria-label="Fechar">&#10005;</button>${corpo}${rota}${meta}`;
    pop.hidden = false;
    posicionarPop();
  }

  // O balão acompanha o ponto quando a vista anda (sem refazer o conteúdo).
  function posicionarPop() {
    const p = (listaDe(st.pop.tipo) || [])[st.pop.i];
    if (!p) return;
    const pop = st.raiz.querySelector(".mp-pop");
    const [sx, sy] = paraTela(p.pos[0], p.pos[2], p.pos[1]);
    const tela = st.raiz.querySelector(".mp-tela");
    pop.style.left = `${Math.min(Math.max(8, sx + 16), tela.clientWidth - 240)}px`;
    pop.style.top = `${Math.min(Math.max(8, sy - 20), tela.clientHeight - 150)}px`;
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
    sincronizarAndarIso();
    vistaParaIso(true);
    atualizar();
  }

  // ---- interação ---------------------------------------------------------------------------------
  function zoom(fator, ox, oy) {
    if (em3d()) { st.iso.zoomPor(fator, ox, oy); return; }
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
    const escalaAgora = () => (em3d() ? tela.clientHeight / st.iso.vista : st.vista ? st.vista.s : 1);
    tela.addEventListener("wheel", (ev) => {
      ev.preventDefault();
      const r = tela.getBoundingClientRect();
      zoom(Math.exp(-Math.max(-300, Math.min(300, ev.deltaY)) * 0.0016), ev.clientX - r.left, ev.clientY - r.top);
    }, { passive: false });
    tela.addEventListener("contextmenu", (ev) => { if (em3d()) ev.preventDefault(); });
    tela.addEventListener("pointerenter", () => {
      if (em3d() && (!document.activeElement || document.activeElement === document.body)) tela.focus({ preventScroll: true });
    });
    tela.addEventListener("pointerdown", (ev) => {
      if (ev.target.closest(".mp-zoom, .mp-pop, .mp-info, .mp-iso-ui")) return;
      toques.set(ev.pointerId, [ev.clientX, ev.clientY]);
      tela.setPointerCapture(ev.pointerId);
      moveu = false;
      if (em3d()) tela.focus({ preventScroll: true });
      if (toques.size === 1) {
        arrasto = { x: ev.clientX, y: ev.clientY, v: { ...st.vista } };
        if (em3d()) st.iso.apertar(ev);
      }
      if (toques.size === 2) {
        const [a, b] = [...toques.values()];
        pinca = { d: Math.hypot(a[0] - b[0], a[1] - b[1]), s: escalaAgora() };
        arrasto = null;
        if (em3d()) st.iso.soltar();
      }
    });
    tela.addEventListener("pointermove", (ev) => {
      if (!toques.has(ev.pointerId) || !st.vista) return;
      toques.set(ev.pointerId, [ev.clientX, ev.clientY]);
      if (pinca && toques.size === 2) {
        const [a, b] = [...toques.values()];
        const r = tela.getBoundingClientRect();
        zoom((pinca.s * Math.hypot(a[0] - b[0], a[1] - b[1]) / pinca.d) / escalaAgora(), (a[0] + b[0]) / 2 - r.left, (a[1] + b[1]) / 2 - r.top);
        moveu = true;
      } else if (arrasto) {
        const dx = ev.clientX - arrasto.x, dy = ev.clientY - arrasto.y;
        if (Math.abs(dx) + Math.abs(dy) > 3) moveu = true;
        if (em3d()) st.iso.mover(ev);
        else {
          st.vista = { ...arrasto.v, cx: arrasto.v.cx - dx / arrasto.v.s, cz: arrasto.v.cz + dy / arrasto.v.s };
          atualizar();
        }
      }
    });
    const soltar = (ev) => {
      toques.delete(ev.pointerId);
      if (toques.size < 2) pinca = null;
      if (!toques.size) { arrasto = null; if (st.iso) st.iso.soltar(); }
    };
    tela.addEventListener("pointerup", (ev) => {
      soltar(ev);
      if (moveu || ev.button === 2) return;
      const alvo = document.elementFromPoint(ev.clientX, ev.clientY);
      const marca = alvo && alvo.closest("[data-tipo]");
      if (marca) mostrarPop(marca.dataset.tipo, Number(marca.dataset.i));
      else if (!alvo || !alvo.closest(".mp-pop")) fecharPop();
    });
    tela.addEventListener("pointercancel", soltar);
    tela.addEventListener("blur", () => { if (st.iso) st.iso.limparTeclas(); });
    tela.addEventListener("keyup", (ev) => { if (em3d()) st.iso.tecla(ev, false); });
    tela.addEventListener("keydown", (ev) => {
      if (ev.target !== tela && ev.target.closest && ev.target.closest(".mp-pop")) return;
      if (em3d()) {
        if (st.iso.tecla(ev, true)) { ev.preventDefault(); return; }
        const acoes3d = { KeyI: () => alternarInterior(), KeyO: () => alternarFoco(), KeyT: () => { st.iso.alternarTopo(); atualizar(); },
                          KeyN: () => st.iso.norte(), PageUp: () => trocarAndar(1), PageDown: () => trocarAndar(-1),
                          Home: () => enquadrarTudo() };
        if (acoes3d[ev.code] && !ev.ctrlKey && !ev.metaKey && !ev.altKey) { ev.preventDefault(); acoes3d[ev.code](); return; }
      }
      const passo = 40 / (st.vista ? st.vista.s : 1);
      const acoes = { "+": () => zoom(1.25), "=": () => zoom(1.25), "-": () => zoom(0.8), ArrowLeft: () => mover(-passo, 0),
                      ArrowRight: () => mover(passo, 0), ArrowUp: () => mover(0, passo), ArrowDown: () => mover(0, -passo), Escape: fecharPop };
      if (acoes[ev.key]) { ev.preventDefault(); acoes[ev.key](); }
      const marca = ev.target.closest && ev.target.closest("[data-tipo]");
      if ((ev.key === "Enter" || ev.key === " ") && marca) { ev.preventDefault(); mostrarPop(marca.dataset.tipo, Number(marca.dataset.i)); }
    });
    raiz.addEventListener("click", (ev) => {
      const modoBtn = ev.target.closest(".mp-modo");
      if (modoBtn) { mudarModo(modoBtn.dataset.modo); return; }
      const isoBtn = ev.target.closest("[data-iso]");
      if (isoBtn && em3d()) {
        const acao = isoBtn.dataset.iso;
        if (acao === "esq") st.iso.girar(-Math.PI / 4);
        else if (acao === "dir") st.iso.girar(Math.PI / 4);
        else if (acao === "norte") st.iso.norte();
        else if (acao === "topo") st.iso.alternarTopo();
        else if (acao === "interior") alternarInterior();
        else if (acao === "foco") alternarFoco();
        atualizar();
        return;
      }
      const z = ev.target.closest("[data-zoom]");
      if (z) {
        if (z.dataset.zoom === "tudo") enquadrarTudo();
        else zoom(z.dataset.zoom === "mais" ? 1.4 : 1 / 1.4);
        return;
      }
      const a = ev.target.closest("[data-andar]");
      if (a) {
        st.andar = a.dataset.andar === "todos" ? "todos" : Number(a.dataset.andar);
        if (st.modo === "iso") st.interior = st.andar !== "todos";  // no 3D, escolher o andar já corta acima dele
        desenharChao();
        sincronizarAndarIso();
        atualizar();
        return;
      }
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
      if (ev.target.closest("[data-rota-ate]")) { rotaAte(); return; }
      if (ev.target.closest("[data-eu]")) { irParaJogador(); return; }
      if (ev.target.closest("[data-limpar-rota]")) { st.rota = null; statusRota(""); desenharChao(); atualizar(); return; }
      const iguais = ev.target.closest("[data-iguais]");
      if (iguais) {
        st.tipoSel = st.tipoSel === iguais.dataset.iguais ? null : iguais.dataset.iguais;
        if (st.pop) mostrarPop(st.pop.tipo, st.pop.i);
        atualizar();
        return;
      }
      if (ev.target.closest(".mp-pop-x")) fecharPop();
    });
    raiz.querySelector(".mp-area").addEventListener("change", (ev) => abrirArea(ev.target.value));
    if (window.ResizeObserver) new ResizeObserver(() => { if (st.iso) st.iso.redimensionar(); atualizar(); }).observe(tela);
  }

  function alternarFoco() {
    st.foco = !st.foco;
    if (st.iso) st.iso.setFoco(st.foco);
    st.raiz.querySelector('[data-iso="foco"]').setAttribute("aria-pressed", String(st.foco));
    st.raiz.querySelector(".mp-iso-sombra").hidden = st.modo !== "iso" || !st.foco;
    atualizar();
  }

  function enquadrarTudo() {
    const tela = st.raiz.querySelector(".mp-tela");
    st.vista = ajustar(caixa(todosPontosChao()), tela.clientWidth, tela.clientHeight, 10);
    vistaParaIso(true);
    atualizar();
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

  window.buildsmithMapa = { montar, ver, _teste: { caixa, ajustar, regua, tamanhoIcone, estadoAndar, corZona, andarDe, tintaParada, pino, trechosTela } };
})();
