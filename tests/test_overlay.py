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
