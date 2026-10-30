(function () {
  // Minimapa: o cenário 3D (iso.js) seguindo o personagem pelo stream ao vivo do servidor (/api/ds2/vivo/stream, memória
  // do jogo). Gira com a câmera do jogo; a seta mostra para onde o personagem olha. ?fundo=escuro: fundo sólido para a
  // janela por cima do jogo (o vazio fora do cenário não vira buraco); sem nada: transparente para a fonte do OBS.
  const VISTA = 60;  // metros na altura do minimapa
  const TEXTO = { "jogo fechado": "jogo fechado", carregando: "carregando…" };
  const q = new URLSearchParams(location.search);
  const escuro = q.get("fundo") === "escuro";
  document.documentElement.classList.toggle("escuro", escuro);
  const caixa = document.getElementById("mini"), seta = document.getElementById("seta"), aviso = document.getElementById("aviso");
  const mostrar = (t) => { aviso.textContent = t || ""; aviso.hidden = !t; seta.style.visibility = t ? "hidden" : ""; };
  const Iso = window.MapaIsometrico;
  if (!Iso || !Iso.suportado()) { mostrar("sem WebGL 2"); return; }
  const iso = new Iso(caixa, { fundo: escuro ? undefined : "transparente", onStatus: (t) => { if (t) mostrar(t); } });
  iso.setFoco(false);
  iso.setAtivo(true);
  let area = null, primeiro = true;
  const tecla = (q.get("tecla") || "").slice(0, 24);  // a tecla do menu que o Windows aceitou (app/overlay.py)
  let dicaAte = tecla ? Date.now() + 6000 : 0;

  function aplicar(v) {
    if (!v.ativo) { mostrar(TEXTO[v.motivo] || "sem leitura do jogo"); return; }
    if (!v.area) { mostrar("esperando a área no save"); return; }
    if (primeiro) { iso.focar(v.pos, VISTA); primeiro = false; }
    if (v.area !== area) {
      area = v.area;
      iso.abrir(area).then(() => { iso.setCorte(null); iso.seguir(v); }).catch(() => mostrar("sem a cena desta área"));
    }
    mostrar(Date.now() < dicaAte ? `${tecla} abre o menu` : null);
    seta.style.visibility = "";
    iso.seguir(v);
    const r = Iso._teste.rotacaoSeta(v.dir_personagem, iso.giro);
    seta.style.transform = r == null ? "" : `rotate(${r}rad)`;
  }

  const fonte = new EventSource("/api/ds2/vivo/stream");
  fonte.onmessage = (e) => { let v = null; try { v = JSON.parse(e.data); } catch (err) { return; } aplicar(v); };
  fonte.onerror = () => mostrar("buildsmith fora do ar");
  window.addEventListener("resize", () => iso.redimensionar());
})();
