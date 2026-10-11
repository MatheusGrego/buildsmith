/**
 * iso.js - Visualizador Isométrico 3D com Three.js para o Buildsmith.
 * Carrega geometria real do DS2 (FLVER2), texturas DDS, controle de rotação 90°,
 * fatiamento de andares (clipping plane) e sincronização de marcadores e rotas.
 */

(function (root, factory) {
  if (typeof define === 'function' && define.amd) {
    define([], factory);
  } else if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.MapaIsometrico = factory();
  }
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  let THREE = null;
  let DDSLoader = null;

  async function garantirThree() {
    if (!THREE) {
      if (typeof window !== 'undefined' && window.THREE) {
        THREE = window.THREE;
      } else {
        THREE = await import('./vendor/three.module.js');
        if (typeof window !== 'undefined') window.THREE = THREE;
      }
    }
    if (!DDSLoader) {
      const ddsMod = await import('./vendor/DDSLoader.js');
      DDSLoader = ddsMod.DDSLoader;
    }
    return { THREE, DDSLoader };
  }

  const ANGULOS_ROTACAO = [0, Math.PI / 2, Math.PI, (3 * Math.PI) / 2];

  class MapaIsometrico {
    constructor(container, opcoes = {}) {
      this.container = typeof container === 'string' ? document.querySelector(container) : container;
      if (!this.container) throw new Error('Container do mapa isométrico não encontrado');

      this.opcoes = Object.assign({
        onMarkerUpdate: null,
        onCameraChange: null,
        alturaCorte: null
      }, opcoes);

      this.cena = null;
      this.camera = null;
      this.renderer = null;
      this.grupoMapa = null;
      this.grupoRotas = null;
      this.animando = false;

      // Estado de rotação e câmera
      this.anguloIndex = 0;
      this.anguloAlvo = 0;
      this.anguloAtual = 0;
      this.elevacao = Math.atan(1 / Math.sqrt(2)); // ~35.264° ângulo isométrico canônico
      this.distancia = 800;
      this.centro = { x: 0, y: 0, z: 0 };
      this.zoom = 1.0;

      // Fatiamento de andares
      this.alturaCorte = this.opcoes.alturaCorte;
      this.planoCorte = null;

      // Caches de cena
      this.cenaDados = null;
      this.texturasCache = new Map();
      this.materiaisCache = new Map();
      this.geometriasCache = new Map();

      // Interação do mouse (pan / zoom)
      this.arrastando = false;
      this.ultimoMouse = { x: 0, y: 0 };

      this._iniciarEventos();
    }

    async inicializar() {
      await garantirThree();

      const rect = this.container.getBoundingClientRect();
      const largura = rect.width || 800;
      const altura = rect.height || 600;

      this.cena = new THREE.Scene();
      this.cena.background = new THREE.Color(0x0c0e12);

      // Câmera ortográfica isométrica
      const aspect = largura / altura;
      const frustumSize = 400;
      this.camera = new THREE.OrthographicCamera(
        (-frustumSize * aspect) / 2,
        (frustumSize * aspect) / 2,
        frustumSize / 2,
        -frustumSize / 2,
        -2000,
        3000
      );

      // Renderer
      this.renderer = new THREE.WebGLRenderer({
        antialias: true,
        alpha: false,
        powerPreference: 'high-performance'
      });
      this.renderer.setSize(largura, altura);
      this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
      this.renderer.localClippingEnabled = true;
      this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
      this.renderer.toneMappingExposure = 1.1;

      this.canvas = this.renderer.domElement;
      this.canvas.className = 'mapa-iso-canvas';
      this.canvas.style.display = 'block';
      this.canvas.style.width = '100%';
      this.canvas.style.height = '100%';
      this.container.appendChild(this.canvas);

      // Iluminação
      const ambient = new THREE.AmbientLight(0xffffff, 1.4);
      this.cena.add(ambient);

      const dirLight = new THREE.DirectionalLight(0xfffaed, 1.6);
      dirLight.position.set(200, 500, 300);
      this.cena.add(dirLight);

      const fillLight = new THREE.DirectionalLight(0x88aacc, 0.6);
      fillLight.position.set(-200, 200, -300);
      this.cena.add(fillLight);

      // Grupos
      this.grupoMapa = new THREE.Group();
      this.grupoRotas = new THREE.Group();
      this.cena.add(this.grupoMapa);
      this.cena.add(this.grupoRotas);

      // Plano de corte
      this.planoCorte = new THREE.Plane(new THREE.Vector3(0, -1, 0), 9999);

      this._atualizarCamera();
      this._loopRender();

      window.addEventListener('resize', () => this.redimensionar());
    }

    _iniciarEventos() {
      this.container.addEventListener('mousedown', (e) => {
        if (e.button === 0 || e.button === 1) {
          this.arrastando = true;
          this.ultimoMouse = { x: e.clientX, y: e.clientY };
        }
      });

      window.addEventListener('mousemove', (e) => {
        if (!this.arrastando) return;
        const dx = e.clientX - this.ultimoMouse.x;
        const dy = e.clientY - this.ultimoMouse.y;
        this.ultimoMouse = { x: e.clientX, y: e.clientY };

        // Converte arrasto de tela para pan no espaço isométrico
        const cos = Math.cos(this.anguloAtual);
        const sin = Math.sin(this.anguloAtual);
        const fator = (400 / (this.container.clientHeight || 600)) / (this.camera ? this.camera.zoom : 1);

        this.centro.x -= (dx * cos - dy * sin) * fator;
        this.centro.z -= (dx * sin + dy * cos) * fator;
        this._atualizarCamera();
      });

      window.addEventListener('mouseup', () => {
        this.arrastando = false;
      });

      this.container.addEventListener('wheel', (e) => {
        e.preventDefault();
        const delta = e.deltaY < 0 ? 1.15 : 0.87;
        this.setZoom(this.zoom * delta);
      }, { passive: false });
    }

    setZoom(novoZoom) {
      this.zoom = Math.max(0.2, Math.min(novoZoom, 6.0));
      if (this.camera) {
        this.camera.zoom = this.zoom;
        this.camera.updateProjectionMatrix();
        this._notificarMudanca();
      }
    }

    girar(direcao = 1) {
      this.anguloIndex = (this.anguloIndex + direcao + 4) % 4;
      this.anguloAlvo = ANGULOS_ROTACAO[this.anguloIndex];
    }

    focar(pos) {
      if (Array.isArray(pos)) {
        this.centro = { x: pos[0], y: pos[1] ?? this.centro.y, z: pos[2] ?? this.centro.z };
      } else if (pos && typeof pos.x === 'number') {
        this.centro = { x: pos.x, y: pos.y ?? this.centro.y, z: pos.z };
      }
      this._atualizarCamera();
    }

    setAlturaCorte(y) {
      this.alturaCorte = y;
      if (this.planoCorte) {
        this.planoCorte.constant = y !== null && y !== undefined ? y : 9999;
      }
      for (const mat of this.materiaisCache.values()) {
        mat.clippingPlanes = y !== null && y !== undefined ? [this.planoCorte] : [];
        mat.needsUpdate = true;
      }
    }

    _atualizarCamera() {
      if (!this.camera) return;

      const cosT = Math.cos(this.anguloAtual);
      const sinT = Math.sin(this.anguloAtual);
      const cosA = Math.cos(this.elevacao);
      const sinA = Math.sin(this.elevacao);

      const cx = this.centro.x;
      const cy = this.centro.y;
      const cz = this.centro.z;

      this.camera.position.set(
        cx + this.distancia * cosA * sinT,
        cy + this.distancia * sinA,
        cz + this.distancia * cosA * cosT
      );
      this.camera.lookAt(cx, cy, cz);
      this._notificarMudanca();
    }

    _notificarMudanca() {
      if (this.opcoes.onCameraChange) {
        this.opcoes.onCameraChange({
          angulo: this.anguloAtual,
          zoom: this.zoom,
          centro: this.centro
        });
      }
      if (this.opcoes.onMarkerUpdate) {
        this.opcoes.onMarkerUpdate();
      }
    }

    _loopRender() {
      requestAnimationFrame(() => this._loopRender());

      // Interpola rotação suave (lerp)
      const diff = this.anguloAlvo - this.anguloAtual;
      // Normaliza menor caminho circular
      let menorDiff = ((diff + Math.PI) % (2 * Math.PI)) - Math.PI;
      if (menorDiff < -Math.PI) menorDiff += 2 * Math.PI;

      if (Math.abs(menorDiff) > 0.001) {
        this.anguloAtual += menorDiff * 0.14;
        this._atualizarCamera();
      }

      if (this.renderer && this.cena && this.camera) {
        this.renderer.render(this.cena, this.camera);
      }
    }

    redimensionar() {
      if (!this.renderer || !this.camera || !this.container) return;
      const rect = this.container.getBoundingClientRect();
      const largura = rect.width || 800;
      const altura = rect.height || 600;
      const aspect = largura / altura;
      const frustumSize = 400;

      this.camera.left = (-frustumSize * aspect) / 2;
      this.camera.right = (frustumSize * aspect) / 2;
      this.camera.top = frustumSize / 2;
      this.camera.bottom = -frustumSize / 2;
      this.camera.updateProjectionMatrix();

      this.renderer.setSize(largura, altura);
      this._notificarMudanca();
    }

    async carregarCena(area) {
      if (!this.cena) await this.inicializar();

      // Limpa mapa anterior
      while (this.grupoMapa.children.length > 0) {
        const obj = this.grupoMapa.children[0];
        this.grupoMapa.remove(obj);
        if (obj.geometry) obj.geometry.dispose();
      }
      this.geometriasCache.clear();
      this.materiaisCache.clear();

      // 1. Fetch de cena.json e geo.bin em paralelo
      const [respJson, respGeo] = await Promise.all([
        fetch(`/api/ds2/cena/${area}/cena.json`),
        fetch(`/api/ds2/cena/${area}/geo.bin`)
      ]);

      if (!respJson.ok || !respGeo.ok) {
        throw new Error(`Falha ao carregar cena da área ${area} (JSON: ${respJson.status}, GEO: ${respGeo.status})`);
      }

      const cenaDados = await respJson.json();
      const geoBuffer = await respGeo.arrayBuffer();
      this.cenaDados = cenaDados;

      // 2. Centraliza câmera no centro do mapa
      const lim = cenaDados.limites;
      if (lim && lim.min && lim.max) {
        this.centro = {
          x: (lim.min[0] + lim.max[0]) / 2,
          y: (lim.min[1] + lim.max[1]) / 2,
          z: (lim.min[2] + lim.max[2]) / 2
        };
      }

      const ddsLoader = new DDSLoader();

      // Função para obter material texturizado
      const obterMaterial = (nomeTex) => {
        const chave = nomeTex || '__sem_tex__';
        if (this.materiaisCache.has(chave)) return this.materiaisCache.get(chave);

        const mat = new THREE.MeshStandardMaterial({
          roughness: 0.85,
          metalness: 0.05,
          side: THREE.DoubleSide
        });

        if (this.alturaCorte !== null && this.alturaCorte !== undefined) {
          mat.clippingPlanes = [this.planoCorte];
        }

        if (nomeTex) {
          const texUrl = `/api/ds2/cena/${area}/tex/${nomeTex}.dds`;
          ddsLoader.load(
            texUrl,
            (tex) => {
              tex.wrapS = THREE.RepeatWrapping;
              tex.wrapT = THREE.RepeatWrapping;
              mat.map = tex;
              mat.needsUpdate = true;
            },
            undefined,
            () => {
              // Fallback sutil de cor de pedra
              mat.color.setHex(0x5a6268);
            }
          );
        } else {
          mat.color.setHex(0x6c757d);
        }

        this.materiaisCache.set(chave, mat);
        return mat;
      };

      // 3. Monta geometrias a partir de geoBuffer
      const modelos = cenaDados.modelos || {};
      for (const [idModelo, modInfo] of Object.entries(modelos)) {
        const subGeoms = [];
        for (const malha of modInfo.malhas || []) {
          const vOffset = malha.v_off;
          const vCount = malha.v_count;
          const iOffset = malha.i_off;
          const iCount = malha.i_count;
          const idxSize = malha.idx_size;

          const floatView = new Float32Array(geoBuffer, vOffset, vCount * 8);
          const interBuffer = new THREE.InterleavedBuffer(floatView, 8);

          const geom = new THREE.BufferGeometry();
          geom.setAttribute('position', new THREE.InterleavedBufferAttribute(interBuffer, 3, 0));
          geom.setAttribute('normal', new THREE.InterleavedBufferAttribute(interBuffer, 3, 3));
          geom.setAttribute('uv', new THREE.InterleavedBufferAttribute(interBuffer, 2, 6));

          const IndexArray = idxSize === 2 ? Uint16Array : Uint32Array;
          const indexView = new IndexArray(geoBuffer, iOffset, iCount);
          geom.setIndex(new THREE.BufferAttribute(indexView, 1));

          subGeoms.push({
            geom,
            material: obterMaterial(malha.tex)
          });
        }
        this.geometriasCache.set(idModelo, subGeoms);
      }

      // 4. Cria instâncias no grupo do mapa
      for (const inst of cenaDados.instancias || []) {
        const subGeoms = this.geometriasCache.get(inst.modelo.toLowerCase()) || this.geometriasCache.get(inst.modelo);
        if (!subGeoms) continue;

        const grupoInst = new THREE.Group();
        grupoInst.position.set(inst.pos[0], inst.pos[1], inst.pos[2]);

        const rx = (inst.rot[0] * Math.PI) / 180;
        const ry = (inst.rot[1] * Math.PI) / 180;
        const rz = (inst.rot[2] * Math.PI) / 180;
        grupoInst.rotation.set(rx, ry, rz, 'ZYX');

        grupoInst.scale.set(inst.esc[0], inst.esc[1], inst.esc[2]);

        for (const { geom, material } of subGeoms) {
          const mesh = new THREE.Mesh(geom, material);
          grupoInst.add(mesh);
        }

        this.grupoMapa.add(grupoInst);
      }

      this._atualizarCamera();
      return cenaDados;
    }

    /**
     * Projeta uma coordenada do jogo (x, y, z) para coordenadas de pixel na tela do container.
     */
    projetar(x, y, z) {
      if (!this.camera || !this.container) return { x: 0, y: 0, visivel: false };
      const vec = new THREE.Vector3(x, y, z);
      vec.project(this.camera);

      const rect = this.container.getBoundingClientRect();
      const w = rect.width || 800;
      const h = rect.height || 600;

      const telaX = (vec.x * 0.5 + 0.5) * w;
      const telaY = (-vec.y * 0.5 + 0.5) * h;
      const visivel = vec.z >= -1 && vec.z <= 1;

      return {
        x: telaX,
        y: telaY,
        visivel
      };
    }

    /**
     * Renderiza ou limpa uma rota 3D no chão.
     */
    desenharRota(pontos) {
      while (this.grupoRotas.children.length > 0) {
        const obj = this.grupoRotas.children[0];
        this.grupoRotas.remove(obj);
        if (obj.geometry) obj.geometry.dispose();
      }
      if (!pontos || pontos.length < 2) return;

      const vertices = [];
      for (const p of pontos) {
        vertices.push(p[0], p[1] + 0.35, p[2]); // eleva 35cm do chão para não z-fightar
      }

      const geom = new THREE.BufferGeometry();
      geom.setAttribute('position', new THREE.Float32BufferAttribute(vertices, 3));
      const mat = new THREE.LineBasicMaterial({
        color: 0x58a6ff,
        linewidth: 4,
        transparent: true,
        opacity: 0.95
      });

      const linha = new THREE.Line(geom, mat);
      this.grupoRotas.add(linha);
    }
  }

  return MapaIsometrico;
});
