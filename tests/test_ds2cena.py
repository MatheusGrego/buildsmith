import struct
import zlib
import pytest

import ds2cena


def build_dcx(data: bytes) -> bytes:
    compressed = zlib.compress(data)
    dca_header = b"DCA\x00" + struct.pack(">I", 8)
    dflt_header = b"DFLT\x00\x00\x00\x00"
    dcx_head = b"DCX\x00\x00\x01\x00\x00\x00\x00\x00\x18\x00\x00\x00$" + dflt_header + dca_header
    return dcx_head + compressed


def build_bhf4(files: dict[str, bytes]) -> tuple[bytes, bytes]:
    """Constrói um par (bhd, bdt) de binder BHF4 para testes."""
    count = len(files)
    esz = 0x24
    bhd = bytearray(0x40 + count * esz)
    bhd[:4] = b"BHF4"
    struct.pack_into("<i", bhd, 0x0C, count)
    struct.pack_into("<q", bhd, 0x20, esz)
    bhd[0x30] = 0  # unicode = False (latin-1)

    bdt = bytearray()
    names_data = bytearray()

    for i, (name, content) in enumerate(files.items()):
        h = 0x40 + i * esz
        offset = len(bdt)
        size = len(content)
        bdt += content

        name_off = 0x40 + count * esz + len(names_data)
        names_data += name.encode("latin-1") + b"\0"

        struct.pack_into("<q", bhd, h + 0x08, size)
        struct.pack_into("<I", bhd, h + 0x18, offset)
        struct.pack_into("<I", bhd, h + esz - 4, name_off)

    return bytes(bhd + names_data), bytes(bdt)


def test_ler_bhf4():
    raw_flv = b"FLVER\x00fake_model"
    files = {
        "m10_04_00_00\\m0000.flv.dcx": build_dcx(raw_flv),
        "m10_04_00_00\\m0000.mte.dcx": build_dcx(b"material_info"),
        "m10_04_00_00\\other.txt": b"texto normal",
    }
    bhd, bdt = build_bhf4(files)

    lidos = ds2cena.ler_bhf4(bhd, bdt, filtro_ext=".flv")
    assert "m0000.flv" in lidos
    assert lidos["m0000.flv"] == raw_flv
    assert "other.txt" not in lidos
    assert "m0000.mte" not in lidos


def test_ler_flver_minimo():
    """Valida decodificação de um FLVER2 com 1 malha, 3 vértices e 1 triângulo."""
    data_off = 0x400
    n_dummy, n_mat, n_bone, n_mesh, n_vb, n_fs, n_lay, n_tex = 0, 1, 0, 1, 1, 1, 1, 1

    header = bytearray(data_off)
    header[:6] = b"FLVER\x00"
    header[6:8] = b"L\x00"
    struct.pack_into("<8i", header, 0x08, 0x20010, data_off, 0, n_dummy, n_mat, n_bone, n_mesh, n_vb)
    header[0x48] = 16  # idx_size
    header[0x49] = 1   # unicode = True
    struct.pack_into("<3i", header, 0x50, n_fs, n_lay, n_tex)

    # Strings em 0x200+
    str_off = 0x200
    header[str_off:str_off + 12] = "Pedra\0".encode("utf-16-le")
    tex_path_off = 0x220
    header[tex_path_off:tex_path_off + 24] = "pedra_d.tga\0".encode("utf-16-le")
    tex_type_off = 0x260
    header[tex_type_off:tex_type_off + 34] = "g_DiffuseTexture\0".encode("utf-16-le")

    off = 0x80
    struct.pack_into("<4i", header, off, str_off, str_off, 1, 0) # Mat 0
    off += n_mat * 0x20

    # Mesh 0: mat=0, fs_count=1, vb_count=1
    fs_idx_off = 0x180
    vb_idx_off = 0x184
    struct.pack_into("<i", header, off + 4, 0)
    struct.pack_into("<4i", header, off + 0x20, 1, fs_idx_off, 1, vb_idx_off)
    struct.pack_into("<i", header, fs_idx_off, 0)
    struct.pack_into("<i", header, vb_idx_off, 0)
    off += n_mesh * 0x30

    # Faceset 0
    ioff = 0
    icount = 3
    struct.pack_into("<I??", header, off, 0, False, True)
    struct.pack_into("<5i", header, off + 8, icount, ioff, 6, 0, 16)
    off += n_fs * 0x20

    # VB 0: lay=0, vsize=24, vcount=3, boff=8
    boff = 8
    struct.pack_into("<8i", header, off, 0, 0, 24, 3, 0, 0, 72, boff)
    off += n_vb * 0x20

    # Layout 0
    moff = 0x140
    struct.pack_into("<4i", header, off, 3, 0, 0, moff)
    off += n_lay * 0x10

    # Texture 0
    struct.pack_into("<2i", header, off, tex_path_off, tex_type_off)

    # Layout 0 members at moff (3 membros de 20 bytes = 60 bytes, 0x140..0x17C)
    struct.pack_into("<5i", header, moff, 0, 0, 2, 0, 0)          # Pos
    struct.pack_into("<5i", header, moff + 0x14, 0, 12, 17, 3, 0)    # Normal
    struct.pack_into("<5i", header, moff + 0x28, 0, 16, 21, 5, 0)    # UV

    # Dados (data_off): 6 bytes índices + 2 bytes alinhamento (boff = 8), depois 3 vértices
    body = bytearray()
    body += struct.pack("<3H", 0, 1, 2) + bytes(2)
    v0 = struct.pack("<3f", 1.0, 2.0, 3.0) + bytes([127, 254, 127, 0]) + struct.pack("<2e", 0.0, 1.0) + bytes(4)
    v1 = struct.pack("<3f", 4.0, 5.0, 6.0) + bytes([127, 254, 127, 0]) + struct.pack("<2e", 0.5, 0.5) + bytes(4)
    v2 = struct.pack("<3f", 7.0, 8.0, 9.0) + bytes([127, 254, 127, 0]) + struct.pack("<2e", 1.0, 0.0) + bytes(4)
    body += v0 + v1 + v2

    res = ds2cena.ler_flver(bytes(header + body))
    assert len(res["malhas"]) == 1
    m = res["malhas"][0]
    assert m["indices"] == [0, 1, 2]
    assert len(m["vertices"]) == 3
    assert m["vertices"][0] == (1.0, 2.0, 3.0)
    assert m["uvs"][0] == pytest.approx((0.0, 1.0), abs=1e-3)
    assert m["textura_difusa"] == "pedra_d"


def test_limitar_dds():
    def make_dds(w, h, mips, fourcc=b"DXT1"):
        h_bytes = bytearray(128)
        h_bytes[:4] = b"DDS "
        struct.pack_into("<6I", h_bytes, 4, 124, 0x081007, h, w, 0, 1)
        struct.pack_into("<I", h_bytes, 28, mips)
        struct.pack_into("<2I", h_bytes, 76, 32, 4)
        h_bytes[84:88] = fourcc
        total = 0
        cw, ch = w, h
        block = 8 if fourcc == b"DXT1" else 16
        for _ in range(mips):
            bw = max(1, (cw + 3) // 4)
            bh = max(1, (ch + 3) // 4)
            total += bw * bh * block
            cw = max(1, cw >> 1)
            ch = max(1, ch >> 1)
        return bytes(h_bytes) + bytes(total)

    d = make_dds(1024, 512, 10, b"DXT1")
    r = ds2cena.limitar_dds(d, 512)
    nh, nw = struct.unpack_from("<2I", r, 12)
    nmips = struct.unpack_from("<I", r, 28)[0]
    assert (nw, nh, nmips) == (512, 256, 9)
    assert len(r) < len(d)


def test_extrair_dds_tpf():
    dds = b"DDS " + bytes(124)
    b = bytearray()
    b += b"TPF\0"
    b += struct.pack("<3I", len(dds), 1, 0x02)
    name_bytes = "rocha_d.dds".encode("latin-1") + b"\0"
    name_off = 0x10 + 0x14
    data_off = name_off + len(name_bytes)
    b += struct.pack("<5I", data_off, len(dds), 0, name_off, 0)
    b += name_bytes
    b += dds

    out = ds2cena.extrair_dds_tpf(bytes(b))
    assert "rocha_d" in out
    assert out["rocha_d"] == dds


def test_empacotar_geometria():
    modelos = {
        "m0000": {
            "bb": ((-10.0, 0.0, -10.0), (10.0, 5.0, 10.0)),
            "malhas": [
                {
                    "material_idx": 0,
                    "textura_difusa": "pedra_d",
                    "vertices": [(0.0, 1.0, 2.0), (3.0, 4.0, 5.0), (6.0, 7.0, 8.0)],
                    "normais": [(0.0, 1.0, 0.0), (0.0, 1.0, 0.0), (0.0, 1.0, 0.0)],
                    "uvs": [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)],
                    "indices": [0, 1, 2],
                }
            ],
        }
    }
    geo_bin, cat = ds2cena.empacotar_geometria(modelos)
    assert "m0000" in cat["modelos"]
    m = cat["modelos"]["m0000"]["malhas"][0]
    assert m["v_count"] == 3
    assert m["i_count"] == 3
    assert m["idx_size"] == 2
    # Valida bytes de vértices
    v0_floats = struct.unpack_from("<8f", geo_bin, m["v_off"])
    assert v0_floats[:3] == (0.0, 1.0, 2.0)
    assert v0_floats[3:6] == (0.0, 1.0, 0.0)
    assert v0_floats[6:8] == (0.0, 0.0)
    # Valida índices
    inds = struct.unpack_from("<3H", geo_bin, m["i_off"])
    assert inds == (0, 1, 2)


def test_msb_instancias():
    def utf16z(text: str) -> bytes:
        return text.encode("utf-16-le") + bytes(2)

    data = bytearray(b"MSB " + struct.pack("<ii", 1, 0x10) + bytes(4))

    # Lista 1: MODEL_PARAM_ST
    head_m = len(data)
    data += bytes(16 + 8 * 2)
    nome_m = len(data)
    data += utf16z("MODEL_PARAM_ST")
    while len(data) % 8:
        data += b"\0"
    m_entry = len(data)
    data += struct.pack("<q", 0x20) + bytes(0x18) + utf16z("m0000")

    # Lista 2: PARTS_PARAM_ST
    while len(data) % 8:
        data += b"\0"
    head_p = len(data)
    data += bytes(16 + 8 * 2)
    nome_p = len(data)
    data += utf16z("PARTS_PARAM_ST")
    while len(data) % 8:
        data += b"\0"
    p_entry = len(data)
    p_rec = bytearray(0x40)
    struct.pack_into("<q", p_rec, 0, 0x40)
    p_rec[8] = 0  # tipo 0 (mapa)
    struct.pack_into("<h", p_rec, 0x0C, 0)
    struct.pack_into("<3f", p_rec, 0x10, 10.0, 20.0, 30.0)
    struct.pack_into("<3f", p_rec, 0x1C, 0.0, 45.0, 0.0)
    struct.pack_into("<3f", p_rec, 0x28, 1.0, 1.0, 1.0)
    data += p_rec + utf16z("m0000_0000")

    struct.pack_into("<ii", data, head_m, 5, 2)
    struct.pack_into("<q", data, head_m + 8, nome_m)
    struct.pack_into("<2q", data, head_m + 16, m_entry, head_p)

    struct.pack_into("<ii", data, head_p, 5, 2)
    struct.pack_into("<q", data, head_p + 8, nome_p)
    struct.pack_into("<2q", data, head_p + 16, p_entry, 0)

    insts, mods = ds2cena.msb_instancias(bytes(data))
    assert len(insts) == 1
    assert "m0000" in mods
    assert insts[0]["modelo"] == "m0000"
    assert insts[0]["pos"] == [10.0, 20.0, 30.0]
    assert insts[0]["rot"] == [0.0, 45.0, 0.0]


def test_extrair_cena_majula():
    from pathlib import Path
    import json
    p = Path.home() / ".buildsmith" / "cache" / "ds2" / "cena" / "m10_04_00_00" / "cena.json"
    if not p.exists():
        pytest.skip("Cache de Majula não gerado ainda")
    cena = json.loads(p.read_text("utf-8"))
    assert cena["versao"] == 1
    assert cena["area"] == "m10_04_00_00"
    assert len(cena["instancias"]) > 0
    assert len(cena["modelos"]) > 0
    assert len(cena["alturas"]) > 0


