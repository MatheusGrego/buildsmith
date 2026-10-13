#!/usr/bin/env python3
"""Estado ao vivo do personagem lido da memória do DS2 SotFS (só leitura, ds2mem): nome, posição, direção do personagem,
posição da câmera e a direção (yaw) dela.

Endereços do DS2S-META (MIT, © 2021 Nordgaren), relativos ao ponteiro estático BaseA (ds2mem.AOB_BASE_A):
  PlayerCtrl = [BaseA+0xD0]; posição = [[PlayerCtrl+0xF8]+0xF0]: floats em +0x20/+0x24/+0x28 e a rotação em +0x30..+0x3C;
  câmera = [[BaseA+0x0]+0x20]: floats em +0x1A0/+0x1A4/+0x1A8; nome = [BaseA+0xA8]+0x114 (UTF-16).
Eixos: os 3 floats na ordem em que estão na memória = (x, y para cima, z), como a posição do save (ds2save.posicao_do_slot);
a conferência com o jogo fixa isso (EIXOS). Direções na convenção do mapa 3D (iso.js): frente = (sen a, cos a) em (x, z).

  python ds2vivo.py   uma leitura em JSON (o jogo precisa estar aberto)
"""
import json
import math
import sys
import time

import ds2mem

EXE = "DarkSoulsII.exe"
OFF_CTRL, OFF_POS, OFF_CAM, OFF_NOME = [0xD0], [0xF8, 0xF0], [0x0, 0x20], [0xA8]
POS_XYZ, POS_QUAT, CAM_XYZ, NOME = 0x20, 0x30, 0x1A0, 0x114
EIXOS = (0, 1, 2)  # índices dos floats da memória para (x, y para cima, z) do mapa


def yaw_da_camera(camera, pos) -> float | None:
    """Direção para onde a câmera olha no chão (da câmera para o personagem). None se ela está quase em cima dele."""
    dx, dz = pos[0] - camera[0], pos[2] - camera[2]
    if math.hypot(dx, dz) < 0.05:
        return None
    return math.atan2(dx, dz)


def direcao_do_quaternion(q) -> float | None:
    """Giro em torno do eixo vertical de um quaternion (w, x, y, z) com y para cima. None se não é uma rotação."""
    w, x, y, z = q
    if abs(math.sqrt(w * w + x * x + y * y + z * z) - 1) > 0.2:
        return None
    return math.atan2(2 * (w * y + x * z), 1 - 2 * (x * x + y * y))


class LeitorVivo:
    """Uma leitura por chamada de `ler()`. Abre o processo na primeira vez e de novo quando o jogo fecha e reabre."""

    def __init__(self, abrir=None, relogio=time.time):
        self._abrir = abrir or (lambda: ds2mem.ProcessoWin.abrir(EXE))
        self._relogio = relogio
        self._mem = None
        self._estatico = None  # endereço do ponteiro BaseA, achado uma vez por processo

    def _soltar(self) -> None:
        if self._mem is not None and hasattr(self._mem, "fechar"):
            self._mem.fechar()
        self._mem, self._estatico = None, None

    def _conectar(self) -> None:
        mem = self._abrir()
        instr = ds2mem.achar_aob(mem, mem.base_modulo, mem.tamanho_modulo, ds2mem.AOB_BASE_A)
        if instr is None:
            if hasattr(mem, "fechar"):
                mem.fechar()
            raise ds2mem.ErroMemoria("versão do jogo sem o BaseA conhecido")
        self._mem, self._estatico = mem, ds2mem.rel32(mem, instr, 3, 7)

    def ler(self) -> dict:
        ts = self._relogio()
        try:
            if self._mem is None:
                self._conectar()
            elif hasattr(self._mem, "vivo") and not self._mem.vivo():
                self._soltar()
                return {"ativo": False, "motivo": "jogo fechado", "ts": ts}
            mem = self._mem
            base_a = mem.u64(self._estatico)
            ctrl = ds2mem.cadeia(mem, base_a, OFF_CTRL) if base_a else None
            pos_ptr = ds2mem.cadeia(mem, ctrl, OFF_POS) if ctrl else None
            if not pos_ptr:
                return {"ativo": False, "motivo": "carregando", "ts": ts}
            bruto = mem.f32s(pos_ptr + POS_XYZ, 3)
            pos = [round(bruto[i], 3) for i in EIXOS]
            cam_ptr = ds2mem.cadeia(mem, base_a, OFF_CAM)
            camera = [round(mem.f32s(cam_ptr + CAM_XYZ, 3)[i], 3) for i in EIXOS] if cam_ptr else None
            nome_ptr = ds2mem.cadeia(mem, base_a, OFF_NOME)
            return {"ativo": True, "nome": mem.utf16(nome_ptr + NOME) if nome_ptr else None, "pos": pos,
                    "dir_personagem": direcao_do_quaternion(mem.f32s(pos_ptr + POS_QUAT, 4)),
                    "camera": camera, "yaw_camera": yaw_da_camera(camera, pos) if camera else None,
                    "area": None, "ts": ts}
        except ds2mem.ErroMemoria as err:
            self._soltar()
            motivo = "jogo fechado" if "não está aberto" in str(err) else str(err)
            return {"ativo": False, "motivo": motivo, "ts": ts}


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(LeitorVivo().ler(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
