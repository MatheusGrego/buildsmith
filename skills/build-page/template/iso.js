(function (raiz, fabrica) {
  // Vista 3D (isométrica) da área com o cenário do jogo, usada pela seção Mapa (mapa.js).
  // Câmera de espectador ortográfica: arrastar move pelo chão (o ponto agarrado fica sob o cursor), botão direito ou
  // Alt+arrastar gira e inclina, roda faz zoom no cursor, WASD/setas andam, Q/E giram, R/F inclinam, Shift acelera.
  // Interior: corta o que está acima do chão do andar escolhido (altura do navmesh + folga): dá para ver dentro de
  // cavernas e prédios em qualquer ângulo. Foco: o que está longe do centro da vista escurece e perde a cor.
  // Livre: câmera de espectador em perspectiva (voa pela área e entra nos lugares): WASD anda para onde olha, segurar
  // o botão do mouse e arrastar olha em volta, E/Espaço sobe, Q/C desce, roda anda para a frente, Shift acelera.
  // Entidades (setEntidades): inimigos, portas, baús, alavancas, elevadores... como formas simples em metros, na
  // posição e rotação do jogo, com o mesmo corte de interior e foco do cenário.
  // Coordenadas: tudo que entra e sai daqui está nas do jogo (x, y, z). O jogo é mão esquerda; o mundo é espelhado em z
  // para o three.js, e com giro 0 o norte do mapa 2D (+z) fica para cima, como no 2D.
  if (typeof module === "object" && module.exports) module.exports = fabrica();
  else raiz.MapaIsometrico = fabrica();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  const GRAU = Math.PI / 180;
  const INCL_MIN = 15 * GRAU, INCL_MAX = 89.5 * GRAU, INCL_PADRAO = 55 * GRAU;
  const VISTA_MIN = 8, VISTA_MAX = 2500;  // altura da vista em metros
  const FOLGA_CORTE = 3.2;                // corte de interior: metros acima do chão do andar
  const CELULA = 1.5;                     // grade de alturas do chão (metros)
  const SUAVE = 14;                       // quanto maior, mais rápido a câmera chega no alvo
  const FUNDO = 0x0c0c0d;
  const COR_SEM_TEXTURA = 0x6b665e;
  const TECLAS = new Set(["KeyW", "KeyA", "KeyS", "KeyD", "KeyQ", "KeyE", "KeyR", "KeyF", "ArrowUp", "ArrowDown",
    "ArrowLeft", "ArrowRight", "ShiftLeft", "ShiftRight", "Equal", "Minus", "NumpadAdd", "NumpadSubtract"]);
  const TECLAS_LIVRE = new Set([...TECLAS, "Space", "KeyC"]);
  const FOV_LIVRE = 60, PITCH_MAX = 89 * GRAU, VEL_LIVRE = 9;  // graus; limite de olhar para cima/baixo; m/s

  // ---- funções puras (testadas no node) ------------------------------------------------------------
  // Direções no chão (x, z do jogo) para um giro: frente (para onde a câmera olha) e direita da tela.
  function eixos(giro) {
    return { frente: [Math.sin(giro), Math.cos(giro)], direita: [Math.cos(giro), -Math.sin(giro)] };
  }
  // Ponto do chão (na altura do alvo) sob um pixel, relativo ao alvo: ox para a direita, oy para baixo, em pixels.
  function chaoDoPixel(giro, incl, mpp, ox, oy) {
    const { frente, direita } = eixos(giro);
    const k = mpp / Math.max(Math.sin(incl), 0.2);
    return [direita[0] * ox * mpp - frente[0] * oy * k, direita[1] * ox * mpp - frente[1] * oy * k];
  }
  // Posição da câmera (coordenadas do jogo) olhando o alvo a uma distância.
  function posicaoCamera(alvo, giro, incl, dist) {
    const { frente } = eixos(giro);
    const ch = Math.cos(incl) * dist;
    return [alvo[0] - frente[0] * ch, alvo[1] + Math.sin(incl) * dist, alvo[2] - frente[1] * ch];
  }
  const angulo = (a) => { const r = a % (2 * Math.PI); return r < -Math.PI ? r + 2 * Math.PI : r > Math.PI ? r - 2 * Math.PI : r; };

  // Matriz 4×4 (coluna a coluna) de uma entidade em coordenadas do jogo: T(pos) · Ry · Rz · Rx (rotação do MSB, em
  // graus, a mesma ordem das peças de mapa) · T(0, base·altura, 0) · S(dims), para uma forma de lado 1 centrada na
  // origem: base 0.5 apoia a forma no chão em pos.
  function matrizEntidade(pos, rot, dims, base = 0.5) {
    const [ax, ay, az] = (rot || [0, 0, 0]).map((a) => a * GRAU);
    const cx = Math.cos(ax), sx = Math.sin(ax), cy = Math.cos(ay), sy = Math.sin(ay), cz = Math.cos(az), sz = Math.sin(az);
    const Rx = [[1, 0, 0], [0, cx, -sx], [0, sx, cx]], Ry = [[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]], Rz = [[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]];
    const mul = (a, b) => a.map((_, i) => [0, 1, 2].map((j) => a[i][0] * b[0][j] + a[i][1] * b[1][j] + a[i][2] * b[2][j]));
    const R = mul(mul(Ry, Rz), Rx);
    const m = new Array(16).fill(0);
    for (let col = 0; col < 3; col++) for (let lin = 0; lin < 3; lin++) m[col * 4 + lin] = R[lin][col] * dims[col];
    const sobe = dims[1] * base;
    m[12] = pos[0] + R[0][1] * sobe; m[13] = pos[1] + R[1][1] * sobe; m[14] = pos[2] + R[2][1] * sobe; m[15] = 1;
    return m;
  }
  // Direção do olhar da câmera livre (coordenadas do jogo): yaw 0 = norte (+z), como o giro da câmera fixa.
  function direcaoLivre(yaw, pitch) {
    return [Math.sin(yaw) * Math.cos(pitch), Math.sin(pitch), Math.cos(yaw) * Math.cos(pitch)];
  }

  // Grade de alturas do chão andável: em cada célula, a maior altura dos triângulos que a cobrem (NaN = sem chão).
  // filtro(yMin, yMax) escolhe os triângulos (por exemplo, só os de um andar).
  function gradeAlturas(verts, tris, filtro, cel = CELULA) {
    let x0 = Infinity, z0 = Infinity, x1 = -Infinity, z1 = -Infinity;
    const sel = [];
    for (let i = 0; i < tris.length; i += 3) {
      const a = tris[i] * 3, b = tris[i + 1] * 3, c = tris[i + 2] * 3;
      const ya = verts[a + 1], yb = verts[b + 1], yc = verts[c + 1];
      if (filtro && !filtro(Math.min(ya, yb, yc), Math.max(ya, yb, yc))) continue;
      sel.push(a, b, c);
      x0 = Math.min(x0, verts[a], verts[b], verts[c]); x1 = Math.max(x1, verts[a], verts[b], verts[c]);
      z0 = Math.min(z0, verts[a + 2], verts[b + 2], verts[c + 2]); z1 = Math.max(z1, verts[a + 2], verts[b + 2], verts[c + 2]);
    }
    if (!sel.length) return null;
    const borda = 6 * cel;
    x0 -= borda; z0 -= borda; x1 += borda; z1 += borda;
    const larg = Math.max(1, Math.ceil((x1 - x0) / cel)), alt = Math.max(1, Math.ceil((z1 - z0) / cel));
    const h = new Float32Array(larg * alt).fill(NaN);
    const marcar = (i, j, y) => {
      if (i < 0 || j < 0 || i >= larg || j >= alt) return;
      const k = j * larg + i;
      if (!(h[k] >= y)) h[k] = y;
    };
    for (let t = 0; t < sel.length; t += 3) {
      const A = sel[t], B = sel[t + 1], C = sel[t + 2];
      const ax = verts[A], az = verts[A + 2], bx = verts[B], bz = verts[B + 2], cx = verts[C], cz = verts[C + 2];
      const den = (bz - cz) * (ax - cx) + (cx - bx) * (az - cz);
      const i0 = Math.floor((Math.min(ax, bx, cx) - x0) / cel), i1 = Math.floor((Math.max(ax, bx, cx) - x0) / cel);
      const j0 = Math.floor((Math.min(az, bz, cz) - z0) / cel), j1 = Math.floor((Math.max(az, bz, cz) - z0) / cel);
      if (Math.abs(den) > 1e-9) {
        for (let j = j0; j <= j1; j++) {
          const pz = z0 + (j + 0.5) * cel;
          for (let i = i0; i <= i1; i++) {
            const px = x0 + (i + 0.5) * cel;
            const l1 = ((bz - cz) * (px - cx) + (cx - bx) * (pz - cz)) / den;
            const l2 = ((cz - az) * (px - cx) + (ax - cx) * (pz - cz)) / den;
            const l3 = 1 - l1 - l2;
            if (l1 < -0.02 || l2 < -0.02 || l3 < -0.02) continue;
            marcar(i, j, l1 * verts[A + 1] + l2 * verts[B + 1] + l3 * verts[C + 1]);
          }
        }
      }
      for (const V of [A, B, C]) marcar(Math.floor((verts[V] - x0) / cel), Math.floor((verts[V + 2] - z0) / cel), verts[V + 1]);
    }
    return { x0, z0, cel, larg, alt, h };
  }
  // Espalha o chão para as células vizinhas sem chão (paredes coladas no chão são cortadas na mesma altura).
  function dilatar(g, passos) {
    for (let p = 0; p < passos; p++) {
      const novo = g.h.slice();
      for (let j = 0; j < g.alt; j++) {
        for (let i = 0; i < g.larg; i++) {
          const k = j * g.larg + i;
          if (!Number.isNaN(g.h[k])) continue;
          let m = NaN;
          for (let dj = -1; dj <= 1; dj++) {
            for (let di = -1; di <= 1; di++) {
              const ii = i + di, jj = j + dj;
              if (ii < 0 || jj < 0 || ii >= g.larg || jj >= g.alt) continue;
              const v = g.h[jj * g.larg + ii];
              if (!(m >= v)) m = Number.isNaN(v) ? m : v;
            }
          }
          novo[k] = m;
        }
      }
      g.h = novo;
    }
    return g;
  }
  // Altura do chão num ponto (bilinear entre as células com chão); null fora do chão.
  function alturaNaGrade(g, x, z) {
    if (!g) return null;
    const cx = (x - g.x0) / g.cel - 0.5, cz = (z - g.z0) / g.cel - 0.5;
    const i = Math.floor(cx), j = Math.floor(cz), fx = cx - i, fz = cz - j;
    let soma = 0, peso = 0;
    for (const [di, dj, w] of [[0, 0, (1 - fx) * (1 - fz)], [1, 0, fx * (1 - fz)], [0, 1, (1 - fx) * fz], [1, 1, fx * fz]]) {
      const ii = i + di, jj = j + dj;
      if (ii < 0 || jj < 0 || ii >= g.larg || jj >= g.alt) continue;
      const v = g.h[jj * g.larg + ii];
      if (Number.isNaN(v) || w <= 0) continue;
      soma += v * w; peso += w;
    }
    return peso > 1e-6 ? soma / peso : null;
  }
  // DDS DXT1/DXT3/DXT5 (o que o extrator grava) -> níveis de mipmap prontos para a CompressedTexture.
  function lerDDS(buf) {
    if (!buf || buf.byteLength < 128) return null;
    const dv = new DataView(buf);
    if (dv.getUint32(0, true) !== 0x20534444) return null;
    const flags = dv.getUint32(8, true), alt = dv.getUint32(12, true), larg = dv.getUint32(16, true);
    const mips = flags & 0x20000 ? Math.max(1, dv.getUint32(28, true)) : 1;
    const formato = String.fromCharCode(dv.getUint8(84), dv.getUint8(85), dv.getUint8(86), dv.getUint8(87));
    const bloco = formato === "DXT1" ? 8 : formato === "DXT3" || formato === "DXT5" ? 16 : 0;
    if (!bloco || !larg || !alt) return null;
    const niveis = [];
    let off = 128, w = larg, h = alt;
    for (let i = 0; i < mips; i++) {
      const tam = Math.max(1, (w + 3) >> 2) * Math.max(1, (h + 3) >> 2) * bloco;
      if (off + tam > buf.byteLength) break;
      niveis.push({ data: new Uint8Array(buf, off, tam), width: w, height: h });
      off += tam; w = Math.max(1, w >> 1); h = Math.max(1, h >> 1);
    }
    return niveis.length ? { formato, largura: larg, altura: alt, niveis } : null;
  }

  // ---- shader: corte de interior, foco e limite da área (injetado no MeshLambertMaterial) ------------------------
  const GLSL_VERT_DECL = "varying vec3 vBsMundo;\n";
  const GLSL_VERT = `
  {
    vec4 bsP = vec4( transformed, 1.0 );
    #ifdef USE_INSTANCING
      bsP = instanceMatrix * bsP;
    #endif
    vBsMundo = ( modelMatrix * bsP ).xyz;
  }`;
  const GLSL_FRAG_DECL = `
varying vec3 vBsMundo;
uniform vec3 uBsFoco;
uniform float uBsRaio;
uniform float uBsFocoOn;
uniform float uBsCorteOn;
uniform float uBsCortePlano;
uniform float uBsAndarMin;
uniform sampler2D uBsCorteMapa;
uniform vec3 uBsCorteRet;
uniform vec2 uBsCorteTam;
uniform vec4 uBsLimite;
uniform float uBsMargem;
uniform vec3 uBsFundo;
float bsAmostra( vec2 c ) {
  ivec2 t = ivec2( clamp( c, vec2( 0.0 ), uBsCorteTam - 1.0 ) );
  return texelFetch( uBsCorteMapa, t, 0 ).r;
}
float bsAlturaCorte( vec3 g ) {
  vec2 c = ( g.xz - uBsCorteRet.xy ) / uBsCorteRet.z - 0.5;
  if ( c.x < -1.0 || c.y < -1.0 || c.x > uBsCorteTam.x || c.y > uBsCorteTam.y ) return uBsCortePlano;
  vec2 b = floor( c ), f = c - b;
  vec4 h = vec4( bsAmostra( b ), bsAmostra( b + vec2( 1.0, 0.0 ) ), bsAmostra( b + vec2( 0.0, 1.0 ) ), bsAmostra( b + vec2( 1.0 ) ) );
  vec4 w = vec4( ( 1.0 - f.x ) * ( 1.0 - f.y ), f.x * ( 1.0 - f.y ), ( 1.0 - f.x ) * f.y, f.x * f.y ) * step( -9000.0, h );
  float sw = w.x + w.y + w.z + w.w;
  return sw < 1e-4 ? uBsCortePlano : dot( h, w ) / sw + ${FOLGA_CORTE.toFixed(2)};
}
`;
  const GLSL_FRAG_INICIO = `
  vec3 bsG = vec3( vBsMundo.x, vBsMundo.y, -vBsMundo.z );
  // fora do chão andável (fundo, morros de longe): some aos poucos até a margem
  float bsFora = max( max( uBsLimite.x - bsG.x, bsG.x - uBsLimite.z ), max( uBsLimite.y - bsG.z, bsG.z - uBsLimite.w ) );
  if ( bsFora > uBsMargem ) discard;
  float bsCorte = 1e6;
  if ( uBsCorteOn > 0.5 ) {
    bsCorte = bsAlturaCorte( bsG );
    if ( bsG.y > bsCorte ) discard;
  }`;
  const GLSL_FRAG_FIM = `
  {
    float bsLum = dot( outgoingLight, vec3( 0.2126, 0.7152, 0.0722 ) );
    outgoingLight = max( mix( vec3( bsLum ), outgoingLight, 1.18 ), 0.0 );
    outgoingLight /= 1.0 + max( outgoingLight - 0.85, 0.0 );  // ombro: pedra clara sob luz forte não estoura em branco
    bsLum = dot( outgoingLight, vec3( 0.2126, 0.7152, 0.0722 ) );
    outgoingLight = mix( outgoingLight, uBsFundo, smoothstep( 0.0, uBsMargem, bsFora ) );
    float bsD = length( vec3( bsG.x - uBsFoco.x, ( bsG.y - uBsFoco.y ) * 0.55, bsG.z - uBsFoco.z ) );
    float bsK = smoothstep( uBsRaio * 0.38, uBsRaio, bsD ) * uBsFocoOn;
    outgoingLight = mix( outgoingLight, mix( vec3( bsLum ), uBsFundo, 0.5 ) * 0.3, bsK * 0.88 );
    if ( uBsCorteOn > 0.5 ) {
      outgoingLight *= 1.0 - 0.5 * smoothstep( 1.5, 10.0, uBsAndarMin - bsG.y );
      float bsBorda = 1.0 - smoothstep( 0.0, 0.2, bsCorte - bsG.y );  // linha do corte, cor de osso
      outgoingLight = mix( outgoingLight, vec3( 0.78, 0.72, 0.6 ), bsBorda * 0.75 );
    }
  }`;

  let THREE = null;
  function carregarThree() {
    if (THREE) return Promise.resolve(THREE);
    return import(new URL("vendor/three.module.js", document.baseURI).href).then((m) => (THREE = m));
  }
  function webglDisponivel() {
    try {
      const c = document.createElement("canvas");
      return !!c.getContext("webgl2");
    } catch (e) { return false; }
  }

  class MapaIsometrico {
    constructor(container, opcoes = {}) {
      this.container = container;
      this.opcoes = opcoes;  // onMudar(): câmera mudou; onStatus(texto|null): carregando, extraindo, erro
      this.area = null;
      this.cena = null;      // cena.json
      this.des = { alvo: [0, 0, 0], giro: 0, incl: INCL_PADRAO, vista: 200 };  // para onde a câmera vai
      this.cur = { alvo: [0, 0, 0], giro: 0, incl: INCL_PADRAO, vista: 200 };  // onde está agora
      this.teclas = new Set();
      this.arrasto = null;
      this.focoOn = true;
      this.corte = null;     // { andar, grade } com o interior ligado
      this.gradeTopo = null; // chão mais alto em cada ponto: a altura do alvo acompanha o terreno
      this.chao = null;      // { v: Float32Array, f: Uint32Array }
      this.ativo = false;
      this.sujo = true;
      this._token = 0;
      this._ultimo = 0;
      this.livre = null;     // câmera livre: { pos, yaw, pitch } (null = câmera fixa)
      this.entidades = [];   // última lista de setEntidades
      this.geometrias = new Map();  // modelo -> submalhas (peças, objetos e personagens da cena)
      this.partes = new Map();      // parte do MSB (objeto) -> instâncias dela, para realçar
      this.personagens = {};        // modelo cXXXX -> { altura }
    }

    static suportado() { return typeof document !== "undefined" && webglDisponivel(); }

    get giro() { return this.livre ? this.livre.yaw : this.cur.giro; }
    // altura da vista em metros (escala dos ícones); na câmera livre, a distância até o que está no centro
    get vista() { return this.livre ? Math.max(VISTA_MIN, this.livre.dist * 1.2) : this.cur.vista; }
    get alvo() { return this.livre ? this._alvoDoLivre() : this.cur.alvo.slice(); }

    // Uma vez só, mesmo com chamadas ao mesmo tempo (abrir a área e pôr as entidades): dois renderers = tela preta.
    iniciar() {
      if (!this._iniciando) this._iniciando = this._iniciar();
      return this._iniciando;
    }

    async _iniciar() {
      await carregarThree();
      const r = new THREE.WebGLRenderer({ antialias: true, powerPreference: "high-performance" });
      r.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
      r.setClearColor(FUNDO, 1);
      r.domElement.className = "mapa-iso-canvas";
      this.container.appendChild(r.domElement);
      this.renderer = r;
      this.s3tc = r.extensions.has("WEBGL_compressed_texture_s3tc");
      this.s3tcSrgb = r.extensions.has("WEBGL_compressed_texture_s3tc_srgb");
      this.anisotropia = Math.min(8, r.capabilities.getMaxAnisotropy());

      this.cena3 = new THREE.Scene();
      this.camera = new THREE.OrthographicCamera(-1, 1, 1, -1, 1, 9000);
      this.cena3.add(new THREE.HemisphereLight(0xeef2f7, 0x4a4238, 4.6));
      this.luz = new THREE.DirectionalLight(0xfff0dc, 2.6);
      this.cena3.add(this.luz, this.luz.target);
      this.cameraLivre = new THREE.PerspectiveCamera(FOV_LIVRE, 1, 0.1, 6000);
      this.mundo = new THREE.Group();
      this.mundo.scale.set(1, 1, -1);  // jogo (mão esquerda) -> three.js
      this.cena3.add(this.mundo);
      this.grupoEnt = new THREE.Group();  // fora do mundo: trocar de área não apaga as formas compartilhadas
      this.grupoEnt.scale.set(1, 1, -1);
      this.cena3.add(this.grupoEnt);
      const capsula = new THREE.CapsuleGeometry(0.5, 1, 4, 12);
      capsula.scale(1, 0.5, 1);  // altura 1, diâmetro 1
      this.formas = { caixa: new THREE.BoxGeometry(1, 1, 1), capsula, cilindro: new THREE.CylinderGeometry(0.5, 0.5, 1, 18),
                      losango: new THREE.OctahedronGeometry(0.5) };
      this.matEnt = new Map();

      const vazio = new THREE.DataTexture(new Float32Array([-10000]), 1, 1, THREE.RedFormat, THREE.FloatType);
      vazio.needsUpdate = true;
      const fundo = new THREE.Color(FUNDO);
      this.uni = {
        uBsFoco: { value: new THREE.Vector3() }, uBsRaio: { value: 100 }, uBsFocoOn: { value: 1 },
        uBsCorteOn: { value: 0 }, uBsCortePlano: { value: 1e6 }, uBsAndarMin: { value: -1e6 },
        uBsCorteMapa: { value: vazio }, uBsCorteRet: { value: new THREE.Vector3(0, 0, 1) }, uBsCorteTam: { value: new THREE.Vector2(1, 1) },
        uBsLimite: { value: new THREE.Vector4(-1e6, -1e6, 1e6, 1e6) }, uBsMargem: { value: 40 }, uBsFundo: { value: new THREE.Vector3(fundo.r, fundo.g, fundo.b) },
      };
      this._vazio = vazio;
      this._v = new THREE.Vector3();
      this.redimensionar();
      const passo = (t) => {
        this._raf = requestAnimationFrame(passo);
        this._quadro(t);
      };
      this._raf = requestAnimationFrame(passo);
    }

    // ---- carga da cena ----------------------------------------------------------------------------
    async abrir(area) {
      await this.iniciar();
      if (this.area === area && this.cena) return this.cena;
      const token = ++this._token;
      this._limpar();
      this.area = area;
      this.cena = null;
      const status = (t) => { if (token === this._token && this.opcoes.onStatus) this.opcoes.onStatus(t); };
      const base = `/api/ds2/cena/${area}`;
      let cena = null, pediu = false;
      for (let tentativa = 0; tentativa < 400 && token === this._token; tentativa++) {
        const r = await fetch(`${base}/cena.json`, { cache: "no-store" }).catch(() => null);
        if (!r) { status("O servidor local não respondeu."); return null; }
        if (r.ok && r.status === 200) { cena = await r.json(); break; }
        const j = await r.json().catch(() => ({}));
        if (r.status === 404 && !pediu) {
          pediu = true;
          status("Extraindo o cenário desta área dos arquivos do jogo (uns 10 segundos na primeira vez)…");
          const p = await fetch(`${base}/extrair`, { method: "POST", headers: { "X-Buildsmith": "1" } }).catch(() => null);
          if (!p || (p.status !== 202 && !p.ok)) { status("Não consegui pedir a extração do cenário ao servidor local."); return null; }
        } else if (r.status === 202) {
          status("Extraindo o cenário desta área dos arquivos do jogo…");
        } else {
          status(`Cenário 3D indisponível: ${j.erro || r.status}`);
          return null;
        }
        await new Promise((ok) => setTimeout(ok, 900));
      }
      if (!cena || token !== this._token) return null;
      status("Carregando o cenário 3D…");
      const resp = await fetch(`${base}/geo.bin`, { cache: "no-store" }).catch(() => null);
      if (!resp || !resp.ok) { status("Não consegui baixar a geometria da área."); return null; }
      const geo = await resp.arrayBuffer();
      if (token !== this._token) return null;
      this.cena = cena;
      this._montar(cena, geo);
      this._carregarTexturas(cena, base, token);
      status(null);
      this.sujo = true;
      return cena;
    }

    _limpar() {
      if (!this.mundo) return;
      const vistos = new Set();
      const solta = (g, m) => {
        if (g && !vistos.has(g)) { vistos.add(g); g.dispose(); }
        if (m && !vistos.has(m)) { vistos.add(m); if (m.map) m.map.dispose(); m.dispose(); }
      };
      this.mundo.traverse((o) => solta(o.geometry, o.material));
      // modelos de personagem não ficam no mundo (só nas entidades): soltos aqui também
      for (const subs of (this.geometrias || new Map()).values()) subs.forEach((x) => solta(x.g, x.material));
      for (const { material } of (this.materiais || new Map()).values()) solta(null, material);
      this.mundo.clear();
      this.materiais = new Map();
      this.geometrias = new Map();
      this.partes = new Map();
      this.personagens = {};
      this.chao = null;
      this.gradeTopo = null;
      if (this.corte && this.corte.textura) this.corte.textura.dispose();
      this.corte = null;
      if (this.uni) this.uni.uBsCorteOn.value = 0;
      this.sujo = true;
    }

    _material(tipo, tex) {
      const chave = `${tipo}|${tex || ""}`;
      if (this.materiais.has(chave)) return this.materiais.get(chave).material;
      const m = new THREE.MeshLambertMaterial({ color: tex ? 0xffffff : COR_SEM_TEXTURA, side: THREE.DoubleSide });
      if (tipo === "recorte") m.alphaTest = 0.5;
      if (tipo === "decal") {
        Object.assign(m, { transparent: true, depthWrite: false, alphaTest: 0.04, polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -2 });
      }
      if (tipo === "agua") {
        m.color.set(0x2c5363);
        Object.assign(m, { transparent: true, opacity: 0.6, depthWrite: false });
      }
      this._injetar(m);
      this.materiais.set(chave, { material: m, tex });
      return m;
    }

    // Corte de interior, foco e limite da área no shader do material (cenário e entidades).
    _injetar(m) {
      const uni = this.uni;
      const srgbNoShader = () => !!(m.map && m.map.userData.srgbNoShader);
      m.onBeforeCompile = (sh) => {
        Object.assign(sh.uniforms, uni);
        sh.vertexShader = GLSL_VERT_DECL + sh.vertexShader.replace("#include <project_vertex>", `#include <project_vertex>${GLSL_VERT}`);
        sh.fragmentShader = GLSL_FRAG_DECL + sh.fragmentShader
          .replace("#include <clipping_planes_fragment>", `#include <clipping_planes_fragment>${GLSL_FRAG_INICIO}`)
          .replace("#include <map_fragment>", srgbNoShader()
            ? "#include <map_fragment>\n  diffuseColor.rgb = pow( diffuseColor.rgb, vec3( 2.2 ) );" : "#include <map_fragment>")
          .replace("#include <opaque_fragment>", `${GLSL_FRAG_FIM}\n  #include <opaque_fragment>`);
      };
      m.customProgramCacheKey = () => `bs-iso-${srgbNoShader() ? 1 : 0}`;
    }

    // ---- entidades (inimigos, portas, baús...) ---------------------------------------------------------
    // O que a cena tem de verdade: objeto do MSB com modelo (pelo nome da parte) e modelo de personagem (cXXXX).
    temParte(parte) { return !!(parte && this.partes && this.partes.has(parte)); }
    temModelo(modelo) { return !!(modelo && this.geometrias && this.geometrias.has(modelo) && this.personagens && this.personagens[modelo]); }
    alturaModelo(modelo) { return (this.personagens && this.personagens[modelo] && this.personagens[modelo].altura) || null; }
    // Por que o modelo do jogo não entrou na cena (o objeto fica com a forma de reserva); null se não se sabe.
    motivoModelo(modelo) { return (this.cena && this.cena.sem_modelo && this.cena.sem_modelo[modelo]) || null; }

    // Realça objetos reais da cena pela cor (multiplica a textura): { parte: 0xRRGGBB }; o resto volta ao normal.
    realcar(cores) {
      if (!this.partes || !THREE) return;
      const c = new THREE.Color(), tocadas = new Set();
      for (const [parte, lista] of this.partes) {
        c.set(cores && cores[parte] != null ? cores[parte] : 0xffffff);
        for (const { malha, i } of lista) { malha.setColorAt(i, c); tocadas.add(malha); }
      }
      tocadas.forEach((m) => { m.instanceColor.needsUpdate = true; });
      this.sujo = true;
    }

    // lista: [{ forma: "caixa"|"capsula"|"cilindro"|"losango", pos, rot?, dims: [larg, alt, prof], base?, cor, transp?,
    //           modelo?: "cXXXX", tinta?, xray? }] — com o modelo na cena, desenha o modelo (tingido por `tinta`); senão a
    // forma. xray: uma segunda passada em cor chapada que atravessa paredes (o realce dos inimigos).
    async setEntidades(lista) {
      this.entidades = lista || [];
      await this.iniciar();
      for (const o of [...this.grupoEnt.children]) { o.dispose && o.dispose(); this.grupoEnt.remove(o); }
      const grupos = new Map();
      for (const e of this.entidades) {
        const k = this.temModelo(e.modelo) ? `modelo|${e.modelo}` : this.formas[e.forma] ? `${e.forma}|${e.transp ? 1 : 0}` : null;
        if (!k) continue;
        if (!grupos.has(k)) grupos.set(k, []);
        grupos.get(k).push(e);
      }
      const m4 = new THREE.Matrix4(), cor = new THREE.Color();
      const xray = (g, es, matriz) => {  // por cima de tudo, meio transparente: dá para ver o inimigo atrás da parede
        const vistos = es.filter((e) => e.xray);
        if (!vistos.length) return;
        if (!this.matXray) {
          this.matXray = new THREE.MeshBasicMaterial({ color: 0xff3b2b, transparent: true, opacity: 0.42, depthTest: false,
                                                       depthWrite: false, side: THREE.DoubleSide });
        }
        const malha = new THREE.InstancedMesh(g, this.matXray, vistos.length);
        vistos.forEach((e, i) => malha.setMatrixAt(i, m4.fromArray(matriz(e))));
        malha.instanceMatrix.needsUpdate = true;
        malha.computeBoundingSphere();
        malha.renderOrder = 10;
        this.grupoEnt.add(malha);
      };
      for (const [k, es] of grupos) {
        if (k.startsWith("modelo|")) {
          const matriz = (e) => matrizEntidade(e.pos, e.rot, [1, 1, 1], 0);
          for (const { g, material } of this.geometrias.get(k.slice(7))) {
            const malha = new THREE.InstancedMesh(g, material, es.length);
            es.forEach((e, i) => {
              malha.setMatrixAt(i, m4.fromArray(matriz(e)));
              malha.setColorAt(i, cor.set(e.tinta ?? 0xffffff));
            });
            malha.instanceMatrix.needsUpdate = true;
            malha.instanceColor.needsUpdate = true;
            malha.computeBoundingSphere();
            this.grupoEnt.add(malha);
            xray(g, es, matriz);
          }
          continue;
        }
        const [forma, transp] = k.split("|");
        if (!this.matEnt.has(k)) {
          const mat = new THREE.MeshLambertMaterial({ color: 0xffffff });
          if (transp === "1") Object.assign(mat, { transparent: true, opacity: 0.38, depthWrite: false, side: THREE.DoubleSide });
          this._injetar(mat);
          this.matEnt.set(k, mat);
        }
        const malha = new THREE.InstancedMesh(this.formas[forma], this.matEnt.get(k), es.length);
        es.forEach((e, i) => {
          malha.setMatrixAt(i, m4.fromArray(matrizEntidade(e.pos, e.rot, e.dims, e.base ?? 0.5)));
          malha.setColorAt(i, cor.set(e.cor ?? 0xcccccc));
        });
        malha.instanceMatrix.needsUpdate = true;
        if (malha.instanceColor) malha.instanceColor.needsUpdate = true;
        malha.computeBoundingSphere();
        if (transp === "1") malha.renderOrder = 3;
        this.grupoEnt.add(malha);
        xray(this.formas[forma], es, (e) => matrizEntidade(e.pos, e.rot, e.dims, e.base ?? 0.5));
      }
      this.sujo = true;
    }

    _montar(cena, geo) {
      const geometrias = new Map();
      for (const [nome, mod] of Object.entries(cena.modelos || {})) {
        const subs = [];
        for (const s of mod.malhas || []) {
          const g = new THREE.BufferGeometry();
          g.setAttribute("position", new THREE.BufferAttribute(new Float32Array(geo, s.pos, s.v_count * 3), 3));
          const nrm = new THREE.InterleavedBuffer(new Int8Array(geo, s.nrm, s.v_count * 4), 4);
          g.setAttribute("normal", new THREE.InterleavedBufferAttribute(nrm, 3, 0, true));
          g.setAttribute("uv", new THREE.BufferAttribute(new Float32Array(geo, s.uv, s.v_count * 2), 2));
          const Idx = s.idx_size === 2 ? Uint16Array : Uint32Array;
          g.setIndex(new THREE.BufferAttribute(new Idx(geo, s.i_off, s.i_count), 1));
          g.computeBoundingSphere();
          subs.push({ g, material: this._material(s.tipo, s.tex), tipo: s.tipo });
        }
        geometrias.set(nome, subs);
      }
      this.geometrias = geometrias;
      this.personagens = cena.personagens || {};
      // peças de mapa e objetos (portas, baús, alavancas...) por modelo; objeto sempre instanciado, com cor por
      // instância, para o filtro poder realçar uma parte só (realcar)
      const porModelo = new Map();
      for (const inst of cena.instancias || []) {
        if (!geometrias.has(inst.modelo)) continue;
        const k = `${inst.obj ? "o" : "m"}|${inst.modelo}`;
        if (!porModelo.has(k)) porModelo.set(k, []);
        porModelo.get(k).push(inst);
      }
      const m4 = new THREE.Matrix4(), branco = new THREE.Color(0xffffff);
      for (const [k, insts] of porModelo) {
        const obj3 = k.startsWith("o|"), matrizes = insts.map((i) => i.matriz);
        for (const { g, material, tipo } of geometrias.get(k.slice(2))) {
          let obj;
          if (obj3) {
            obj = new THREE.InstancedMesh(g, material, insts.length);
            insts.forEach((inst, i) => {
              obj.setMatrixAt(i, m4.fromArray(inst.matriz));
              obj.setColorAt(i, branco);
              if (!this.partes.has(inst.nome)) this.partes.set(inst.nome, []);
              this.partes.get(inst.nome).push({ malha: obj, i });
            });
            obj.instanceMatrix.needsUpdate = true;
            obj.computeBoundingSphere();
            obj.matrixAutoUpdate = false;
          } else if (matrizes.length === 1) {
            obj = new THREE.Mesh(g, material);
            obj.matrixAutoUpdate = false;
            obj.matrix.fromArray(matrizes[0]);
          } else {
            obj = new THREE.InstancedMesh(g, material, matrizes.length);
            matrizes.forEach((mt, i) => obj.setMatrixAt(i, m4.fromArray(mt)));
            obj.instanceMatrix.needsUpdate = true;
            obj.computeBoundingSphere();
            obj.matrixAutoUpdate = false;
          }
          if (tipo === "decal" || tipo === "agua") obj.renderOrder = 2;
          this.mundo.add(obj);
        }
      }
      this.mundo.updateMatrixWorld(true);
      const lim = cena.limites, mg = cena.margem || 40;
      if (lim) this.uni.uBsLimite.value.set(lim.min[0], lim.min[2], lim.max[0], lim.max[2]);
      this.uni.uBsMargem.value = mg;
      if (cena.chao && cena.chao.i_count) {
        this.chao = { v: new Float32Array(geo, cena.chao.v_off, cena.chao.v_count * 3), f: new Uint32Array(geo, cena.chao.i_off, cena.chao.i_count) };
        this.gradeTopo = dilatar(gradeAlturas(this.chao.v, this.chao.f, null), 2);
      }
    }

    async _carregarTexturas(cena, base, token) {
      const nomes = [...new Set([...this.materiais.values()].map((x) => x.tex).filter(Boolean))];
      if (!this.s3tc) {
        if (this.opcoes.onStatus) this.opcoes.onStatus("Este navegador não lê as texturas do jogo (DXT): cenário sem cor.");
        return;
      }
      const fila = nomes.slice();
      const trabalhar = async () => {
        while (fila.length && token === this._token) {
          const nome = fila.shift();
          const r = await fetch(`${base}/tex/${encodeURIComponent(nome)}.dds`).catch(() => null);
          const dds = r && r.ok ? lerDDS(await r.arrayBuffer()) : null;
          if (!dds || token !== this._token) continue;
          const fmt = { DXT1: THREE.RGBA_S3TC_DXT1_Format, DXT3: THREE.RGBA_S3TC_DXT3_Format, DXT5: THREE.RGBA_S3TC_DXT5_Format }[dds.formato];
          const t = new THREE.CompressedTexture(dds.niveis, dds.largura, dds.altura, fmt);
          t.colorSpace = this.s3tcSrgb ? THREE.SRGBColorSpace : THREE.NoColorSpace;
          t.userData.srgbNoShader = !this.s3tcSrgb;
          t.wrapS = t.wrapT = THREE.RepeatWrapping;
          t.magFilter = THREE.LinearFilter;
          t.minFilter = dds.niveis.length > 1 ? THREE.LinearMipmapLinearFilter : THREE.LinearFilter;
          t.anisotropy = this.anisotropia;
          t.needsUpdate = true;
          for (const { material, tex } of this.materiais.values()) {
            if (tex !== nome) continue;
            material.map = t;
            material.needsUpdate = true;
          }
          this.sujo = true;
        }
      };
      await Promise.all(Array.from({ length: 6 }, trabalhar));
    }

    // ---- câmera -----------------------------------------------------------------------------------
    _tela() {
      const r = this.container.getBoundingClientRect();
      return { w: Math.max(1, r.width), h: Math.max(1, r.height) };
    }
    mpp(vista = this.des.vista) { return vista / this._tela().h; }

    // Mesmo enquadramento do 2D: centro (cx, cz) e escala s em pixels por metro.
    verComo2D(cx, cz, s, y, animar = false) {
      const alvoY = y ?? this._alturaChao(cx, cz, this.des.alvo[1]) ?? this.des.alvo[1];
      this.des.alvo = [cx, alvoY, cz];
      this.des.vista = Math.min(VISTA_MAX, Math.max(VISTA_MIN, this._tela().h / Math.max(s, 1e-3)));
      if (this.livre) { this._livreOlhar(this.des.alvo, this.des.vista); return; }
      if (animar) this.sujo = true;
      else this._pular();
    }
    comoVista2D() {
      if (this.livre) {
        const a = this._alvoDoLivre();
        return { cx: a[0], cz: a[2], s: this._tela().h / Math.max(VISTA_MIN, Math.min(VISTA_MAX, this.livre.dist)) };
      }
      return { cx: this.des.alvo[0], cz: this.des.alvo[2], s: this._tela().h / this.des.vista };
    }
    focar(pos, vista) {
      this.des.alvo = [pos[0], pos[1], pos[2]];
      if (vista) this.des.vista = Math.min(VISTA_MAX, Math.max(VISTA_MIN, vista));
      if (this.livre) this._livreOlhar(this.des.alvo, this.des.vista);
      this.sujo = true;
    }

    // ---- câmera livre (espectador) ------------------------------------------------------------------
    // Liga/desliga; ao ligar, a câmera sai de onde a vista fixa está olhando; ao desligar, a vista fixa volta para onde
    // a livre olhava.
    alternarLivre(on = !this.livre) {
      if (on && !this.livre) {
        const d = Math.max(12, Math.min(220, this.cur.vista * 0.55));
        const p = posicaoCamera(this.cur.alvo, this.cur.giro, this.cur.incl, d);
        this.livre = { pos: p, yaw: this.cur.giro, pitch: -Math.min(this.cur.incl, 70 * GRAU), dist: d };
      } else if (!on && this.livre) {
        const a = this._alvoDoLivre();
        this.des.alvo = a;
        this.des.giro = this.livre.yaw;
        this.des.vista = Math.min(VISTA_MAX, Math.max(VISTA_MIN, this.livre.dist * 1.6));
        this.livre = null;
        this._pular();
      }
      this.teclas.clear();
      this.sujo = true;
      return !!this.livre;
    }
    // Ponto do chão para onde a câmera livre olha (ou à frente dela, se olha para o horizonte).
    _alvoDoLivre() {
      const L = this.livre, d = direcaoLivre(L.yaw, L.pitch);
      const yChao = this._alturaChao(L.pos[0], L.pos[2], L.pos[1]) ?? L.pos[1] - 2;
      const t = d[1] < -0.08 ? Math.min(400, Math.max(2, (L.pos[1] - yChao) / -d[1])) : 25;
      L.dist = t;
      return [L.pos[0] + d[0] * t, L.pos[1] + d[1] * t, L.pos[2] + d[2] * t];
    }
    // Põe a câmera livre olhando para um ponto, um pouco atrás e acima dele, mantendo o rumo.
    _livreOlhar(alvo, vista) {
      const L = this.livre, d = Math.max(8, Math.min(220, (vista || 60) * 0.45)), pitch = -35 * GRAU;
      const f = direcaoLivre(L.yaw, pitch);
      L.pos = [alvo[0] - f[0] * d, alvo[1] - f[1] * d, alvo[2] - f[2] * d];
      L.pitch = pitch;
      L.dist = d;
      this.sujo = true;
    }
    _pular() {  // sem animação (troca de área, troca de vista)
      this.cur = { alvo: this.des.alvo.slice(), giro: this.des.giro, incl: this.des.incl, vista: this.des.vista };
      this.sujo = true;
    }
    girar(delta) {
      if (this.livre) this.livre.yaw += delta;
      else this.des.giro += delta;
      this.sujo = true;
    }
    norte() {
      if (this.livre) this.livre.yaw = 0;
      else this.des.giro = Math.round(this.des.giro / (2 * Math.PI)) * 2 * Math.PI;
      this.sujo = true;
    }
    alternarTopo() {
      if (this.livre) { this.livre.pitch = this.livre.pitch < -80 * GRAU ? -30 * GRAU : -PITCH_MAX; this.sujo = true; return this.livre.pitch < -80 * GRAU; }
      this.des.incl = this.des.incl > 80 * GRAU ? INCL_PADRAO : INCL_MAX;
      this.sujo = true;
      return this.des.incl > 80 * GRAU;
    }
    deCima() { return this.livre ? this.livre.pitch < -80 * GRAU : this.des.incl > 80 * GRAU; }
    zoomPor(fator, ox, oy) {
      if (this.livre) {  // roda na câmera livre: anda para onde o cursor aponta
        const L = this.livre, passo = Math.log(fator) * Math.max(6, L.dist * 0.6);
        const d = this._raioDoPixel(ox, oy);
        for (let k = 0; k < 3; k++) L.pos[k] += d[k] * passo;
        this.sujo = true;
        return;
      }
      const { w, h } = this._tela();
      ox = ox ?? w / 2; oy = oy ?? h / 2;
      const nova = Math.min(VISTA_MAX, Math.max(VISTA_MIN, this.des.vista / fator));
      const k = nova / this.des.vista;
      const p = chaoDoPixel(this.des.giro, this.des.incl, this.mpp(), ox - w / 2, oy - h / 2);
      this.des.alvo[0] += p[0] * (1 - k);
      this.des.alvo[2] += p[1] * (1 - k);
      this.des.vista = nova;
      this.sujo = true;
    }
    setFoco(on) { this.focoOn = !!on; this.sujo = true; }

    // Corte de interior pelo chão de um andar ({ min, max, altura }); null desliga.
    setCorte(andar) {
      if (this.corte && this.corte.textura) this.corte.textura.dispose();
      this.corte = null;
      if (!this.uni) return;
      if (!andar) { this.uni.uBsCorteOn.value = 0; this.sujo = true; return; }
      let grade = null;
      if (this.chao) {
        const y0 = andar.min - 1.0, y1 = andar.max + 1.0;
        grade = gradeAlturas(this.chao.v, this.chao.f, (a, b) => b >= y0 && a <= y1 && (a + b) / 2 >= y0 && (a + b) / 2 <= y1);
        if (grade) dilatar(grade, 3);
      }
      let textura = null;
      if (grade) {
        const dados = Float32Array.from(grade.h, (v) => (Number.isNaN(v) ? -10000 : v));
        textura = new THREE.DataTexture(dados, grade.larg, grade.alt, THREE.RedFormat, THREE.FloatType);
        textura.minFilter = textura.magFilter = THREE.NearestFilter;
        textura.needsUpdate = true;
        this.uni.uBsCorteRet.value.set(grade.x0, grade.z0, grade.cel);
        this.uni.uBsCorteTam.value.set(grade.larg, grade.alt);
      }
      this.uni.uBsCorteMapa.value = textura || this._vazio;
      this.uni.uBsCortePlano.value = andar.max + FOLGA_CORTE;
      this.uni.uBsAndarMin.value = andar.min;
      this.uni.uBsCorteOn.value = 1;
      this.corte = { andar, grade, textura };
      this.sujo = true;
    }
    // Altura onde o corte passa em (x, z); Infinity sem corte.
    alturaCorte(x, z) {
      if (!this.corte) return Infinity;
      const h = alturaNaGrade(this.corte.grade, x, z);
      return h == null ? this.corte.andar.max + FOLGA_CORTE : h + FOLGA_CORTE;
    }
    // Chão andável sob (x, z): com corte, o do andar; senão, o mais perto de yRef (ou o mais alto).
    _alturaChao(x, z, yRef) {
      if (this.corte) return alturaNaGrade(this.corte.grade, x, z);
      return alturaNaGrade(this.gradeTopo, x, z);
    }

    // ---- projeção para os marcadores do mapa.js -----------------------------------------------------
    projetar(x, y, z) {
      if (!this.camera) return [0, 0, false, {}];
      const { w, h } = this._tela();
      const v = this._v.set(x, y, -z).project(this.livre ? this.cameraLivre : this.camera);
      const raio = this._raio();
      const d = Math.hypot(x - this.cur.alvo[0], (y - this.cur.alvo[1]) * 0.55, z - this.cur.alvo[2]);
      return [(v.x + 1) / 2 * w, (1 - v.y) / 2 * h, v.z > -1 && v.z < 1,
        { cortado: y > this.alturaCorte(x, z) + 0.5, longe: !this.livre && this.focoOn && d > raio * 0.8 }];
    }
    // Direção (jogo) do raio da câmera livre que passa pelo pixel (ox, oy); sem pixel, o centro da tela.
    _raioDoPixel(ox, oy) {
      const { w, h } = this._tela(), L = this.livre;
      if (ox == null || oy == null || !this.cameraLivre) return direcaoLivre(L.yaw, L.pitch);
      const v = this._v.set((ox / w) * 2 - 1, 1 - (oy / h) * 2, 0.5).unproject(this.cameraLivre);
      const p = this.cameraLivre.position, n = Math.hypot(v.x - p.x, v.y - p.y, v.z - p.z) || 1;
      return [(v.x - p.x) / n, (v.y - p.y) / n, -(v.z - p.z) / n];
    }
    _raio() { return Math.max(30, this.cur.vista); }

    // ---- entrada (o mapa.js repassa os eventos da tela) ---------------------------------------------
    apertar(ev) {
      if (this.livre) {  // qualquer botão segurado olha em volta
        this.arrasto = { x: ev.clientX, y: ev.clientY, olhar: true, yaw: this.livre.yaw, pitch: this.livre.pitch };
        return;
      }
      const orbitar = ev.button === 2 || ev.button === 1 || ev.altKey || ev.ctrlKey;
      this.arrasto = { x: ev.clientX, y: ev.clientY, orbitar, giro: this.des.giro, incl: this.des.incl };
    }
    mover(ev) {
      const a = this.arrasto;
      if (!a) return;
      const dx = ev.clientX - a.x, dy = ev.clientY - a.y;
      if (a.olhar && this.livre) {
        this.livre.yaw = a.yaw + dx * 0.0042;
        this.livre.pitch = Math.min(PITCH_MAX, Math.max(-PITCH_MAX, a.pitch - dy * 0.0042));
      } else if (a.orbitar) {
        this.des.giro = a.giro - dx * 0.006;
        this.des.incl = Math.min(INCL_MAX, Math.max(INCL_MIN, a.incl + dy * 0.005));
      } else {
        const p = chaoDoPixel(this.cur.giro, this.cur.incl, this.mpp(this.cur.vista), ev.clientX - a.x, ev.clientY - a.y);
        a.x = ev.clientX; a.y = ev.clientY;
        for (const s of [this.des, this.cur]) { s.alvo[0] -= p[0]; s.alvo[2] -= p[1]; }
      }
      this.sujo = true;
    }
    soltar() { this.arrasto = null; }
    // true se a tecla é da câmera (o mapa.js não trata mais)
    tecla(ev, baixo) {
      if (!(this.livre ? TECLAS_LIVRE : TECLAS).has(ev.code)) return false;
      if (!baixo) { this.teclas.delete(ev.code); return true; }
      if (ev.ctrlKey || ev.metaKey || ev.altKey) return false;
      this.teclas.add(ev.code);
      this.sujo = true;
      return true;
    }
    limparTeclas() { this.teclas.clear(); this.arrasto = null; }
    setAtivo(on) { this.ativo = !!on; this.sujo = true; if (!on) this.limparTeclas(); }

    redimensionar() {
      if (!this.renderer) return;
      const { w, h } = this._tela();
      this.renderer.setSize(w, h, false);
      this.renderer.domElement.style.width = "100%";
      this.renderer.domElement.style.height = "100%";
      this.sujo = true;
    }

    // ---- quadro -----------------------------------------------------------------------------------
    _quadro(t) {
      const dt = Math.min(0.1, this._ultimo ? (t - this._ultimo) / 1000 : 0.016);
      this._ultimo = t;
      if (!this.ativo || !this.renderer) return;
      if (this.livre) { this._quadroLivre(dt); return; }
      const T = this.teclas, d = this.des;
      if (T.size) {
        const rapido = T.has("ShiftLeft") || T.has("ShiftRight") ? 2.6 : 1;
        const frente = (T.has("KeyW") || T.has("ArrowUp") ? 1 : 0) - (T.has("KeyS") || T.has("ArrowDown") ? 1 : 0);
        const lado = (T.has("KeyD") || T.has("ArrowRight") ? 1 : 0) - (T.has("KeyA") || T.has("ArrowLeft") ? 1 : 0);
        if (frente || lado) {
          const { frente: f, direita: r } = eixos(d.giro);
          const passo = d.vista * 0.7 * rapido * dt / Math.hypot(frente, lado);
          d.alvo[0] += (f[0] * frente + r[0] * lado) * passo;
          d.alvo[2] += (f[1] * frente + r[1] * lado) * passo;
        }
        d.giro += ((T.has("KeyE") ? 1 : 0) - (T.has("KeyQ") ? 1 : 0)) * 1.7 * rapido * dt;
        d.incl = Math.min(INCL_MAX, Math.max(INCL_MIN, d.incl + ((T.has("KeyR") ? 1 : 0) - (T.has("KeyF") ? 1 : 0)) * 0.9 * dt));
        const z = (T.has("Equal") || T.has("NumpadAdd") ? 1 : 0) - (T.has("Minus") || T.has("NumpadSubtract") ? 1 : 0);
        if (z) d.vista = Math.min(VISTA_MAX, Math.max(VISTA_MIN, d.vista * Math.exp(-z * 1.6 * dt)));
      }
      // a altura do alvo acompanha o chão sob o centro da tela (desliza pelo raio da vista: a imagem não pula)
      const yChao = this._alturaChao(d.alvo[0], d.alvo[2], d.alvo[1]);
      if (yChao != null && Math.abs(yChao - d.alvo[1]) > 0.3) {
        const { frente } = eixos(d.giro);
        const passo = (yChao - d.alvo[1]) * Math.min(1, dt * 8);
        const k = Math.cos(d.incl) / Math.max(Math.sin(d.incl), 0.05);
        for (const s of this.arrasto ? [d, this.cur] : [d]) {
          s.alvo[1] += passo;  // subir pelo raio = chegar mais perto da câmera (para trás no chão)
          s.alvo[0] -= frente[0] * passo * k;
          s.alvo[2] -= frente[1] * passo * k;
        }
      }
      const c = this.cur, a = 1 - Math.exp(-dt * SUAVE);
      let mexeu = false;
      const chegar = (v, alvo) => { const n = v + (alvo - v) * a; if (Math.abs(n - v) > 1e-5) mexeu = true; return Math.abs(alvo - n) < 1e-4 ? alvo : n; };
      c.alvo = c.alvo.map((v, i) => chegar(v, d.alvo[i]));
      c.giro = chegar(c.giro, c.giro + angulo(d.giro - c.giro));
      c.incl = chegar(c.incl, d.incl);
      c.vista = chegar(c.vista, d.vista);
      if (!mexeu && !this.sujo) return;
      this.sujo = false;
      this._aplicarCamera();
      this.renderer.render(this.cena3, this.camera);
      if (this.opcoes.onMudar) this.opcoes.onMudar();
    }

    _quadroLivre(dt) {
      const T = this.teclas, L = this.livre;
      let mexeu = false;
      if (T.size) {
        const rapido = T.has("ShiftLeft") || T.has("ShiftRight") ? 3.5 : 1;
        const frente = (T.has("KeyW") || T.has("ArrowUp") ? 1 : 0) - (T.has("KeyS") || T.has("ArrowDown") ? 1 : 0);
        const lado = (T.has("KeyD") || T.has("ArrowRight") ? 1 : 0) - (T.has("KeyA") || T.has("ArrowLeft") ? 1 : 0);
        const sobe = (T.has("KeyE") || T.has("Space") ? 1 : 0) - (T.has("KeyQ") || T.has("KeyC") ? 1 : 0);
        const v = VEL_LIVRE * rapido * dt * Math.max(1, Math.min(6, L.dist / 25));
        const f = direcaoLivre(L.yaw, L.pitch), r = eixos(L.yaw).direita;
        const passo = [f[0] * frente + r[0] * lado, f[1] * frente + sobe, f[2] * frente + r[1] * lado];
        if (passo.some((c) => c)) { for (let k = 0; k < 3; k++) L.pos[k] += passo[k] * v; mexeu = true; }
        const incl = (T.has("KeyR") ? 1 : 0) - (T.has("KeyF") ? 1 : 0);
        if (incl) { L.pitch = Math.min(PITCH_MAX, Math.max(-PITCH_MAX, L.pitch + incl * 0.9 * dt)); mexeu = true; }
      }
      if (!mexeu && !this.sujo) return;
      this.sujo = false;
      this._aplicarCamera();
      this.renderer.render(this.cena3, this.cameraLivre);
      if (this.opcoes.onMudar) this.opcoes.onMudar();
    }

    _aplicarCamera() {
      if (this.livre) {
        const L = this.livre, cam = this.cameraLivre, { w, h } = this._tela();
        const d = direcaoLivre(L.yaw, L.pitch);
        cam.aspect = w / h;
        cam.near = 0.3; cam.far = 4500;
        cam.position.set(L.pos[0], L.pos[1], -L.pos[2]);
        cam.up.set(0, 1, 0);
        cam.lookAt(L.pos[0] + d[0], L.pos[1] + d[1], -(L.pos[2] + d[2]));
        cam.updateProjectionMatrix();
        cam.updateMatrixWorld();
        const r = eixos(L.yaw).direita;
        this.luz.position.set(L.pos[0] - r[0] * 220, L.pos[1] + 520, -(L.pos[2] - r[1] * 220));
        this.luz.target.position.set(L.pos[0] + d[0] * 20, L.pos[1] + d[1] * 20, -(L.pos[2] + d[2] * 20));
        this.luz.target.updateMatrixWorld();
        this.uni.uBsFoco.value.set(L.pos[0], L.pos[1], L.pos[2]);
        this.uni.uBsFocoOn.value = 0;  // na câmera livre o "longe" é o horizonte: nada escurece
        return;
      }
      const c = this.cur, cam = this.camera;
      const { w, h } = this._tela();
      const D = 4000;
      const p = posicaoCamera(c.alvo, c.giro, c.incl, D);
      const { frente } = eixos(c.giro);
      const si = Math.sin(c.incl), co = Math.cos(c.incl);
      cam.position.set(p[0], p[1], -p[2]);
      cam.up.set(frente[0] * si, co, -frente[1] * si);
      cam.lookAt(c.alvo[0], c.alvo[1], -c.alvo[2]);
      const meia = c.vista / 2, asp = w / h;
      Object.assign(cam, { left: -meia * asp, right: meia * asp, top: meia, bottom: -meia, near: 1, far: D * 2.2 });
      cam.updateProjectionMatrix();
      cam.updateMatrixWorld();
      // luz de cima, vinda de trás e da esquerda da câmera: as faces que a gente vê ficam iluminadas
      const { direita } = eixos(c.giro);
      this.luz.position.set(c.alvo[0] - frente[0] * 300 - direita[0] * 220, c.alvo[1] + 520, -(c.alvo[2] - frente[1] * 300 - direita[1] * 220));
      this.luz.target.position.set(c.alvo[0], c.alvo[1], -c.alvo[2]);
      this.luz.target.updateMatrixWorld();
      this.uni.uBsFoco.value.set(c.alvo[0], c.alvo[1], c.alvo[2]);
      this.uni.uBsRaio.value = this._raio();
      this.uni.uBsFocoOn.value = this.focoOn ? 1 : 0;
    }

    destruir() {
      cancelAnimationFrame(this._raf);
      this._token++;
      this._limpar();
      if (this.renderer) { this.renderer.dispose(); this.renderer.domElement.remove(); }
      this.renderer = null;
    }
  }

  MapaIsometrico._teste = { eixos, chaoDoPixel, posicaoCamera, gradeAlturas, dilatar, alturaNaGrade, lerDDS, angulo, matrizEntidade,
    direcaoLivre };
  return MapaIsometrico;
});
