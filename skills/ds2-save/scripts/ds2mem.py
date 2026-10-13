#!/usr/bin/env python3
"""Leitura (só leitura) da memória de um processo do Windows, para o estado ao vivo do jogo (ds2vivo).

Nada é escrito no jogo e nada é injetado: OpenProcess com PROCESS_VM_READ | PROCESS_QUERY_INFORMATION e ReadProcessMemory,
pelo ctypes (sem dependência). Os endereços do DS2 SotFS vêm do DS2S-META (MIT, © 2021 Nordgaren): o ponteiro estático
`BaseA` se acha pelo padrão AOB_BASE_A (instrução `mov rax, [rip+rel32]`) e o resto é cadeia de ponteiros a partir dele.

  MemoriaFalsa: regiões em dicionário, para testes sem o jogo.
"""
import re
import struct
import sys

AOB_BASE_A = "48 8B 05 ? ? ? ? 48 8B 58 38 48 85 DB 74 ? F6"  # DS2S-META: rel32 na posição 3, instrução de 7 bytes


class ErroMemoria(Exception):
    pass


class Memoria:
    """Leitura tipada sobre `ler(endereco, n)`."""

    def ler(self, endereco: int, n: int) -> bytes:  # pragma: no cover - interface
        raise NotImplementedError

    def u64(self, endereco: int) -> int:
        return struct.unpack("<Q", self.ler(endereco, 8))[0]

    def i32(self, endereco: int) -> int:
        return struct.unpack("<i", self.ler(endereco, 4))[0]

    def f32(self, endereco: int) -> float:
        return struct.unpack("<f", self.ler(endereco, 4))[0]

    def f32s(self, endereco: int, n: int) -> tuple:
        return struct.unpack(f"<{n}f", self.ler(endereco, 4 * n))

    def utf16(self, endereco: int, max_chars: int = 32) -> str:
        """Texto UTF-16 até o terminador, lido de 8 em 8 bytes (o nome pode estar no fim de uma página de memória)."""
        dados = b""
        while len(dados) < 2 * max_chars:
            try:
                pedaco = self.ler(endereco + len(dados), 8)
            except ErroMemoria:
                pedaco = self.ler(endereco + len(dados), 2)  # perto do fim da região: de 2 em 2
            for i in range(0, len(pedaco), 2):
                if pedaco[i:i + 2] == b"\0\0":
                    return (dados + pedaco[:i]).decode("utf-16-le", "replace")
            dados += pedaco
        return dados[:2 * max_chars].decode("utf-16-le", "replace")


class MemoriaFalsa(Memoria):
    def __init__(self, regioes: dict[int, bytes]):
        self.regioes = dict(regioes)

    def ler(self, endereco: int, n: int) -> bytes:
        for inicio, dados in self.regioes.items():
            if inicio <= endereco and endereco + n <= inicio + len(dados):
                return dados[endereco - inicio:endereco - inicio + n]
        raise ErroMemoria(f"leitura fora da memória: {endereco:#x} (+{n})")


def _regex(padrao: str) -> re.Pattern:
    partes = [b"." if p in ("?", "??") else re.escape(bytes([int(p, 16)])) for p in padrao.split()]
    return re.compile(b"".join(partes), re.DOTALL)


def achar_aob(mem: Memoria, inicio: int, tamanho: int, padrao: str, bloco: int = 1 << 20) -> int | None:
    """Primeiro endereço onde o padrão ('?' = qualquer byte) aparece em [inicio, inicio + tamanho). Lê em blocos com
    sobreposição do tamanho do padrão; bloco ilegível é pulado."""
    rx, n = _regex(padrao), len(padrao.split())
    pos = 0
    while pos < tamanho:
        ler = min(bloco + n - 1, tamanho - pos)
        try:
            dados = mem.ler(inicio + pos, ler)
        except ErroMemoria:
            dados = b""
        m = rx.search(dados)
        if m:
            return inicio + pos + m.start()
        pos += bloco
    return None


def rel32(mem: Memoria, endereco: int, pos: int, tam: int) -> int:
    """Endereço apontado por uma instrução com deslocamento relativo ao RIP: fim da instrução + rel32."""
    return endereco + tam + mem.i32(endereco + pos)


def cadeia(mem: Memoria, valor: int, offsets) -> int | None:
    """Segue ponteiros: valor = [valor + off] para cada off. None quando algum dá 0 (jogo carregando, tela de título)."""
    for off in offsets:
        valor = mem.u64(valor + off)
        if not valor:
            return None
    return valor


# ---- Windows ---------------------------------------------------------------------------------------------------------

PROCESS_VM_READ, PROCESS_QUERY_INFORMATION = 0x0010, 0x0400


class ProcessoWin(Memoria):
    """Processo aberto só para leitura. `base_modulo`/`tamanho_modulo` = o executável principal."""

    def __init__(self, handle, pid: int, base: int, tamanho: int):
        self.handle, self.pid, self.base_modulo, self.tamanho_modulo = handle, pid, base, tamanho

    @classmethod
    def abrir(cls, exe: str) -> "ProcessoWin":
        if sys.platform != "win32":
            raise ErroMemoria("leitura de memória só no Windows")
        import ctypes
        from ctypes import wintypes

        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        psapi = ctypes.WinDLL("psapi", use_last_error=True)

        class PROCESSENTRY32W(ctypes.Structure):
            _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD), ("th32ProcessID", wintypes.DWORD),
                        ("th32DefaultHeapID", ctypes.c_size_t), ("th32ModuleID", wintypes.DWORD),
                        ("cntThreads", wintypes.DWORD), ("th32ParentProcessID", wintypes.DWORD),
                        ("pcPriClassBase", ctypes.c_long), ("dwFlags", wintypes.DWORD), ("szExeFile", ctypes.c_wchar * 260)]

        class MODULEINFO(ctypes.Structure):
            _fields_ = [("lpBaseOfDll", ctypes.c_void_p), ("SizeOfImage", wintypes.DWORD), ("EntryPoint", ctypes.c_void_p)]

        k32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
        k32.OpenProcess.restype = wintypes.HANDLE
        snap = k32.CreateToolhelp32Snapshot(0x2, 0)  # TH32CS_SNAPPROCESS
        pid = None
        try:
            e = PROCESSENTRY32W()
            e.dwSize = ctypes.sizeof(e)
            ok = k32.Process32FirstW(snap, ctypes.byref(e))
            while ok:
                if e.szExeFile.lower() == exe.lower():
                    pid = e.th32ProcessID
                    break
                ok = k32.Process32NextW(snap, ctypes.byref(e))
        finally:
            k32.CloseHandle(snap)
        if pid is None:
            raise ErroMemoria(f"{exe} não está aberto")
        handle = k32.OpenProcess(PROCESS_VM_READ | PROCESS_QUERY_INFORMATION, False, pid)
        if not handle:
            raise ErroMemoria(f"sem permissão para ler {exe} (erro {ctypes.get_last_error()})")
        mods = (ctypes.c_void_p * 1)()
        needed = wintypes.DWORD()
        if not psapi.EnumProcessModulesEx(handle, mods, ctypes.sizeof(mods), ctypes.byref(needed), 0x03):
            k32.CloseHandle(handle)
            raise ErroMemoria(f"não consegui listar os módulos de {exe}")
        info = MODULEINFO()
        psapi.GetModuleInformation(handle, ctypes.c_void_p(mods[0]), ctypes.byref(info), ctypes.sizeof(info))
        proc = cls(handle, pid, info.lpBaseOfDll or 0, info.SizeOfImage)
        proc._k32 = k32
        return proc

    def ler(self, endereco: int, n: int) -> bytes:
        import ctypes

        buf = ctypes.create_string_buffer(n)
        lido = ctypes.c_size_t()
        ok = self._k32.ReadProcessMemory(self.handle, ctypes.c_void_p(endereco), buf, n, ctypes.byref(lido))
        if not ok or lido.value != n:
            raise ErroMemoria(f"leitura falhou em {endereco:#x} (+{n})")
        return buf.raw

    def vivo(self) -> bool:
        """O processo ainda existe (o jogo pode ter fechado com o handle aberto)."""
        import ctypes

        codigo = ctypes.c_ulong()
        return bool(self._k32.GetExitCodeProcess(self.handle, ctypes.byref(codigo))) and codigo.value == 259  # STILL_ACTIVE

    def fechar(self) -> None:
        if self.handle:
            self._k32.CloseHandle(self.handle)
            self.handle = None
