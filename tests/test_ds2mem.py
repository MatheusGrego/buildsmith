import struct
import subprocess

import pytest

import ds2mem

BASE = 0x140000000


def memoria(**extra):
    """Módulo falso com uma instrução `mov rax, [rip+rel]` no meio e um ponteiro estático depois dela."""
    codigo = bytearray(0x200)
    instr = 0x100
    codigo[instr:instr + 7] = bytes.fromhex("48 8B 05 00 00 00 00".replace(" ", ""))
    struct.pack_into("<i", codigo, instr + 3, 0x80)  # rel32: ponteiro em instr + 7 + 0x80
    codigo[instr + 7:instr + 17] = bytes.fromhex("488B583848 85DB 74 10 F6".replace(" ", ""))
    struct.pack_into("<Q", codigo, instr + 7 + 0x80, 0x5000)
    regioes = {BASE: bytes(codigo), 0x5000: struct.pack("<Q", 0x6000) + bytes(0xC8) + struct.pack("<Q", 0x7000),
               0x6000: bytes(0x40), 0x7000: struct.pack("<f", 1.5) + "Teste\0".encode("utf-16-le")}
    regioes.update(extra)
    return ds2mem.MemoriaFalsa(regioes)


def test_aob_with_wildcards_finds_the_instruction():
    mem = memoria()
    assert ds2mem.achar_aob(mem, BASE, 0x200, "48 8B 05 ? ? ? ? 48 8B 58 38 48 85 DB 74 ? F6") == BASE + 0x100
    assert ds2mem.achar_aob(mem, BASE, 0x200, "48 8B 05 ? ? ? ? 99") is None


def test_aob_across_block_boundaries():
    mem = memoria()
    assert ds2mem.achar_aob(mem, BASE, 0x200, "48 8B 05 ? ? ? ? 48 8B 58 38", bloco=0x104) == BASE + 0x100


def test_rel32_resolves_instruction_plus_size_plus_offset():
    mem = memoria()
    assert ds2mem.rel32(mem, BASE + 0x100, 3, 7) == BASE + 0x100 + 7 + 0x80
    assert mem.u64(ds2mem.rel32(mem, BASE + 0x100, 3, 7)) == 0x5000


def test_chain_follows_pointers_and_stops_at_null():
    mem = memoria()
    assert ds2mem.cadeia(mem, 0x5000, [0x0]) == 0x6000
    assert ds2mem.cadeia(mem, 0x5000, [0xD0]) == 0x7000
    assert ds2mem.cadeia(mem, 0x5000, [0x0, 0x8]) is None  # [0x6008] = 0: ponteiro nulo


def test_typed_reads_and_utf16():
    mem = memoria()
    assert mem.f32(0x7000) == 1.5 and mem.utf16(0x7004) == "Teste"


def test_reading_outside_the_regions_is_an_error():
    with pytest.raises(ds2mem.ErroMemoria):
        memoria().ler(0x9999, 4)


def test_missing_process_is_an_error():
    with pytest.raises(ds2mem.ErroMemoria, match="não está aberto"):
        ds2mem.ProcessoWin.abrir("nao-existe-buildsmith.exe")


def _jogo_aberto():
    try:
        out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq DarkSoulsII.exe"], capture_output=True, text=True).stdout
    except OSError:
        return False
    return "DarkSoulsII.exe" in out


@pytest.mark.skipif(not _jogo_aberto(), reason="DS2 fechado")
def test_real_base_a_is_found_in_the_game():
    proc = ds2mem.ProcessoWin.abrir("DarkSoulsII.exe")
    try:
        instr = ds2mem.achar_aob(proc, proc.base_modulo, proc.tamanho_modulo, ds2mem.AOB_BASE_A)
        assert instr is not None and proc.u64(ds2mem.rel32(proc, instr, 3, 7)) != 0
    finally:
        proc.fechar()
