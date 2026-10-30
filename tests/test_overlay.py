import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

import overlay


def test_geometry_on_a_1080p_monitor():
    g = overlay.geometria((0, 0, 1920, 1080))
    assert g["mini"] == (1639, 22, 259, 259)  # 24% da altura, margem de 2%, canto superior direito
    assert g["grande"] == (192, 108, 1536, 864)  # 80% x 80%, no centro


def test_geometry_on_a_second_monitor_uses_its_offset_and_real_pixels():
    g = overlay.geometria((1920, 0, 2560, 1440))
    assert g["mini"] == (1920 + 2560 - 29 - 346, 29, 346, 346)
    assert g["grande"] == (1920 + 256, 144, 2048, 1152)


def test_hotkeys_fall_back_when_taken():
    tomadas = {(overlay.MOD_CONTROL | overlay.MOD_SHIFT, ord("M"))}
    teclas = overlay.escolher_teclas(lambda mods, vk: (mods & ~overlay.MOD_NOREPEAT, vk) not in tomadas)
    assert teclas == {"grande": "Ctrl+Alt+M", "mini": "Ctrl+Shift+N"}
    assert overlay.escolher_teclas(lambda mods, vk: False) == {"grande": None, "mini": None}


class WinFalso:
    def __init__(self):
        self.pid, self.jogo, self.frente = None, 100, None
        self.janelas, self.visiveis, self.posicoes, self.estilos, self.focos = {}, set(), {}, {}, []
        self.proximo = 500

    def pid_do_jogo(self):
        return self.pid

    def janela_do_jogo(self, pid):
        return self.jogo if pid else None

    def monitor(self, hwnd):
        return (0, 0, 1920, 1080)

    def abrir_janela(self, url, rect, papel):
        self.proximo += 1
        self.janelas[self.proximo] = (url, papel)
        return self.proximo

    def existe(self, hwnd):
        return hwnd in self.janelas

    def em_primeiro_plano(self):
        return self.frente

    def estilizar(self, hwnd, papel):
        self.estilos[hwnd] = papel

    def posicionar(self, hwnd, rect):
        self.posicoes[hwnd] = rect

    def mostrar(self, hwnd, on):
        (self.visiveis.add if on else self.visiveis.discard)(hwnd)

    def focar(self, hwnd):
        self.focos.append(hwnd)
        self.frente = hwnd


def novo():
    win = WinFalso()
    return win, overlay.Overlay(win, url_mini="http://x/mini", url_grande=lambda: "http://x/grande")


def test_nothing_happens_without_the_game():
    win, ov = novo()
    ov.passo()
    assert win.janelas == {} and not win.visiveis


def test_game_in_focus_gets_the_minimap_on_top_and_the_big_one_hidden():
    win, ov = novo()
    win.pid, win.frente = 42, 100
    ov.passo()
    mini, grande = ov.mini, ov.grande
    assert win.janelas[mini] == ("http://x/mini", "mini") and win.janelas[grande] == ("http://x/grande", "grande")
    assert win.estilos == {mini: "mini", grande: "grande"}
    assert mini in win.visiveis and grande not in win.visiveis
    assert win.posicoes[mini] == (1639, 22, 259, 259)


def test_minimap_hides_when_another_app_is_in_front_and_returns():
    win, ov = novo()
    win.pid, win.frente = 42, 100
    ov.passo()
    win.frente = 999  # alt-tab
    ov.passo()
    assert ov.mini not in win.visiveis
    win.frente = 100
    ov.passo()
    assert ov.mini in win.visiveis


def test_hotkey_opens_and_closes_the_big_overlay_and_gives_focus_back():
    win, ov = novo()
    win.pid, win.frente = 42, 100
    ov.passo()
    ov.alternar_grande()
    assert ov.grande in win.visiveis and win.frente == ov.grande
    ov.passo()  # o overlay grande na frente conta como jogo em foco: o minimapa fica
    assert ov.mini in win.visiveis
    ov.alternar_grande()
    assert ov.grande not in win.visiveis and win.focos[-1] == 100


def test_minimap_hotkey_hides_it_until_pressed_again():
    win, ov = novo()
    win.pid, win.frente = 42, 100
    ov.passo()
    ov.alternar_mini()
    ov.passo()
    assert ov.mini not in win.visiveis
    ov.alternar_mini()
    ov.passo()
    assert ov.mini in win.visiveis


def test_closed_window_is_recreated_and_game_closing_hides_all():
    win, ov = novo()
    win.pid, win.frente = 42, 100
    ov.passo()
    velho = ov.mini
    del win.janelas[velho]  # o usuário fechou a janela do Edge (janela fechada não fica visível)
    win.visiveis.discard(velho)
    ov.passo()
    assert ov.mini != velho and ov.mini in win.visiveis
    win.pid = None
    ov.passo()
    assert not win.visiveis


# ---- Linux com Hyprland ------------------------------------------------------------------------------------------------

class HyprctlFalso:
    """Responde como o hyprctl do Hyprland 0.56 (JSON de clients/monitors/binds) e guarda os eval e dispatch."""

    def __init__(self):
        self.clientes = [{"address": "0xjogo", "pid": 4242, "class": "steam_app_335300", "monitor": 1, "mapped": True,
                          "workspace": {"name": "3"}}]
        self.monitores = [{"id": 0, "x": 0, "y": 0, "width": 1366, "height": 768, "scale": 1.0},
                          {"id": 1, "x": 1366, "y": 0, "width": 2560, "height": 1440, "scale": 1.25}]
        self.binds = [{"modmask": 64, "key": "M"}]
        self.ativa, self.evals, self.dispatches = "0xjogo", [], []

    def __call__(self, args):
        if args[0] == "-j":
            return __import__("json").dumps({"clients": self.clientes, "monitors": self.monitores, "binds": self.binds,
                                              "activewindow": {"address": self.ativa},
                                              "activeworkspace": {"name": "3"}}[args[1]])
        (self.evals if args[0] == "eval" else self.dispatches).append(args[1])
        return "ok"


def hypr(tmp_path, **kw):
    falso = HyprctlFalso()
    return overlay.Hyprland(tmp_path / "perfis", 8642, navegador="/usr/bin/zen-browser", hyprctl=falso, **kw), falso


def test_hyprland_sets_window_rules_for_both_windows(tmp_path):
    _, h = hypr(tmp_path)
    mini, grande = h.evals
    assert 'class = "^buildsmith-mini$"' in mini and "no_focus = true" in mini and "pin = true" in mini
    assert 'class = "^buildsmith-grande$"' in grande and "float = true" in grande and "no_focus" not in grande


def test_hyprland_finds_the_game_and_its_monitor_in_logical_pixels(tmp_path):
    win, h = hypr(tmp_path, pid_do_jogo=lambda: 4242)
    assert win.pid_do_jogo() == 4242 and win.janela_do_jogo(4242) == "0xjogo"
    assert win.monitor("0xjogo") == (1366, 0, 2048, 1152)  # 2560 x 1440 com escala 1,25
    h.clientes[0]["pid"] = 1  # o pid da janela não bate (XWayland): acha pela classe do Proton
    win._cache = (0.0, [])
    assert win.janela_do_jogo(4242) == "0xjogo"
    assert win.em_primeiro_plano() == "0xjogo"


def test_hyprland_opens_a_kiosk_browser_with_its_own_profile_and_class(tmp_path, monkeypatch):
    win, h = hypr(tmp_path)
    abertos = []

    class Popen:
        def __init__(self, args, **kwargs):
            abertos.append(args)
            h.clientes.append({"address": "0xmini", "pid": 77, "class": "buildsmith-mini", "workspace": {"name": "3"}})

        def poll(self):
            return None
    monkeypatch.setattr(overlay.subprocess, "Popen", Popen)
    assert win.abrir_janela("http://127.0.0.1:8642/p/ds2/x/overlay.html", (10, 20, 300, 300), "mini") == "0xmini"
    args = abertos[0]
    assert args[0] == "/usr/bin/zen-browser" and args[-1].endswith("overlay.html")
    assert ["--name", "buildsmith-mini"] == args[args.index("--name"):args.index("--name") + 2] and "--kiosk" in args
    perfil = Path(args[args.index("--profile") + 1])
    assert perfil == tmp_path / "perfis" / "mini"
    assert "min-width: 0" in (perfil / "chrome" / "userChrome.css").read_text(encoding="utf-8")
    assert "legacyUserProfileCustomizations" in (perfil / "user.js").read_text(encoding="utf-8")
    assert h.dispatches == ['hl.dsp.window.resize({ window = "address:0xmini", x = 300, y = 300, relative = false })',
                            'hl.dsp.window.move({ window = "address:0xmini", x = 10, y = 20, relative = false })']
    win.posicionar("0xmini", (10, 20, 300, 300))
    assert len(h.dispatches) == 2  # mesma geometria: nada de novo
    assert win.abrir_janela("u", (10, 20, 300, 300), "mini") == "0xmini" and len(abertos) == 1  # já aberta: reusa


def test_hyprland_hides_in_a_special_workspace_and_shows_pinned_over_the_game(tmp_path):
    win, h = hypr(tmp_path)
    win.mostrar("0xmini", False)
    assert h.dispatches == ['hl.dsp.window.pin({ window = "address:0xmini", action = "disable" })',
                            'hl.dsp.window.move({ window = "address:0xmini", workspace = "special:buildsmith", follow = false })']
    win.mostrar("0xmini", False)
    assert len(h.dispatches) == 2
    win.mostrar("0xmini", True)
    assert h.dispatches[2:] == ['hl.dsp.window.move({ window = "address:0xmini", workspace = "3", follow = false })',
                                'hl.dsp.window.pin({ window = "address:0xmini", action = "enable" })',
                                'hl.dsp.window.alter_zorder({ window = "address:0xmini", mode = "top" })']
    win.focar("0xmini")
    assert h.dispatches[-1] == 'hl.dsp.focus({ window = "address:0xmini" })'


def test_hyprland_keys_call_the_server_and_skip_combos_the_user_has(tmp_path):
    win, h = hypr(tmp_path)
    h.binds.append({"modmask": 5, "key": "M"})  # Ctrl+Shift+M já é do usuário
    chamadas = []
    teclas = win.ouvir_teclas({"grande": lambda: chamadas.append("grande"), "mini": lambda: chamadas.append("mini")})
    assert teclas == {"grande": "Ctrl+Alt+M", "mini": "Ctrl+Shift+N"}
    binds = h.evals[2:]
    assert binds[0].startswith('hl.bind("CTRL + ALT + M", hl.dsp.exec_cmd([[curl ') and "/api/overlay/grande" in binds[0]
    assert binds[1].startswith('hl.bind("CTRL + SHIFT + N"') and "/api/overlay/mini" in binds[1]
    assert "X-Buildsmith: 1" in binds[0]
    assert overlay.disparar("grande") and chamadas == ["grande"] and not overlay.disparar("nada")
    win2, h2 = hypr(tmp_path)  # servidor reiniciado: tira os binds que deixou antes de pôr de novo
    win2.ouvir_teclas({"grande": lambda: None, "mini": lambda: None})
    assert h2.evals[2:4] == ['hl.unbind("CTRL + ALT + M")', 'hl.unbind("CTRL + SHIFT + N")']


def test_overlay_does_not_start_outside_windows_and_hyprland(tmp_path, monkeypatch):
    monkeypatch.setattr(overlay.sys, "platform", "linux")
    monkeypatch.delenv("HYPRLAND_INSTANCE_SIGNATURE", raising=False)
    avisos = []
    assert overlay.iniciar(tmp_path, 8642, lambda: "x", avisos.append) is None
    assert avisos == ["overlay: só no Windows e no Linux com Hyprland"]


def test_hyprland_takes_the_kiosk_window_out_of_fullscreen_before_sizing_it(tmp_path):
    win, h = hypr(tmp_path)
    h.clientes.append({"address": "0xgrande", "class": "buildsmith-grande", "fullscreen": 2, "workspace": {"name": "3"}})
    win.posicionar("0xgrande", (136, 77, 1093, 614))
    assert h.dispatches[0] == 'hl.dsp.window.fullscreen_state({ window = "address:0xgrande", internal = 0, client = 2 })'
    assert h.dispatches[1:] == ['hl.dsp.window.resize({ window = "address:0xgrande", x = 1093, y = 614, relative = false })',
                                'hl.dsp.window.move({ window = "address:0xgrande", x = 136, y = 77, relative = false })']
