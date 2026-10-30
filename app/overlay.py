#!/usr/bin/env python3
"""Janelas do buildsmith por cima do DS2 (Seamless Coop com `borderless_fullscreen = 1`): o minimapa sempre na tela
enquanto o jogo está em foco e o overlay grande (a página do personagem) numa tecla.

As janelas são o Edge em modo app (`--app=`, um perfil próprio por janela em ~/.buildsmith/overlay-edge) ajustadas pela
API do Windows (ctypes): sem borda, sempre por cima, no monitor do jogo, em pixels reais (DPI por monitor). O minimapa deixa
o clique passar para o jogo, não ganha foco e fica fora da barra de tarefas; a transparência é da janela inteira.

Teclas globais (RegisterHotKey): Ctrl+Shift+M abre/fecha o overlay grande, Ctrl+Shift+N mostra/esconde o minimapa; se outro
programa já usa, Ctrl+Alt+M / Ctrl+Alt+N.

O `Overlay` só decide (criar, mostrar, esconder, focar); quem fala com o Windows é o `Win32`, trocável nos testes.
Roda numa thread do servidor (serve.py), que já fica aberto enquanto se joga.
"""
import os
import subprocess
import sys
import threading
import urllib.parse
from pathlib import Path

MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_NOREPEAT = 0x1, 0x2, 0x4, 0x4000
TECLAS = {"grande": [(MOD_CONTROL | MOD_SHIFT, "M"), (MOD_CONTROL | MOD_ALT, "M")],
          "mini": [(MOD_CONTROL | MOD_SHIFT, "N"), (MOD_CONTROL | MOD_ALT, "N")]}
JOGO = "DarkSoulsII.exe"
OPACIDADE_MINI = 235  # 0-255: o jogo aparece de leve por trás do minimapa
INTERVALO = 1.0  # segundos entre conferências (jogo aberto, foco, "sempre por cima")


def geometria(monitor) -> dict:
    """Retângulos (x, y, largura, altura) em pixels reais: minimapa quadrado de 24% da altura do monitor no canto superior
    direito com margem de 2%; overlay grande 80% x 80% no centro."""
    x, y, w, h = monitor
    lado, margem = round(0.24 * h), round(0.02 * h)
    gw, gh = round(0.8 * w), round(0.8 * h)
    return {"mini": (x + w - margem - lado, y + margem, lado, lado),
            "grande": (x + (w - gw) // 2, y + (h - gh) // 2, gw, gh)}


def _nome_tecla(mods: int, letra: str) -> str:
    return "+".join([n for bit, n in ((MOD_CONTROL, "Ctrl"), (MOD_ALT, "Alt"), (MOD_SHIFT, "Shift")) if mods & bit] + [letra])


def escolher_teclas(registrar) -> dict:
    """Primeira combinação de cada ação que o Windows aceita (registrar(mods, vk) -> bool). None: todas tomadas."""
    out = {}
    for acao, opcoes in TECLAS.items():
        out[acao] = None
        for mods, letra in opcoes:
            if registrar(mods | MOD_NOREPEAT, ord(letra)):
                out[acao] = _nome_tecla(mods, letra)
                break
    return out


class Overlay:
    def __init__(self, win, url_mini, url_grande):
        """url_mini e url_grande: texto ou função (a página do personagem carregado no jogo, na hora de abrir)."""
        self.win, self.url_mini, self.url_grande = win, url_mini, url_grande
        self.mini = self.grande = None
        self.jogo = None
        self.mini_ligado = True
        self.grande_aberto = False
        self._lock = threading.Lock()

    def _garantir(self, papel: str, rect) -> int | None:
        hwnd = getattr(self, papel)
        if hwnd is None or not self.win.existe(hwnd):
            url = self.url_mini if papel == "mini" else self.url_grande
            url = url() if callable(url) else url
            hwnd = self.win.abrir_janela(url, rect, papel)
            if hwnd is None:
                return None
            self.win.estilizar(hwnd, papel)
            if papel == "grande":
                self.win.mostrar(hwnd, self.grande_aberto)
            setattr(self, papel, hwnd)
        return hwnd

    def _esconder_tudo(self) -> None:
        for hwnd in (self.mini, self.grande):
            if hwnd is not None and self.win.existe(hwnd):
                self.win.mostrar(hwnd, False)
        self.grande_aberto = False

    def passo(self) -> None:
        """Uma conferência: jogo aberto? em foco? janelas existem? minimapa por cima no monitor do jogo."""
        with self._lock:
            pid = self.win.pid_do_jogo()
            self.jogo = self.win.janela_do_jogo(pid) if pid else None
            if self.jogo is None:
                self._esconder_tudo()
                return
            g = geometria(self.win.monitor(self.jogo))
            mini, grande = self._garantir("mini", g["mini"]), self._garantir("grande", g["grande"])
            frente = self.win.em_primeiro_plano()
            em_jogo = frente in (self.jogo, mini, grande)
            if mini is not None:
                visivel = em_jogo and self.mini_ligado
                if visivel:
                    self.win.posicionar(mini, g["mini"])  # reafirma o "sempre por cima" e o monitor do jogo
                self.win.mostrar(mini, visivel)
            if grande is not None and self.grande_aberto:
                self.win.posicionar(grande, g["grande"])

    def alternar_grande(self) -> None:
        with self._lock:
            if self.grande is None or self.jogo is None:
                return
            self.grande_aberto = not self.grande_aberto
            self.win.mostrar(self.grande, self.grande_aberto)
            self.win.focar(self.grande if self.grande_aberto else self.jogo)

    def alternar_mini(self) -> None:
        with self._lock:
            self.mini_ligado = not self.mini_ligado


# ---- Windows (ctypes) --------------------------------------------------------------------------------------------------

class Win32:
    """Chamadas da API do Windows. Conferido à mão com o jogo aberto (Task 8 do plano)."""

    GWL_STYLE, GWL_EXSTYLE = -16, -20
    WS_POPUP, WS_VISIBLE = 0x80000000, 0x10000000
    WS_EX_LAYERED, WS_EX_TRANSPARENT, WS_EX_TOOLWINDOW, WS_EX_TOPMOST, WS_EX_NOACTIVATE = 0x80000, 0x20, 0x80, 0x8, 0x8000000
    SWP_NOACTIVATE, SWP_FRAMECHANGED, SWP_SHOWWINDOW = 0x10, 0x20, 0x40
    HWND_TOPMOST = -1

    def __init__(self, perfis: Path, edge: str | None = None):
        import ctypes
        from ctypes import wintypes

        self.ct, self.wt = ctypes, wintypes
        self.u32 = ctypes.WinDLL("user32", use_last_error=True)
        self.k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        try:
            self.u32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))  # PER_MONITOR_AWARE_V2: pixels reais
        except AttributeError:
            pass
        self.u32.GetForegroundWindow.restype = wintypes.HWND
        self.u32.MonitorFromWindow.restype = wintypes.HANDLE
        self.u32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
        self.u32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
        self.u32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
        self.u32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                          ctypes.c_int, wintypes.UINT]
        self.perfis, self.edge = Path(perfis), edge or achar_edge()
        self._procs = {}

    def pid_do_jogo(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "ds2-save" / "scripts"))
        import ds2mem

        try:
            proc = ds2mem.ProcessoWin.abrir(JOGO)
        except ds2mem.ErroMemoria:
            return None
        pid = proc.pid
        proc.fechar()
        return pid

    def _janelas_do_pid(self, pid: int) -> list[int]:
        ct, wt = self.ct, self.wt
        achadas = []

        @ct.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
        def cada(hwnd, _):
            dono = wt.DWORD()
            self.u32.GetWindowThreadProcessId(hwnd, ct.byref(dono))
            if dono.value == pid and self.u32.IsWindowVisible(hwnd) and self.u32.GetWindowTextLengthW(hwnd) > 0:
                achadas.append(hwnd)
            return True
        self.u32.EnumWindows(cada, 0)
        return achadas

    def janela_do_jogo(self, pid):
        janelas = self._janelas_do_pid(pid)
        return janelas[0] if janelas else None

    def monitor(self, hwnd):
        ct, wt = self.ct, self.wt

        class MONITORINFO(ct.Structure):
            _fields_ = [("cbSize", wt.DWORD), ("rcMonitor", wt.RECT), ("rcWork", wt.RECT), ("dwFlags", wt.DWORD)]
        info = MONITORINFO()
        info.cbSize = ct.sizeof(info)
        self.u32.GetMonitorInfoW(self.u32.MonitorFromWindow(hwnd, 2), ct.byref(info))  # MONITOR_DEFAULTTONEAREST
        r = info.rcMonitor
        return (r.left, r.top, r.right - r.left, r.bottom - r.top)

    def abrir_janela(self, url, rect, papel):
        import time

        if not self.edge:
            return None
        x, y, w, h = rect
        perfil = self.perfis / papel
        perfil.mkdir(parents=True, exist_ok=True)
        proc = self._procs.get(papel)
        if proc is None or proc.poll() is not None:
            proc = subprocess.Popen([self.edge, f"--app={url}", f"--user-data-dir={perfil}", "--no-first-run",
                                     "--no-default-browser-check", f"--window-position={x},{y}", f"--window-size={w},{h}"],
                                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self._procs[papel] = proc
        for _ in range(40):  # até ~8 s para o Edge abrir a janela
            janelas = self._janelas_do_pid(proc.pid)
            if janelas:
                return janelas[0]
            time.sleep(0.2)
        return None

    def existe(self, hwnd):
        return bool(self.u32.IsWindow(hwnd))

    def em_primeiro_plano(self):
        return self.u32.GetForegroundWindow()

    def estilizar(self, hwnd, papel):
        self.u32.SetWindowLongPtrW(hwnd, self.GWL_STYLE, self.WS_POPUP | self.WS_VISIBLE)
        ex = self.WS_EX_TOPMOST | self.WS_EX_TOOLWINDOW
        if papel == "mini":
            ex |= self.WS_EX_LAYERED | self.WS_EX_TRANSPARENT | self.WS_EX_NOACTIVATE
        self.u32.SetWindowLongPtrW(hwnd, self.GWL_EXSTYLE, ex)
        if papel == "mini":
            self.u32.SetLayeredWindowAttributes(hwnd, 0, OPACIDADE_MINI, 0x2)  # LWA_ALPHA

    def posicionar(self, hwnd, rect):
        x, y, w, h = rect
        self.u32.SetWindowPos(hwnd, self.HWND_TOPMOST, x, y, w, h, self.SWP_NOACTIVATE | self.SWP_FRAMECHANGED)

    def mostrar(self, hwnd, on):
        self.u32.ShowWindow(hwnd, 4 if on else 0)  # SW_SHOWNOACTIVATE / SW_HIDE

    def focar(self, hwnd):
        self.u32.ShowWindow(hwnd, 5)  # SW_SHOW
        self.u32.SetForegroundWindow(hwnd)

    def ouvir_teclas(self, acoes: dict) -> dict:
        """Registra as teclas numa thread própria (o Windows entrega WM_HOTKEY à thread que registrou) e chama
        acoes[nome]() quando apertam. Devolve as teclas que valeram."""
        ct, wt = self.ct, self.wt
        pronto, escolhidas = threading.Event(), {}

        def laco():
            ids = {}

            def registrar(mods, vk):
                n = len(ids) + 1
                if self.u32.RegisterHotKey(None, n, mods, vk):
                    ids[n] = None
                    return True
                return False
            escolhidas.update(escolher_teclas(registrar))
            nomes = [a for a, t in escolhidas.items() if t]
            for n, acao in zip(sorted(ids), nomes):
                ids[n] = acao
            pronto.set()
            msg = wt.MSG()
            while self.u32.GetMessageW(ct.byref(msg), None, 0, 0) > 0:
                if msg.message == 0x0312 and ids.get(msg.wParam):  # WM_HOTKEY
                    acoes[ids[msg.wParam]]()
        threading.Thread(target=laco, daemon=True, name="overlay-teclas").start()
        pronto.wait(5)
        return escolhidas


def achar_edge() -> str | None:
    for base in (os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles"), os.environ.get("LOCALAPPDATA")):
        if base:
            exe = Path(base) / "Microsoft" / "Edge" / "Application" / "msedge.exe"
            if exe.is_file():
                return str(exe)
    return None


def iniciar(home: Path, port: int, slug_do_jogador, avisa=lambda texto: None) -> Overlay | None:
    """Sobe o overlay numa thread (só no Windows, com Edge). slug_do_jogador() -> pasta da página do personagem no jogo."""
    if sys.platform != "win32":
        return None
    win = Win32(Path(home) / "overlay-edge")
    if not win.edge:
        avisa("overlay: Edge não encontrado; o minimapa por cima do jogo fica desligado")
        return None
    base, teclas = f"http://127.0.0.1:{port}", {}
    dica = lambda: urllib.parse.quote(teclas.get("grande") or "")  # noqa: E731 (o minimapa mostra a tecla que valeu)
    ov = Overlay(win, url_mini=lambda: f"{base}/p/ds2/{slug_do_jogador()}/overlay.html?fundo=escuro&tecla={dica()}",
                 url_grande=lambda: f"{base}/p/ds2/{slug_do_jogador()}/?overlay=1#mapa")
    teclas.update(win.ouvir_teclas({"grande": ov.alternar_grande, "mini": ov.alternar_mini}))
    avisa(f"overlay: teclas {teclas}")

    def laco():
        parar = threading.Event()
        while not parar.wait(INTERVALO):
            try:
                ov.passo()
            except Exception as err:  # Windows recusou uma chamada: tenta de novo no próximo passo
                avisa(f"overlay: {type(err).__name__}: {err}")
    threading.Thread(target=laco, daemon=True, name="overlay").start()
    return ov
