"""release/construir.py: o ícone do lançador (recurso do Windows em .syso) e o próprio lançador em Go."""
import shutil
import struct
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "release"))
import construir  # noqa: E402


def ico_de(imagens: list[bytes]) -> bytes:
    cab = struct.pack("<3H", 0, 1, len(imagens))
    off, entradas = 6 + 16 * len(imagens), b""
    for i, img in enumerate(imagens):
        lado = 16 * (i + 1)
        entradas += struct.pack("<4B2H2I", lado, lado, 0, 0, 1, 32, len(img), off)
        off += len(img)
    return cab + entradas + b"".join(imagens)


def diretorio(rsrc: bytes, off: int) -> list[tuple[int, int]]:
    named, ids = struct.unpack_from("<HH", rsrc, off + 12)
    return [struct.unpack_from("<II", rsrc, off + 16 + 8 * k) for k in range(named + ids)]


def test_icon_resource_object_has_icons_group_and_relocations():
    imagens = [b"\x89PNG-16-" + b"a" * 5, b"\x89PNG-32-" + b"b" * 11]
    obj = construir.syso_do_icone(ico_de(imagens))
    maquina, secoes, _t, simbolos_off, n_simbolos, opt, _c = struct.unpack_from("<HHIIIHH", obj, 0)
    assert (maquina, secoes, opt, n_simbolos) == (0x8664, 1, 0, 1)
    nome, _vs, _va, tamanho, dados_off, reloc_off, _l, n_reloc, _nl, carac = struct.unpack_from("<8sIIIIIIHHI", obj, 20)
    assert nome == b".rsrc\0\0\0" and carac == 0x40000040 and n_reloc == 3  # 2 imagens + o grupo
    rsrc = obj[dados_off:dados_off + tamanho]
    tipos = diretorio(rsrc, 0)
    assert [t for t, _ in tipos] == [3, 14]  # RT_ICON, RT_GROUP_ICON, em ordem

    def dado(sub_off):
        nivel2 = diretorio(rsrc, sub_off & 0x7FFFFFFF)
        out = []
        for ident, nivel3 in nivel2:
            (_lang, entrada), = diretorio(rsrc, nivel3 & 0x7FFFFFFF)
            rva, tam = struct.unpack_from("<II", rsrc, entrada)
            out.append((ident, rsrc[rva:rva + tam], entrada))
        return out

    icones, (grupo,) = dado(tipos[0][1]), dado(tipos[1][1])
    assert [(i, b) for i, b, _ in icones] == [(1, imagens[0]), (2, imagens[1])]
    _r, tipo, n = struct.unpack_from("<3H", grupo[1], 0)
    assert (tipo, n) == (1, 2)
    assert [struct.unpack_from("<I", grupo[1], 6 + 14 * k + 8)[0] for k in range(2)] == [len(b) for b in imagens]
    assert [struct.unpack_from("<H", grupo[1], 6 + 14 * k + 12)[0] for k in range(2)] == [1, 2]
    relocs = [struct.unpack_from("<IIH", obj, reloc_off + 10 * k) for k in range(n_reloc)]
    assert sorted(r[0] for r in relocs) == sorted(e for _, _, e in icones + [grupo])  # o RVA de cada dado
    assert all(r[1:] == (0, 3) for r in relocs)  # símbolo .rsrc, IMAGE_REL_AMD64_ADDR32NB
    assert obj[simbolos_off:simbolos_off + 8] == b".rsrc\0\0\0"


@pytest.mark.skipif(shutil.which("go") is None, reason="sem Go para testar o lançador")
def test_launcher_go_tests_pass():
    r = subprocess.run(["go", "test", "./..."], cwd=RAIZ / "release" / "lancador", capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=300)
    assert r.returncode == 0, r.stdout + r.stderr
