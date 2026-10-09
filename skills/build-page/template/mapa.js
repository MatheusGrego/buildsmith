(function () {
  // Mapa isométrico da área do alvo: chão do navmesh do jogo (faixas por altura), fogueiras, passos numerados,
  // item no fim e rota pelo chão. Dados: plano.*.mapa (pontos e trechos) + mapas/<area>.json (recorte da área).
  const COS = Math.cos(Math.PI / 6), SIN = Math.sin(Math.PI / 6);
  const MARGEM = 25;
  const ALTURA = 8;  // metros acima e abaixo dos pontos e da rota: outros andares ficam de fora
  const FAIXAS = 6;
  const areas = {};
  const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const fmt = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 0 });
  const iso = (p) => [(p[0] - p[2]) * COS, (p[0] + p[2]) * SIN - p[1]];
  const AREA_OK = /^m\d\d_\d\d_\d\d_\d\d$/;

  function carregar(area) {
    if (!AREA_OK.test(area)) return Promise.resolve(null);
    if (!areas[area]) areas[area] = fetch(`mapas/${area}.json`, { cache: "no-store" }).then((r) => (r.ok ? r.json() : null)).catch(() => null);
    return areas[area];
  }

  function svgMapa(area, mapa) {
    const pts = mapa.pontos.map((p) => p.pos).concat(...mapa.trechos.filter(Boolean));
    if (!pts.length) return "";
    const xs = pts.map((p) => p[0]), zs = pts.map((p) => p[2]);
    const x0 = Math.min(...xs) - MARGEM, x1 = Math.max(...xs) + MARGEM, z0 = Math.min(...zs) - MARGEM, z1 = Math.max(...zs) + MARGEM;
    const hs = pts.map((p) => p[1]);
    const h0 = Math.min(...hs) - ALTURA, h1 = Math.max(...hs) + ALTURA;
    const dentro = (x, z) => x >= x0 && x <= x1 && z >= z0 && z <= z1;
    const naAltura = (t) => { const h = (t[0][1] + t[1][1] + t[2][1]) / 3; return h >= h0 && h <= h1; };
    const tris = [];
    (area.malhas || []).forEach((m) => {
      const v = m.v, f = m.f;
      for (let i = 0; i + 2 < f.length; i += 3) {
        const t = [f[i], f[i + 1], f[i + 2]].map((k) => [v[3 * k], v[3 * k + 1], v[3 * k + 2]]);
        if (t.some((p) => dentro(p[0], p[2])) && naAltura(t)) tris.push(t);
      }
    });
    const todos = tris.flat().concat(pts);
    const proj = todos.map(iso);
    const minX = Math.min(...proj.map((p) => p[0])) - 12, maxX = Math.max(...proj.map((p) => p[0])) + 12;
    const minY = Math.min(...proj.map((p) => p[1])) - 18, maxY = Math.max(...proj.map((p) => p[1])) + 12;
    const ys = tris.map((t) => (t[0][1] + t[1][1] + t[2][1]) / 3);
    const yLo = Math.min(...ys, 0), yHi = Math.max(...ys, 1);
    const faixas = Array.from({ length: FAIXAS }, () => []);
    tris.forEach((t, i) => {
      const b = Math.min(FAIXAS - 1, Math.floor((ys[i] - yLo) / ((yHi - yLo) || 1) * FAIXAS));
      faixas[b].push("M" + t.map((p) => iso(p).map((c) => c.toFixed(1)).join(" ")).join("L") + "Z");
    });
    const chao = faixas.map((d, b) => d.length ? `<path class="mp-chao b${b}" d="${d.join("")}"/>` : "").join("");
    const fogueiras = (area.fogueiras || []).filter((f) => dentro(f.pos[0], f.pos[2]) && f.pos[1] >= h0 && f.pos[1] <= h1 && !mapa.pontos.some((p) => p.tipo === "fogueira" && p.ref === f.id)).map((f) => {
      const [x, y] = iso(f.pos);
      return `<g class="mp-fog"><title>${esc(f.nome)}</title><image href="icons/fogueira.png" x="${(x - 5).toFixed(1)}" y="${(y - 10).toFixed(1)}" width="10" height="10"/><text x="${(x + 7).toFixed(1)}" y="${(y - 2).toFixed(1)}">${esc(f.nome)}</text></g>`;
    }).join("");
    const rota = mapa.trechos.map((t) => t ? `<polyline class="mp-rota" points="${t.map((p) => iso(p).map((c) => c.toFixed(1)).join(",")).join(" ")}"/>` : "").join("");
    const ultimo = mapa.pontos.length - 1;
    const marcas = mapa.pontos.map((p, i) => {
      const [x, y] = iso(p.pos);
      const titulo = `${p.n}. ${p.nome}`;
      if (p.tipo === "fogueira") {
        return `<g class="mp-ponto mp-partida" transform="translate(${x.toFixed(1)} ${y.toFixed(1)})"><title>${esc(titulo)}</title><circle r="9"/><image href="icons/fogueira.png" x="-7" y="-8" width="14" height="14"/><text class="mp-n" x="11" y="-6">${p.n}</text></g>`;
      }
      const fim = i === ultimo && p.tipo === "item";
      return `<g class="mp-ponto${fim ? " mp-fim" : ""}" transform="translate(${x.toFixed(1)} ${y.toFixed(1)})"><title>${esc(titulo)}</title>${fim ? '<rect x="-6" y="-6" width="12" height="12" transform="rotate(45)"/>' : '<circle r="7"/>'}<text y="3.5">${p.n}</text></g>`;
    }).join("");
    const resumo = mapa.pontos.map((p) => `${p.n}. ${p.nome}`).join("; ");
    const caminho = (mapa.areas || []).length > 1 ? `<p class="mp-areas">${mapa.areas.map(esc).join(" &#8594; ")}</p>` : "";
    const lista = mapa.pontos.map((p) => `<li><span class="mp-li-n">${p.n}</span>${esc(p.nome)}</li>`).join("");
    const semCaminho = mapa.trechos.some((t) => !t) ? '<span class="neg">trecho sem caminho pelo chão</span>' : "";
    return `<figure class="mapa">${caminho}
      <svg viewBox="${minX.toFixed(1)} ${minY.toFixed(1)} ${(maxX - minX).toFixed(1)} ${(maxY - minY).toFixed(1)}" role="img" aria-label="${esc(`${mapa.nome}: ${resumo}`)}" preserveAspectRatio="xMidYMid meet">${chao}${fogueiras}${rota}${marcas}</svg>
      <figcaption class="mp-leg"><ol class="mp-lista">${lista}</ol>
        <span class="mp-info">${esc(mapa.nome)} · ${fmt.format(mapa.metros)} m pelo chão ${semCaminho}</span>
        <span class="mp-aviso">rota pelo chão; portas e alavancas não aparecem</span></figcaption>
    </figure>`;
  }

  async function desenhar(slot, mapa) {
    if (!slot) return;
    if (!mapa || !Array.isArray(mapa.pontos) || !mapa.pontos.length) { slot.hidden = true; slot.innerHTML = ""; return; }
    slot.hidden = false;
    const pedido = (slot.dataset.pedido = String(Math.random()));
    slot.innerHTML = '<figure class="mapa"><p class="empty">Carregando o mapa…</p></figure>';
    const area = await carregar(mapa.area);
    if (slot.dataset.pedido !== pedido) return;  // outra fonte foi escolhida enquanto carregava
    slot.innerHTML = area ? svgMapa(area, mapa) : '<figure class="mapa"><p class="empty">Mapa indisponível.</p></figure>';
  }

  window.buildsmithMapa = function (app, plano) {
    (plano.passos || []).forEach((s) => desenhar(app.querySelector(`[data-mapa-passo="${CSS.escape(s.id)}"]`), s.mapa));
  };
  window.buildsmithMapaFonte = function (app, plano, itemId, idx) {
    const item = (plano.itens || []).find((it) => it.id === itemId);
    const fonte = item && (item.fontes || [])[idx];
    desenhar(app.querySelector(`[data-mapa-item="${CSS.escape(itemId)}"]`), fonte && fonte.mapa);
  };
})();
