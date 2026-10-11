(function () {
  // Mapa geral da área (estilo The Division): vista de cima por andar, zonas de fogueira em sequência, chefes, NPCs,
  // todos os itens com ícone, grade, régua, zoom e arrastar, filtros, painel "Rota da área" e "Ver no mapa".
  // Dados: mapas/indice.json + mapas/<area>.json, gerados por script a partir dos arquivos do jogo.
  // Pelo servidor local (/p/<jogo>/<personagem>/): você no mapa (posição do save), "Rota até aqui" pelo chão e a vista
  // 3D (iso.js) com o cenário do jogo, com os mesmos marcadores, filtros, andares e rota projetados por cima.
  // Inimigos e objetos (portas, alavancas, elevadores, névoas, baús) têm tamanho em metros: no 2D crescem com o zoom,
  // no 3D viram formas na escala do cenário (iso.setEntidades). Porta com chave mostra a chave e onde ela está.
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
                   ["plano", "Itens do plano"], ["outros", "Outros itens"], ["chaves", "Chaves"], ["baus", "Baús"],
                   ["objetos", "Portas e alavancas"], ["inimigos", "Inimigos"]];
  // Objetos do mapa (ds2mapa/ds2nomes): rótulo, forma 3D e tamanho em metros (largura, altura, profundidade).
  const OBJ = {
    porta: { nome: "Porta", forma: "caixa", dims: [2.2, 3.0, 0.3], cor: 0x8a5a33 },
    nevoa: { nome: "Névoa", forma: "caixa", dims: [3.2, 3.6, 0.08], cor: 0xe8ecf2, transp: true },
    alavanca: { nome: "Alavanca", forma: "capsula", dims: [0.24, 1.3, 0.24], cor: 0xb4bcc4 },
    elevador: { nome: "Elevador", forma: "cilindro", dims: [2.6, 0.3, 2.6], cor: 0x6f8fae },
    ponte: { nome: "Ponte", forma: "losango", dims: [1, 1, 1], base: 2.2, cor: 0x9a8f7e },
    pharros: { nome: "Mecanismo de Pharros", forma: "losango", dims: [0.9, 0.9, 0.9], base: 2.2, cor: 0xd7c27a },
    escada: { nome: "Escada", forma: "caixa", dims: [0.9, 3.2, 0.12], cor: 0x9c7a52 },
    bau: { nome: "Baú", forma: "caixa", dims: [1.1, 0.7, 0.7], cor: 0x7b4f24 },
  };
  const OBJ_TEXTO = {
    porta: "Porta ou portão. A rota pelo chão não sabe se está trancada.",
    nevoa: "Névoa: passagem para outra área ou para a sala do chefe.",
    alavanca: "Alavanca ou interruptor: costuma abrir portão, ponte ou chamar elevador por perto.",
    elevador: "Elevador.",
    ponte: "Ponte que muda (cai, quebra ou é baixada por alavanca).",
    pharros: "Mecanismo de Pharros: abre com uma Pharros' Lockstone.",
    escada: "Escada.",
    bau: "Baú.",
  };
  const COR_CHAVE = 0xd9b04a;
  // Tinta do objeto real da cena quando o filtro dele está ligado (multiplica a textura do jogo).
  const TINTA_OBJ = { porta: 0xffc48a, nevoa: 0xffffff, alavanca: 0x9fd8ff, elevador: 0x9fd8ff, ponte: 0xffe0a0,
                      pharros: 0xffe27a, escada: 0xffe0a0, bau: 0xffcf6a };
  const TINTA_CHAVE = 0xffc23a;
  const modeloInimigo = (tipo) => `c${String(Math.floor(Number(tipo) / 100)).padStart(4, "0")}`;
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
  // Áreas liberadas pelo save: alguma fogueira dela acesa ou você está nela. Área sem fogueira (trecho de mapa, memória)
  // acompanha a rota: liberada se vem antes da área liberada mais adiante.
  // Tamanho da porta pelo nome do modelo: dupla, grande ou pesada é mais larga; portão e grade, um meio-termo.
  function dimsObjeto(o) {
    const n = o.nome || "";
    if (o.cat === "porta" && /large|heavy|king's|double|both|rotunda/i.test(n)) return [4.4, 5.0, 0.4];
    if (o.cat === "porta" && /gate|bars/i.test(n)) return [3.0, 3.4, 0.2];
    return (OBJ[o.cat] || OBJ.porta).dims;
  }
  // Altura do inimigo em metros (para a forma 3D e o tamanho no 2D): chefe visto como inimigo é grande; o resto
  // cresce com o HP (Hollow ~1,8 m; Ruin Sentinel, 2330 HP, ~3 m).
  function alturaInimigo(t) {
    if (t && t.chefe) return 3.4;
    return Math.min(3.6, Math.max(1.8, 1.8 + ((t && t.hp) || 0) / 1600 - 0.25));
  }
  // Raio do inimigo no 2D: meio metro na escala do mapa, com mínimo e máximo em pixels.
  const raioInimigo = (s, t) => Math.min(18, Math.max(3.5, 0.28 * alturaInimigo(t) * s));
  function liberadas(indice, acesas, areaJogador) {
    const ok = new Set(indice.filter((a) => (a.fogueiras || []).some((id) => acesas.has(id)) || a.area === areaJogador).map((a) => a.area));
    const ate = Math.max(-1, ...indice.filter((a) => ok.has(a.area) && (a.ordem ?? 100) < 100).map((a) => a.ordem));
    indice.forEach((a) => { if (!(a.fogueiras || []).length && (a.ordem ?? 100) <= ate) ok.add(a.area); });
    return ok;
  }
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
               modo: "2d", iso: null, interior: false, foco: true, acesas: null, fogChave: undefined, escolhida: false,
               entChave: null, vivo: null, realce: false,
               filtros: { zonas: true, fogueiras: true, chefes: true, npcs: true, plano: true, outros: true, chaves: true,
                          baus: false, objetos: false, inimigos: false } };
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
          <button type="button" class="mp-filtro mp-realce-bt" data-realce aria-pressed="false" title="Inimigos em vermelho forte, com anel pulsando e visíveis através das paredes no 3D (H)">Realçar inimigos</button>
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
              <button type="button" class="mp-iso-tg" data-iso="livre" aria-pressed="false" title="Câmera livre: voar pela área e entrar nos lugares (V)">Livre</button>
            </div>
            <p class="mp-iso-ajuda" data-ajuda="fixa"><kbd>WASD</kbd> andar · <kbd>Q</kbd><kbd>E</kbd> girar · <kbd>R</kbd><kbd>F</kbd> inclinar · <kbd>Shift</kbd> rápido · botão direito arrasta: girar · roda: zoom · <kbd>V</kbd> livre</p>
            <p class="mp-iso-ajuda" data-ajuda="livre" hidden><kbd>WASD</kbd> voar · segure e arraste: olhar · <kbd>E</kbd>/<kbd>Espaço</kbd> sobe · <kbd>Q</kbd>/<kbd>C</kbd> desce · <kbd>Shift</kbd> rápido · roda: avançar · <kbd>V</kbd> volta à fixa</p>
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
      <p class="mp-leg"><span class="mp-k mp-k-zonas"></span>zona 1 → última <span class="mp-k mp-k-chefe"></span>chefe <span class="mp-k mp-k-npc"></span>NPC <span class="mp-k mp-k-plano"></span>do plano <span class="mp-k mp-k-outro"></span>item <span class="mp-k mp-k-rota"></span>rota <span class="mp-k mp-k-parada"></span>paradas 1 → última <span class="mp-k mp-k-eu"></span>você <span class="mp-k mp-k-inimigo"></span>inimigo <span class="mp-k mp-k-porta"></span>porta <span class="mp-k mp-k-chave"></span>chave <span class="mp-k mp-k-bau"></span>baú <span class="mp-aviso">rota pelo chão: não sabe se a porta está trancada</span></p>
    </div>`;
    ligar(raiz);
    return carregar("mapas/indice.json").then((indice) => {
      st.indice = Array.isArray(indice) ? indice.filter((a) => AREA_OK.test(a.area)) : [];
      preencherAreas();
      if (!st.indice.length) return vazio("Mapa indisponível. Rode o /buildsmith:build com o DS2 SotFS instalado.");
      if (API && !st.poll) {
        st.poll = setInterval(() => { if (!document.hidden && st.raiz.offsetParent !== null) buscarJogador(); }, POLL_MS);
      }
      // abre onde você está (posição do save); sem servidor ou fora das áreas, a 1ª do plano
      return (API ? buscarJogador() : Promise.resolve()).then(() => {
        if (st.escolhida && st.doc) return null;
        const j = st.jogador;
        return abrirArea(j && st.indice.some((a) => a.area === j.area) ? j.area : st.indice[0].area);
      });
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
    const fogs = novo && Array.isArray(novo.fogueiras) ? novo.fogueiras.filter(Number.isInteger) : null;
    const fogChave = fogs ? fogs.join(",") : null;
    if (chave(novo) === chave(st.jogador) && fogChave === st.fogChave) return;
    const mudouArea = (novo && novo.area) !== (st.jogador && st.jogador.area);
    st.jogador = novo;
    if (fogChave !== st.fogChave || mudouArea) {  // fogueira acesa no jogo: áreas e zonas mudam na hora
      st.fogChave = fogChave;
      st.acesas = fogs ? new Set(fogs) : null;
      preencherAreas();
      if (st.doc) desenharRotaArea();
    }
    mostrarOnde();
    atualizar();
  }

  // Seletor de áreas na ordem da rota; com o save, separado em liberadas e ainda não liberadas.
  function preencherAreas() {
    const sel = st.raiz.querySelector(".mp-area");
    const valor = sel.value;
    const pos = new Map(st.indice.map((a, i) => [a.area, i]));
    const ordenadas = [...st.indice].sort((a, b) => (a.ordem ?? 100) - (b.ordem ?? 100) || pos.get(a.area) - pos.get(b.area));
    const opcao = (a) => `<option value="${esc(a.area)}">${esc(a.nome)}${a.itens_plano ? ` (${a.itens_plano})` : ""}</option>`;
    if (st.acesas) {
      const ok = liberadas(st.indice, st.acesas, st.jogador && st.jogador.area);
      const sim = ordenadas.filter((a) => ok.has(a.area)), nao = ordenadas.filter((a) => !ok.has(a.area));
      sel.innerHTML = `<optgroup label="Liberadas · ${sim.length}">${sim.map(opcao).join("")}</optgroup>`
        + (nao.length ? `<optgroup label="Ainda não liberadas · ${nao.length}">${nao.map(opcao).join("")}</optgroup>` : "");
    } else {
      sel.innerHTML = ordenadas.map(opcao).join("");
    }
    if (valor) sel.value = valor;
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
    const nome = tipo === "item" ? (p.itens[0] ? p.itens[0].nome : "item") : tipo === "inimigo" ? (tipoInimigo(p.tipo).nome || "inimigo")
      : tipo === "objeto" ? nomeObjeto(p) : p.nome;
    return { pos: p.pos, andar: p.andar, zona: p.zona, nome };
  }

  function listaDe(tipo) {
    return { npc: st.doc.npcs, chefe: st.doc.chefes, item: st.doc.itens, inimigo: st.doc.inimigos, fogueira: st.doc.fogueiras,
             objeto: st.doc.objetos || [] }[tipo];
  }
  const nomeObjeto = (o) => (o.chave ? `${(OBJ[o.cat] || OBJ.porta).nome} (${o.chave.nome})` : (OBJ[o.cat] || OBJ.porta).nome);
  // Objeto aparece pelo filtro dele: porta com chave também pelo filtro Chaves; baú pelo Baús.
  function objetoVisivel(o) {
    if (o.cat === "bau") return st.filtros.baus;
    if (o.chave && st.filtros.chaves) return true;
    return st.filtros.objetos;
  }
  const itemVisivel = (p, destaque) => (destaque ? st.filtros.plano : st.filtros.outros) || (p.chave && st.filtros.chaves);

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
    st.entChave = null;
    if (st.iso) st.iso.setEntidades([]);  // as formas da área anterior saem já; as desta entram com o cenário
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
      const acesa = st.acesas ? st.acesas.has(z.fogueira) : null;
      return `<li><button type="button" class="mp-zona-i${acesa === false ? " mp-zona-apagada" : ""}" data-zona="${z.ordem}" aria-pressed="${st.zonaSel === z.ordem}">
        <span class="mp-zn" style="background:${corDe(z.ordem)}">${z.ordem}</span>
        <span class="mp-zt">${esc(z.nome)}${acesa === null ? "" : `<span class="mp-zfog${acesa ? "" : " apagada"}">${acesa ? "fogueira acesa" : "fogueira apagada"}</span>`}${resumo ? `<span class="mp-zr">${esc(resumo)}</span>` : ""}${chefes.map((c) => `<span class="mp-zchefe${c.estado === "derrotado" ? " derrotado" : ""}">Chefe: ${esc(c.nome)}</span>`).join("")}</span>
      </button></li>`;
    }).join("") || '<li class="mp-sem">Área sem fogueira.</li>';
    const por = d.zonas ? d.zonas.ordem_por : "nenhuma";
    const acesas = st.acesas ? d.fogueiras.filter((f) => st.acesas.has(f.id)).length : null;
    st.raiz.querySelector(".mp-nota").textContent = [
      acesas === null || !d.fogueiras.length ? "" : `${acesas} de ${d.fogueiras.length} ${d.fogueiras.length === 1 ? "fogueira acesa" : "fogueiras acesas"} no save.`,
      por === "inicio" ? "Ordem: distância a pé desde a entrada da área. Portas e atalhos podem mudar o caminho."
        : por === "id" ? "Ordem pelo número da fogueira no jogo." : ""].filter(Boolean).join(" ");
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
    sincronizarEntidades();
    atualizar();
  }

  // Formas 3D dos inimigos e objetos visíveis pelos filtros (refeitas só quando a lista muda, não a cada quadro).
  // Inimigo: o modelo do jogo quando a cena trouxe (cXXXX = linha do EnemyParam // 100, virado como o gerador), senão a
  // cápsula; objeto com modelo na cena já está no cenário (o filtro só realça), sem modelo vira a forma de reserva.
  function entidades3d() {
    const out = [];
    if (st.filtros.inimigos) st.doc.inimigos.forEach((e) => {
      const t = tipoInimigo(e.tipo), h = alturaInimigo(t), igual = st.tipoSel && e.tipo === st.tipoSel;
      const forte = st.realce && (!st.tipoSel || igual);
      // realce: cor forte e a passada que atravessa parede, menos no que está acima do corte de interior
      const xray = forte && !(e.pos[1] > st.iso.alturaCorte(e.pos[0], e.pos[2]) + 0.5);
      out.push({ modelo: modeloInimigo(e.tipo), rot: e.rot ? [0, e.rot[1], 0] : null, xray,
                 tinta: igual ? 0xffd27a : st.tipoSel ? 0x5a4a48 : forte ? 0xff7a62 : 0xffffff,
                 forma: "capsula", pos: e.pos, dims: [h * 0.36, h, h * 0.36],
                 cor: igual ? 0xf2c14e : st.tipoSel ? 0x4a2420 : forte ? 0xff3b2b : t.chefe ? 0xd1572f : 0xb8352a });
    });
    // NPC com modelo próprio na cena (Straid, McDuff...): pelo filtro NPCs; sem modelo, só o retrato por cima
    if (st.filtros.npcs) (st.doc.npcs || []).forEach((n) => {
      if (!n.modelo || !st.iso.temModelo(n.modelo)) return;
      out.push({ modelo: n.modelo, pos: n.pos, rot: n.rot ? [0, n.rot[1], 0] : null, tinta: n.plano ? 0xffe2a0 : 0xffffff });
    });
    (st.doc.objetos || []).forEach((o) => {
      const c = OBJ[o.cat];
      if (!c || !objetoVisivel(o) || st.iso.temParte(o.parte)) return;
      out.push({ forma: c.forma, pos: o.pos, rot: o.rot, dims: dimsObjeto(o), base: c.base, transp: c.transp,
                 cor: o.chave ? COR_CHAVE : c.cor });
    });
    return out;
  }
  function realces3d() {
    const cores = {};
    (st.doc.objetos || []).forEach((o) => {
      if (o.parte && OBJ[o.cat] && objetoVisivel(o)) cores[o.parte] = o.chave ? TINTA_CHAVE : TINTA_OBJ[o.cat];
    });
    return cores;
  }
  function sincronizarEntidades() {
    if (!st.iso || !st.doc) return;
    const tres = em3d(), lista = tres ? entidades3d() : [];
    const cena = st.iso.cena ? st.iso.area : "-";
    const chave = `${st.doc.area}|${cena}|${JSON.stringify(st.filtros)}|${st.tipoSel}|${st.realce}|${st.interior}|${st.andar}|${lista.length}`;
    if (chave === st.entChave) return;
    st.entChave = chave;
    st.iso.setEntidades(lista);
    st.iso.realcar(tres ? realces3d() : {});
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
    raiz.querySelector(".mp-iso-sombra").hidden = !tres || !st.foco || !!(st.iso && st.iso.livre);
    raiz.querySelector(".mp-mundo").style.display = tres ? "none" : "";
    raiz.querySelector(".mp-tela").classList.toggle("mp-3d", tres);
    st.iso && st.iso.setAtivo(tres);
    sincronizarEntidades();
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
    // projeção + o que esconder: fora da tela, acima do corte de interior; "longe" do foco e, na câmera livre, o que
    // está atrás de parede ficam apagados e sem nome (senão o chefe da outra sala parece estar na parede da frente)
    const ver = (pos) => {
      const [sx, sy, vis, extra] = paraTela(pos[0], pos[2], pos[1]);
      if (!vis || !dentro(sx, sy) || (extra && extra.cortado)) return null;
      return [sx, sy, extra && extra.longe ? " mp-fora-foco" : extra && extra.atras ? " mp-atras" : ""];
    };
    const retrato = (k, sx, sy, r, src, classe, titulo, rotulo, dados) => {
      const id = `mp-c${k}`;
      clips.push(`<clipPath id="${id}"><circle cx="${f1(sx)}" cy="${f1(sy)}" r="${f1(r)}"/></clipPath>`);
      const img = src && ICONE_OK.test(src) ? `<image href="${esc(src)}" x="${f1(sx - r)}" y="${f1(sy - r)}" width="${f1(2 * r)}" height="${f1(2 * r)}" clip-path="url(#${id})" preserveAspectRatio="xMidYMin slice"/>`
        : `<text class="mp-ini" x="${f1(sx)}" y="${f1(sy + 4)}">${esc(titulo.trim().replace(/^the\s+/i, "").charAt(0))}</text>`;
      return `<g class="${classe}" ${dados} tabindex="0"><title>${esc(titulo)}</title><circle class="mp-fundo" cx="${f1(sx)}" cy="${f1(sy)}" r="${f1(r)}"/>${img}<circle class="mp-aro" cx="${f1(sx)}" cy="${f1(sy)}" r="${f1(r)}"/>${rotulo ? `<text class="mp-rotulo" x="${f1(sx)}" y="${f1(sy + r + 12)}">${esc(rotulo)}</text>` : ""}</g>`;
    };
    // No 3D a forma está no cenário (iso.setEntidades): aqui fica só o alvo do clique, do tamanho dela na tela.
    const alvo3d = (pos, alt) => {
      const [ax, ay] = paraTela(pos[0], pos[2], pos[1]), [bx, by] = paraTela(pos[0], pos[2], pos[1] + alt);
      return [(ax + bx) / 2, (ay + by) / 2, Math.max(7, Math.hypot(ax - bx, ay - by) / 2 + 2), bx, by];
    };
    const badgeChave = (x, y, icone) => `<g class="mp-badge-chave"><circle cx="${f1(x)}" cy="${f1(y)}" r="9"/>${icone && ICONE_OK.test(icone)
      ? `<image href="${esc(icone)}" x="${f1(x - 7)}" y="${f1(y - 7)}" width="14" height="14"/>` : `<path d="M${f1(x - 4)} ${f1(y)}a2.6 2.6 0 1 0 0.1 0M${f1(x - 1.4)} ${f1(y)}h6v2.5M${f1(x + 2.5)} ${f1(y)}v2"/>`}</g>`;
    const glifoObjeto = (o, sx, sy) => {
      const d = dimsObjeto(o), rot = `transform="rotate(${f1(o.rot ? o.rot[1] : 0)} ${f1(sx)} ${f1(sy)})"`;
      if (o.cat === "porta" || o.cat === "nevoa" || o.cat === "escada" || o.cat === "bau") {
        const L = Math.max(o.cat === "bau" ? 9 : 11, d[0] * s), E = Math.max(o.cat === "bau" ? 7 : 3.5, d[2] * s * (o.cat === "bau" ? 1 : 1.8));
        return `<rect class="mp-obj-forma" x="${f1(sx - L / 2)}" y="${f1(sy - E / 2)}" width="${f1(L)}" height="${f1(E)}" rx="1.5" ${rot}/>`;
      }
      if (o.cat === "elevador") return `<circle class="mp-obj-forma" cx="${f1(sx)}" cy="${f1(sy)}" r="${f1(Math.max(6, d[0] * s / 2))}"/><circle class="mp-obj-miolo" cx="${f1(sx)}" cy="${f1(sy)}" r="2"/>`;
      if (o.cat === "alavanca") {
        const r = Math.max(3.5, 0.3 * s);
        return `<line class="mp-obj-haste" x1="${f1(sx)}" y1="${f1(sy)}" x2="${f1(sx + r * 1.6)}" y2="${f1(sy - r * 2.2)}"/><circle class="mp-obj-forma" cx="${f1(sx)}" cy="${f1(sy)}" r="${f1(r)}"/>`;
      }
      return `<rect class="mp-obj-forma" x="${f1(sx - 5)}" y="${f1(sy - 5)}" width="10" height="10" transform="rotate(45 ${f1(sx)} ${f1(sy)})"/>`;
    };
    // objetos antes dos itens: o ícone do item fica por cima do baú dele
    (st.doc.objetos || []).forEach((o, i) => {
      if (!OBJ[o.cat] || !objetoVisivel(o)) return;
      const q = ver(o.pos);
      if (!q) return;
      const [sx, sy, longe] = q;
      const estado = estadoAndar(o.andar, andarSel);
      let corpo;
      if (tres) {
        const d = dimsObjeto(o), [cx, cy, r, tx, ty] = alvo3d(o.pos, (OBJ[o.cat].base || 0) + d[1]);
        corpo = `<circle class="mp-alvo3d" cx="${f1(cx)}" cy="${f1(cy)}" r="${f1(r)}"/>${o.chave ? badgeChave(tx, ty - 10, o.chave.icone) : ""}`;
      } else {
        corpo = glifoObjeto(o, sx, sy) + (o.chave ? badgeChave(sx, sy - Math.max(14, dimsObjeto(o)[1] * s * 0.35), o.chave.icone) : "");
      }
      const rotulo = o.chave && (nomes || tres) && estado === "cheio" && !longe
        ? `<text class="mp-rotulo mp-rotulo-chave" x="${f1(sx)}" y="${f1(sy + 16)}">${esc(o.chave.nome)}</text>` : "";
      partes.push(`<g class="mp-obj mp-obj-${o.cat}${o.chave ? " mp-obj-chave" : ""} ${estado}${longe}" data-tipo="objeto" data-i="${i}" tabindex="0"><title>${esc(nomeObjeto(o) + (o.nome ? ` · ${o.nome}` : ""))}</title>${corpo}${rotulo}</g>`);
    });
    if (st.filtros.inimigos) st.doc.inimigos.forEach((e, i) => {
      const p = ver(e.pos);
      if (!p) return;
      const [sx, sy, longe] = p;
      const t = tipoInimigo(e.tipo), igual = st.tipoSel && e.tipo === st.tipoSel;
      const forte = st.realce && (!st.tipoSel || igual);
      const classe = `mp-inimigo ${estadoAndar(e.andar, andarSel)}${longe}${igual ? " mp-inimigo-sel" : st.tipoSel ? " mp-inimigo-fora" : ""}${t.chefe ? " mp-inimigo-chefe" : ""}${forte ? " mp-inimigo-forte" : ""}`;
      const titulo = `<title>${esc(t.nome || "Inimigo (nome não confirmado)")}</title>`;
      const anel = (x, y, r) => (forte ? `<circle class="mp-realce-anel" cx="${f1(x)}" cy="${f1(y)}" r="${f1(r)}"/>` : "");
      if (tres) {
        const [cx, cy, r] = alvo3d(e.pos, st.iso.alturaModelo(modeloInimigo(e.tipo)) || alturaInimigo(t));
        partes.push(`${anel(cx, cy, Math.max(9, r))}<circle class="mp-alvo3d ${classe}" data-tipo="inimigo" data-i="${i}" tabindex="0" cx="${f1(cx)}" cy="${f1(cy)}" r="${f1(r)}">${titulo}</circle>`);
        return;
      }
      const r = raioInimigo(s, t) * (igual ? 1.25 : 1) * (forte ? 1.35 : 1) + (forte ? 1.5 : 0);
      if (r >= 11 && t.retrato && ICONE_OK.test(t.retrato)) {
        partes.push(anel(sx, sy, r + 3) + retrato(`e${i}`, sx, sy, r, t.retrato, `${classe} mp-inimigo-ret`, t.nome || "Inimigo", "", `data-tipo="inimigo" data-i="${i}"`));
        return;
      }
      partes.push(`${anel(sx, sy, r + 4)}<circle class="${classe}" data-tipo="inimigo" data-i="${i}" tabindex="0" cx="${f1(sx)}" cy="${f1(sy)}" r="${f1(r)}">${titulo}</circle>`);
    });
    st.doc.itens.forEach((p, i) => {
      const destaque = p.plano || (st.destaque && p.item_id === st.destaque);
      if (!itemVisivel(p, destaque)) return;
      const q = ver(p.pos);
      if (!q) return;
      const [sx, sy, longe] = q;
      const estado = estadoAndar(p.andar, andarSel);
      const t = estado === "cheio" ? (destaque ? tam + 4 : tam) : Math.max(12, tam - 8);
      const img = p.icone && ICONE_OK.test(p.icone) ? `<image href="${esc(p.icone)}" x="${f1(sx - t / 2)}" y="${f1(sy - t / 2)}" width="${t}" height="${t}"/>` : `<rect class="mp-losango" x="${f1(sx - t / 4)}" y="${f1(sy - t / 4)}" width="${t / 2}" height="${t / 2}" transform="rotate(45 ${f1(sx)} ${f1(sy)})"/>`;
      const nome = p.itens[0] ? `${p.itens[0].nome}${p.itens[0].qtd > 1 ? ` ×${p.itens[0].qtd}` : ""}${p.itens.length > 1 ? ` +${p.itens.length - 1}` : ""}` : "";
      const chave = p.chave && st.filtros.chaves ? badgeChave(sx + t / 2 + 1, sy - t / 2 - 1, null) : "";
      const jaTem = destaque && temNoSave(p);  // item do plano que o save já mostra no inventário
      const check = jaTem ? `<g class="mp-ja-tem-k"><circle cx="${f1(sx - t / 2 - 1)}" cy="${f1(sy - t / 2 - 1)}" r="7"/><path d="M${f1(sx - t / 2 - 4.5)} ${f1(sy - t / 2 - 1)}l2.5 2.6 4.6-5"/></g>` : "";
      const ondeEsta = p.no === "bau" ? " (baú)" : p.no === "cadaver" ? " (cadáver)" : "";
      partes.push(`<g class="mp-item ${destaque ? "mp-do-plano" : ""}${jaTem ? " mp-ja-tem" : ""}${p.chave ? " mp-item-chave" : ""}${p.no === "bau" ? " mp-no-bau" : ""} ${estado}${longe}" data-tipo="item" data-i="${i}" tabindex="0"><title>${esc(nome + ondeEsta + (jaTem ? " (você já tem)" : ""))}</title><rect class="mp-moldura" x="${f1(sx - t / 2 - 2)}" y="${f1(sy - t / 2 - 2)}" width="${t + 4}" height="${t + 4}" rx="3"/>${img}${chave}${check}${nomes && estado === "cheio" && !longe ? `<text class="mp-rotulo" x="${f1(sx)}" y="${f1(sy + t / 2 + 12)}">${esc(nome)}</text>` : ""}</g>`);
    });
    if (st.filtros.fogueiras) st.doc.fogueiras.forEach((f, i) => {
      const q = ver(f.pos);
      if (!q) return;
      const [sx, sy, longe] = q;
      const estado = estadoAndar(f.andar, andarSel), t = estado === "cheio" ? tam + 2 : Math.max(12, tam - 8);
      const badge = f.zona && st.filtros.zonas ? `<circle class="mp-badge" cx="${f1(sx - t / 2)}" cy="${f1(sy - t / 2)}" r="8" fill="${corDe(f.zona)}"/><text class="mp-badge-n" x="${f1(sx - t / 2)}" y="${f1(sy - t / 2 + 3.5)}">${f.zona}</text>` : "";
      const apagada = st.acesas && !st.acesas.has(f.id) ? " mp-fog-apagada" : "";
      partes.push(`<g class="mp-fog ${estado}${longe}${apagada}" data-tipo="fogueira" data-i="${i}" tabindex="0"><title>${esc(`${f.zona ? nomeZona(f.zona) : f.nome}${apagada ? " (apagada)" : ""}`)}</title><image href="icons/fogueira.png" x="${f1(sx - t / 2)}" y="${f1(sy - t / 2)}" width="${t}" height="${t}"/>${badge}${(nomes || s >= 1.5) && estado === "cheio" && !longe ? `<text class="mp-rotulo mp-rotulo-fog" x="${f1(sx)}" y="${f1(sy - t / 2 - 5)}">${esc(f.zona ? `${f.zona} · ${f.nome}` : f.nome)}</text>` : ""}</g>`);
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
    st.raiz.querySelector(".mp-tela").classList.toggle("mp-realce-on", st.realce && st.filtros.inimigos);
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
      const foto = t.retrato && ICONE_OK.test(t.retrato) ? `<img class="mp-pop-foto" src="${esc(t.retrato)}" alt="" width="40" height="40">` : "";
      const origem = { jogo: "Nome pela linha do jogo", modelo: "Nome pelo modelo do jogo", wiki: "Nome pela wiki" }[t.fonte] || "Nome";
      corpo = `<p class="mp-pop-tit">${foto}${t.nome ? esc(t.nome) : "Inimigo"}</p>
        ${t.nome ? "" : '<p class="mp-pop-sub">Nome não confirmado: nem a linha do jogo, nem o modelo, nem a wiki deram um nome só.</p>'}
        ${t.chefe ? '<p class="mp-pop-sub">Chefe de outra área, aqui como inimigo comum.</p>' : ""}
        ${numeros ? `<p class="mp-pop-sub">${numeros} <span class="mp-fonte">(jogo)</span></p>` : ""}
        ${t.drops && t.drops.length ? `<p class="mp-pop-sub">Drops (jogo): ${esc(t.drops.join(", "))}</p>` : ""}
        ${t.prova ? `<p class="mp-prova">${origem}: ${esc(t.prova)}</p>` : ""}
        <p><button type="button" class="pesq" data-iguais="${esc(p.tipo)}">${st.tipoSel === p.tipo ? "Parar de destacar" : `Destacar os ${fmt.format(t.n || 1)} iguais`}</button></p>
        ${link ? `<a href="${esc(link)}" target="_blank" rel="noopener noreferrer">página na wiki</a>` : ""}`;
    } else if (tipo === "objeto") {
      const c = OBJ[p.cat] || OBJ.porta;
      let extra = "";
      if (p.chave) {
        const k = p.chave, link = linkSeguro(k.wiki);
        const onde = (k.onde || []).filter((x) => AREA_OK.test(x.area)).map((x) => `<li>${esc(x.nome)} <button type="button" class="pesq" data-ir-lote="${esc(x.area)}|${Number(x.lote)}">ver no mapa</button></li>`).join("");
        extra = `<p class="mp-pop-chave">${k.icone && ICONE_OK.test(k.icone) ? `<img src="${esc(k.icone)}" alt="" width="24" height="24">` : ""}Abre com <strong>${esc(k.nome)}</strong></p>
          ${onde ? `<p class="mp-pop-sub">Onde pegar a chave:</p><ul>${onde}</ul>` : '<p class="mp-pop-sub">A chave não está no chão das áreas do mapa (loja, NPC ou drop).</p>'}
          ${link ? `<a href="${esc(link)}" target="_blank" rel="noopener noreferrer">chave na wiki</a>` : ""}
          <p class="mp-prova">Chave pelo nome do modelo da porta (Smithbox), conferida na lista de itens do jogo.</p>`;
      } else if (p.cat === "bau") {
        const conteudo = ((st.doc.itens.find((x) => x.lote === p.lote) || {}).itens) || [];
        extra = conteudo.length ? `<ul>${conteudo.map((it) => `<li>${esc(it.nome)}${it.qtd > 1 ? ` <span class="mp-qtd">×${it.qtd}</span>` : ""}</li>`).join("")}</ul>`
          : '<p class="mp-pop-sub">O jogo não liga item a este baú.</p>';
      }
      const reserva = em3d() && st.iso.cena && !st.iso.temParte(p.parte)
        ? `<p class="mp-prova">Forma de reserva: o modelo do jogo${p.modelo ? ` (${esc(p.modelo)})` : ""} não entrou na cena${st.iso.motivoModelo(p.modelo) ? `: ${esc(st.iso.motivoModelo(p.modelo))}` : ""}.</p>` : "";
      corpo = `<p class="mp-pop-tit">${esc(c.nome)}</p>${p.nome ? `<p class="mp-pop-sub">${esc(p.nome)} <span class="mp-fonte">(modelo do jogo)</span></p>` : ""}<p class="mp-pop-sub">${esc(OBJ_TEXTO[p.cat] || "")}</p>${extra}${reserva}`;
    } else if (tipo === "fogueira") {
      const acesa = st.acesas ? (st.acesas.has(p.id) ? " · acesa no save" : " · ainda apagada") : "";
      corpo = `<p class="mp-pop-tit">${esc(p.nome)}</p><p class="mp-pop-sub">Fogueira${p.zona ? ` da zona ${esc(nomeZona(p.zona))}` : ""}${acesa}</p>`;
    } else {
      const no = p.no === "bau" ? "Dentro de um baú." : p.no === "cadaver" ? "Num cadáver." : "";
      const V = window.buildsmithVivo, tem = st.vivo && V ? p.itens.map((it) => [it.nome, V.itemNoSave(it.nome, st.vivo)]).filter(([, x]) => x) : [];
      corpo = `<ul>${p.itens.map((it) => `<li>${esc(it.nome)}${it.qtd > 1 ? ` <span class="mp-qtd">×${it.qtd}</span>` : ""}</li>`).join("")}</ul>${no ? `<p class="mp-pop-sub">${no}</p>` : ""}${tem.length ? `<p class="mp-pop-sub mp-pop-tem">Você já tem: ${tem.map(([n, x]) => `${esc(n)}${x.qtd > 1 ? ` ×${fmt.format(x.qtd)}` : ""}`).join(", ")} <span class="mp-fonte">(save)</span></p>` : ""}${p.chave ? '<p class="mp-pop-sub">É uma chave: abre porta, portão ou cela.</p>' : ""}${p.item_id ? `<a class="req-link" href="#item-${esc(p.item_id)}" data-goto-item="${esc(p.item_id)}">ver em Onde pegar</a>` : ""}`;
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
                          KeyV: () => alternarLivre(),
                          KeyN: () => st.iso.norte(), PageUp: () => trocarAndar(1), PageDown: () => trocarAndar(-1),
                          Home: () => enquadrarTudo() };
        if (acoes3d[ev.code] && !ev.ctrlKey && !ev.metaKey && !ev.altKey) { ev.preventDefault(); acoes3d[ev.code](); return; }
      }
      if ((ev.key === "h" || ev.key === "H") && !ev.ctrlKey && !ev.metaKey && !ev.altKey) { ev.preventDefault(); alternarRealce(); return; }
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
        else if (acao === "livre") alternarLivre();
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
      if (ev.target.closest("[data-realce]")) { alternarRealce(); return; }
      const f = ev.target.closest("[data-filtro]");
      if (f) {
        st.filtros[f.dataset.filtro] = !st.filtros[f.dataset.filtro];
        f.setAttribute("aria-pressed", String(st.filtros[f.dataset.filtro]));
        if (f.dataset.filtro === "zonas") desenharChao();
        sincronizarEntidades();
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
        sincronizarEntidades();
        atualizar();
        return;
      }
      const irLote = ev.target.closest("[data-ir-lote]");
      if (irLote) {
        const [area, lote] = irLote.dataset.irLote.split("|");
        irParaLote(area, Number(lote));
        return;
      }
      if (ev.target.closest(".mp-pop-x")) fecharPop();
    });
    raiz.querySelector(".mp-area").addEventListener("change", (ev) => { st.escolhida = true; abrirArea(ev.target.value); });
    if (window.ResizeObserver) new ResizeObserver(() => { if (st.iso) st.iso.redimensionar(); atualizar(); }).observe(tela);
  }

  // Realçar inimigos: liga o filtro Inimigos junto; desligar o filtro não apaga a escolha do realce.
  function alternarRealce() {
    st.realce = !st.realce;
    if (st.realce && !st.filtros.inimigos) {
      st.filtros.inimigos = true;
      st.raiz.querySelector('[data-filtro="inimigos"]').setAttribute("aria-pressed", "true");
    }
    st.raiz.querySelector("[data-realce]").setAttribute("aria-pressed", String(st.realce));
    sincronizarEntidades();
    atualizar();
  }

  function alternarLivre() {
    const on = st.iso.alternarLivre();
    const ui = st.raiz.querySelector(".mp-iso-ui");
    ui.querySelector('[data-iso="livre"]').setAttribute("aria-pressed", String(on));
    ui.querySelector('[data-ajuda="fixa"]').hidden = on;
    ui.querySelector('[data-ajuda="livre"]').hidden = !on;
    st.raiz.querySelector(".mp-iso-sombra").hidden = on || !st.foco;
    atualizar();
  }

  // Save ao vivo (pagina.js): marca no mapa os itens do plano que você já tem.
  function temNoSave(p) {
    const V = typeof window !== "undefined" && window.buildsmithVivo;
    return Boolean(st.vivo && V && p.itens.some((it) => V.itemNoSave(it.nome, st.vivo)));
  }
  function setVivo(v) {
    const V = window.buildsmithVivo;
    st.vivo = v && V ? V.indice(v) : null;
    if (st.raiz && st.doc) atualizar();
  }

  // "ver no mapa" da chave de uma porta: abre a área do lote e mostra o item.
  async function irParaLote(area, lote) {
    if (!AREA_OK.test(area)) return;
    st.escolhida = true;
    if (!st.doc || st.doc.area !== area) await abrirArea(area);
    if (!st.doc || st.doc.area !== area) return;
    const i = st.doc.itens.findIndex((x) => x.lote === lote);
    if (i < 0) return;
    const p = st.doc.itens[i];
    if (p.andar != null) st.andar = p.andar;
    const tela = st.raiz.querySelector(".mp-tela");
    st.vista = ajustar(caixa([[p.pos[0], p.pos[2]]]), tela.clientWidth, tela.clientHeight, 40);
    desenharChao();
    sincronizarAndarIso();
    vistaParaIso(true);
    atualizar();
    mostrarPop("item", i);
  }

  function alternarFoco() {
    st.foco = !st.foco;
    if (st.iso) st.iso.setFoco(st.foco);
    st.raiz.querySelector('[data-iso="foco"]').setAttribute("aria-pressed", String(st.foco));
    st.raiz.querySelector(".mp-iso-sombra").hidden = st.modo !== "iso" || !st.foco || !!(st.iso && st.iso.livre);
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
    st.escolhida = true;
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

  window.buildsmithMapa = { montar, ver, setVivo, _teste: { caixa, ajustar, regua, tamanhoIcone, estadoAndar, corZona, andarDe, tintaParada, pino, trechosTela, liberadas,
                                                   dimsObjeto, alturaInimigo, raioInimigo, iso: () => st.iso } };
})();
