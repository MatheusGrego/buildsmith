import os
import struct
import subprocess
import sys
import time

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
        ds2mem.abrir("nao-existe-buildsmith.exe")


def _jogo_legivel():
    try:
        ds2mem.abrir("DarkSoulsII.exe").fechar()
    except ds2mem.ErroMemoria:
        return False
    return True


@pytest.mark.skipif(not _jogo_legivel(), reason="DS2 fechado (no Linux: ou aberto sem o ajudante)")
def test_real_base_a_is_found_in_the_game():
    proc = ds2mem.abrir("DarkSoulsII.exe")
    try:
        instr = ds2mem.achar_aob(proc, proc.base_modulo, proc.tamanho_modulo, ds2mem.AOB_BASE_A)
        assert instr is not None and proc.u64(ds2mem.rel32(proc, instr, 3, 7)) != 0
    finally:
        proc.fechar()


# ---- Linux (/proc) -----------------------------------------------------------------------------------------------------

linux = pytest.mark.skipif(not sys.platform.startswith("linux"), reason="leitura pelo /proc só no Linux")
EXE_TESTE = "BuildsmithTeste.exe"  # nome diferente do jogo: o teste não pega um DS2 aberto de verdade
MARCA = b"BUILDSMITH-TESTE"

# Processo no papel do jogo no Proton: se chama como o exe, mapeia o arquivo do exe e espera. Com "1" faz como o Wine: o
# processo do jogo nasce de um fork duplo (fica órfão) e o primeiro processo espera, como o proton.
JOGO_FALSO = r"""
import mmap, os, sys, time
exe, pronto, duplo = sys.argv[1], sys.argv[2], sys.argv[3] == "1"
if duplo:
    if os.fork() > 0:
        time.sleep(60)
        os._exit(0)
    if os.fork() > 0:
        os._exit(0)
with open("/proc/self/comm", "w") as fh:
    fh.write(os.path.basename(exe)[:15])
with open(exe, "rb") as fh:
    imagem = mmap.mmap(fh.fileno(), 0, prot=mmap.PROT_READ)
with open(pronto + ".tmp", "w") as fh:
    fh.write(str(os.getpid()))
os.replace(pronto + ".tmp", pronto)
time.sleep(60)
"""


def imagem_pe(caminho):
    """Arquivo com cabeçalho PE: SizeOfImage 0x3000 (maior que o arquivo, como as seções na memória) e uma marca."""
    dados = bytearray(0x1000)
    dados[:2] = b"MZ"
    struct.pack_into("<I", dados, 0x3C, 0x80)
    dados[0x80:0x84] = b"PE\0\0"
    struct.pack_into("<I", dados, 0x80 + 0x50, 0x3000)
    dados[0x200:0x200 + len(MARCA)] = MARCA
    caminho.write_bytes(bytes(dados))


def esperar_pid(pronto, segundos=10.0):
    fim = time.time() + segundos
    while time.time() < fim:
        if pronto.exists():
            return int(pronto.read_text())
        time.sleep(0.05)
    raise AssertionError("o jogo falso não abriu")


def jogo_falso(tmp_path, exe_nome=EXE_TESTE, duplo=False, antes=(), env=None):
    """Sobe o jogo falso (opcionalmente atrás de um comando, ex. o ajudante). Devolve (Popen, pid do jogo, exe)."""
    exe, script, pronto = tmp_path / exe_nome, tmp_path / "jogo.py", tmp_path / "pronto"
    imagem_pe(exe)
    script.write_text(JOGO_FALSO, encoding="utf-8")
    proc = subprocess.Popen([*antes, sys.executable, str(script), str(exe), str(pronto), "1" if duplo else "0"], env=env)
    return proc, esperar_pid(pronto), exe


@linux
def test_linux_reader_reads_the_module_of_a_child_process(tmp_path):
    filho, pid, _ = jogo_falso(tmp_path)
    try:
        proc = ds2mem.ProcessoLinux.abrir(EXE_TESTE)
        assert proc.pid == pid and proc.tamanho_modulo == 0x3000  # do cabeçalho PE, não do tamanho do arquivo
        assert proc.ler(proc.base_modulo + 0x200, len(MARCA)) == MARCA
        assert proc.vivo()
        with pytest.raises(ds2mem.ErroMemoria):
            proc.ler(0x10, 4)  # página sem mapeamento
        filho.kill()
        filho.wait()
        assert not proc.vivo()
        proc.fechar()
    finally:
        if filho.poll() is None:
            filho.kill()
            filho.wait()


def test_pid_and_module_come_from_proc(tmp_path):
    for pid, comm, cmd in ((10, "DarkSoulsII.exe", b"Z:\\jogo\\DarkSoulsII.exe"), (12, "DarkSoulsII.exe", b"DarkSoulsII.exe"),
                           (20, "bash", b"bash"), (30, "BuildsmithTeste", b"python3 /tmp/x/BuildsmithTeste.exe")):
        d = tmp_path / str(pid)
        d.mkdir()
        (d / "comm").write_text(comm + "\n", encoding="utf-8")
        (d / "cmdline").write_bytes(cmd)
    (tmp_path / "self").mkdir()
    assert sorted(ds2mem.pids_de("DarkSoulsII.exe", tmp_path)) == [10, 12]
    assert ds2mem.pid_de("DarkSoulsII.exe", tmp_path) == 12  # o mais novo
    assert ds2mem.pid_de("BuildsmithTeste.exe", tmp_path) == 30  # nome maior que 15: confere no cmdline
    assert ds2mem.pid_de("outro.exe", tmp_path) is None
    (tmp_path / "12" / "maps").write_text(
        "140000000-140001000 r--p 00000000 08:01 1 /home/j/Steam/steamapps/common/DS2/Game/DarkSoulsII.exe\n"
        "140001000-140800000 r-xp 00001000 08:01 1 /home/j/Steam/steamapps/common/DS2/Game/DarkSoulsII.exe\n"
        "7f0000000000-7f0000001000 rw-p 00000000 00:00 0 \n", encoding="utf-8")
    assert ds2mem.modulo_linux(12, "DarkSoulsII.exe", tmp_path) == (0x140000000, 0x140800000)
    with pytest.raises(ds2mem.ErroMemoria, match="não achei"):
        ds2mem.modulo_linux(12, "outro.exe", tmp_path)


@linux
def test_without_permission_and_without_helper_says_how_to_fix(tmp_path, monkeypatch):
    filho, _, _ = jogo_falso(tmp_path)
    try:
        abrir_os = os.open

        def negar(caminho, *args, **kwargs):  # o que o Yama faz com quem não é ancestral do jogo
            if str(caminho).endswith("/mem"):
                raise PermissionError(13, "Permission denied")
            return abrir_os(caminho, *args, **kwargs)
        monkeypatch.setattr(ds2mem.os, "open", negar)
        with pytest.raises(ds2mem.ErroMemoria, match="vivo_linux"):
            ds2mem.ProcessoLinux.abrir(EXE_TESTE, ajudante=tmp_path / "sem-ajudante.sock")
    finally:
        filho.kill()
        filho.wait()
