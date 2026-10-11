import json
import math
import struct
import zlib
from pathlib import Path

import pytest

import ds2cena

GAME = Path(r"C:/Program Files (x86)/Steam/steamapps/common/Dark Souls II Scholar of the First Sin/Game")


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


def build_flver(malhas: list[dict], version: int = 0x20010, ossos: list[dict] | None = None) -> bytes:
    """FLVER2 "L" mínimo. Cada malha: mtd, texturas [(caminho, tipo)], vertices [(pos, normal_bytes4, uv_int16)],
    facesets [(flags, strip, indices)] e, opcionais, dinamica, no (osso da malha) e ossos_malha (lista de ossos).
    Layout: posição Float3, normal Byte4B (UByte4, 0x11), UV tipo 0x15 (int16). ossos: [{t, r, s, pai}]."""
    ossos = ossos or []
    n_mat = n_mesh = n_vb = n_lay = len(malhas)
    n_fs = sum(len(m["facesets"]) for m in malhas)
    n_tex = sum(len(m["texturas"]) for m in malhas)
    off_mat = 0x80
    off_osso = off_mat + n_mat * 0x20
    off_mesh = off_osso + len(ossos) * 0x80
    off_fs = off_mesh + n_mesh * 0x30
    off_vb = off_fs + n_fs * 0x20
    off_lay = off_vb + n_vb * 0x20
    off_tex = off_lay + n_lay * 0x10
    cauda = bytearray()  # listas de índices, membros de layout e textos, depois do cabeçalho
    base_cauda = off_tex + n_tex * 0x20

    def poe(b: bytes) -> int:
        while len(cauda) % 4:
            cauda.append(0)
        o = base_cauda + len(cauda)
        cauda.extend(b)
        return o

    dados = bytearray()  # índices e vértices (relativos a data_off)

    def poe_dados(b: bytes) -> int:
        while len(dados) % 4:
            dados.append(0)
        o = len(dados)
        dados.extend(b)
        return o

    cab = bytearray(base_cauda)
    cab[:6] = b"FLVER\x00"
    cab[6:8] = b"L\x00"
    cab[0x48] = 16
    cab[0x49] = 1
    struct.pack_into("<3i", cab, 0x50, n_fs, n_lay, n_tex)
    for k, o in enumerate(ossos):
        struct.pack_into("<3f", cab, off_osso + k * 0x80, *o.get("t", (0, 0, 0)))
        struct.pack_into("<3f", cab, off_osso + k * 0x80 + 0x10, *o.get("r", (0, 0, 0)))
        struct.pack_into("<h", cab, off_osso + k * 0x80 + 0x1C, o.get("pai", -1))
        struct.pack_into("<3f", cab, off_osso + k * 0x80 + 0x20, *o.get("s", (1, 1, 1)))
    fs_i = tex_i = 0
    for k, m in enumerate(malhas):
        nome_o = poe("Material\0".encode("utf-16-le"))
        mtd_o = poe(f"N:\\mtd\\{m['mtd']}\0".encode("utf-16-le"))
        struct.pack_into("<4i", cab, off_mat + k * 0x20, nome_o, mtd_o, len(m["texturas"]), tex_i)
        for caminho, tipo in m["texturas"]:
            struct.pack_into("<2i", cab, off_tex + tex_i * 0x20, poe(f"{caminho}\0".encode("utf-16-le")), poe(f"{tipo}\0".encode("utf-16-le")))
            tex_i += 1
        fs_lista = list(range(fs_i, fs_i + len(m["facesets"])))
        for flags, strip, indices in m["facesets"]:
            ioff = poe_dados(struct.pack(f"<{len(indices)}H", *indices))
            o = off_fs + fs_i * 0x20
            struct.pack_into("<I??", cab, o, flags, strip, False)
            struct.pack_into("<5i", cab, o + 8, len(indices), ioff, len(indices) * 2, 0, 16)
            fs_i += 1
        o = off_mesh + k * 0x30
        cab[o] = 1 if m.get("dinamica") else 0
        struct.pack_into("<i", cab, o + 4, k)
        om = m.get("ossos_malha", [])
        struct.pack_into("<2i", cab, o + 0x10, m.get("no", -1), len(om))
        struct.pack_into("<i", cab, o + 0x1C, poe(struct.pack(f"<{len(om)}i", *om)) if om else 0)
        struct.pack_into("<4i", cab, o + 0x20, len(fs_lista), poe(struct.pack(f"<{len(fs_lista)}i", *fs_lista)), 1, poe(struct.pack("<i", k)))
        vbytes = b"".join(struct.pack("<3f", *p) + bytes(n) + struct.pack("<2h", *uv) for p, n, uv in m["vertices"])
        boff = poe_dados(vbytes)
        struct.pack_into("<8i", cab, off_vb + k * 0x20, 0, k, 20, len(m["vertices"]), 0, 0, len(vbytes), boff)
        membros = struct.pack("<5i", 0, 0, 0x02, 0, 0) + struct.pack("<5i", 0, 12, 0x11, 3, 0) + struct.pack("<5i", 0, 16, 0x15, 5, 0)
        struct.pack_into("<4i", cab, off_lay + k * 0x10, 3, 0, 0, poe(membros))
    corpo = bytes(cab) + bytes(cauda)
    data_off = (len(corpo) + 15) // 16 * 16
    corpo += bytes(data_off - len(corpo))
    final = bytearray(corpo) + dados
    struct.pack_into("<8i", final, 0x08, version, data_off, len(dados), 0, n_mat, len(ossos), n_mesh, n_vb)
    struct.pack_into("<3f", final, 0x28, -1.0, 0.0, -1.0)
    struct.pack_into("<3f", final, 0x34, 1.0, 2.0, 1.0)
    return bytes(final)


CIMA = [127, 254, 127, 0]  # normal Byte4B (0, 1, 0)


def tri_malha(mtd="GI_M[DB].mtd", facesets=None, uv=((0, 0), (2048, 0), (2048, 2048))):
    return {"mtd": mtd, "texturas": [("N:\\tex\\pedra_n.tga", "g_BumpmapTexture"), ("N:\\tex\\Pedra_D.tga", "g_DiffuseTexture")],
            "vertices": [((0.0, 0.0, 0.0), CIMA, uv[0]), ((1.0, 0.0, 0.0), CIMA, uv[1]), ((1.0, 0.0, 1.0), CIMA, uv[2])],
            "facesets": facesets or [(0, False, [0, 1, 2])]}


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


def test_ler_flver_uv_int16_normal_e_difusa():
    """UV do DS2 é int16 ÷ 2048 (versão 0x20010), normal Byte4B; a difusa vem pelo tipo, não pela ordem."""
    res = ds2cena.ler_flver(build_flver([tri_malha()]))
    assert len(res["malhas"]) == 1
    m = res["malhas"][0]
    assert m["indices"] == [0, 1, 2]
    assert m["vertices"][2] == (1.0, 0.0, 1.0)
    assert m["uvs"] == [pytest.approx((0.0, 0.0)), pytest.approx((1.0, 0.0)), pytest.approx((1.0, 1.0))]
    assert m["normais"][0] == pytest.approx((0.0, 1.0, 0.0))
    assert m["textura_difusa"] == "pedra_d"
    assert m["tipo"] == "opaco" and m["mtd"] == "GI_M[DB].mtd"


def test_ler_flver_ignora_caixa_dummy():
    m = tri_malha()
    m["texturas"] = [("N:\\tex\\dummy128.tga", "g_DiffuseTexture")]
    assert ds2cena.ler_flver(build_flver([m]))["malhas"][0]["tipo"] == "ignorar"


def test_ler_flver_uv_antigo_usa_1024():
    res = ds2cena.ler_flver(build_flver([tri_malha(uv=((0, 0), (1024, 0), (1024, 1024)))], version=0x2000C))
    assert res["malhas"][0]["uvs"][2] == pytest.approx((1.0, 1.0))


def test_ler_flver_pula_lod_e_desfaz_strip():
    # 1º faceset é LOD (flag 0x01000000); o 2º é o LOD0 em triangle strip, com um degenerado no fim
    m = tri_malha(facesets=[(0x01000000, False, [0, 1, 2]), (0, True, [1, 2, 0, 0])])
    res = ds2cena.ler_flver(build_flver([m]))
    assert res["malhas"][0]["indices"] == [1, 2, 0]


def test_triangulos_de_strip():
    assert ds2cena.triangulos_de_strip([0, 1, 2, 3]) == [0, 1, 2, 3, 2, 1]
    assert ds2cena.triangulos_de_strip([0, 1, 2, 0xFFFF, 3, 4, 5]) == [0, 1, 2, 3, 4, 5]
    assert ds2cena.triangulos_de_strip([0, 0, 1, 2]) == [2, 1, 0]


def test_classe_material():
    assert ds2cena.classe_material("N:\\FRPG2\\mtd\\SkyDome.mtd") == "ignorar"
    assert ds2cena.classe_material("NoLit[D]_Alp.mtd") == "ignorar"  # cartões pretos de neblina na entrada das cavernas
    assert ds2cena.classe_material("GI_M[D]_Alp_1bit.mtd") == "recorte"
    assert ds2cena.classe_material("Grass[D]_Alp_1bit.mtd") == "recorte"
    assert ds2cena.classe_material("GI_M[DB][decal]_Alp.mtd") == "decal"
    assert ds2cena.classe_material("Water[DSB][M]_Alp.mtd") == "agua"
    assert ds2cena.classe_material("GI_M[DB][M_mask].mtd") == "opaco"


def test_textura_difusa():
    assert ds2cena.textura_difusa([("a\\x_n.tga", "g_BumpmapTexture"), ("a\\X_D.tga", "g_DiffuseTexture")]) == "x_d"
    assert ds2cena.textura_difusa([("a\\x_n.tga", ""), ("a\\y_d.tga", "")]) == "y_d"
    assert ds2cena.textura_difusa([("a\\x_n.tga", "g_BumpmapTexture")]) is None


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
    name_bytes = "Rocha_d.dds".encode("latin-1") + b"\0"
    name_off = 0x10 + 0x14
    data_off = name_off + len(name_bytes)
    b += struct.pack("<5I", data_off, len(dds), 0, name_off, 0)
    b += name_bytes
    b += dds

    out = ds2cena.extrair_dds_tpf(bytes(b))
    assert out == {"rocha_d": dds}


def test_empacotar_geometria():
    modelos = {"m0000": ds2cena.ler_flver(build_flver([tri_malha(), tri_malha(mtd="SkyDome.mtd")]))}
    geo, cat = ds2cena.empacotar_geometria(modelos)
    malhas = cat["modelos"]["m0000"]["malhas"]
    assert len(malhas) == 1  # a do céu fica de fora
    m = malhas[0]
    assert (m["v_count"], m["i_count"], m["idx_size"], m["tipo"], m["tex"]) == (3, 3, 2, "opaco", "pedra_d")
    assert all(m[k] % 4 == 0 for k in ("pos", "nrm", "uv", "i_off"))
    assert struct.unpack_from("<3f", geo, m["pos"] + 24) == (1.0, 0.0, 1.0)
    assert struct.unpack_from("<4b", geo, m["nrm"]) == (0, 127, 0, 0)
    assert struct.unpack_from("<2f", geo, m["uv"] + 16) == (1.0, 1.0)
    assert struct.unpack_from("<3H", geo, m["i_off"]) == (0, 1, 2)
    assert m["i_off"] + 6 <= len(geo)


def test_matriz_instancia_gira_x_depois_z_depois_y():
    m = ds2cena.matriz_instancia((10, 20, 30), (0, 90, 0), (1, 1, 1))
    assert ds2cena.aplicar_matriz(m, (1, 0, 0)) == pytest.approx((10, 20, 29))  # +x vira -z com 90° em Y
    m = ds2cena.matriz_instancia((0, 0, 0), (90, 0, 90), (1, 1, 1))
    assert ds2cena.aplicar_matriz(m, (0, 1, 0)) == pytest.approx((0, 0, 1), abs=1e-6)  # X primeiro: (0,1,0) -> (0,0,1)
    m = ds2cena.matriz_instancia((0, 0, 0), (0, 0, 0), (2, 3, 4))
    assert ds2cena.aplicar_matriz(m, (1, 1, 1)) == pytest.approx((2, 3, 4))
    assert len(m) == 16 and m[15] == 1.0


def test_caixa_mundo():
    m = ds2cena.matriz_instancia((100, 0, 0), (0, 90, 0), (1, 1, 1))
    lo, hi = ds2cena.caixa_mundo(m, ((0, 0, 0), (2, 1, 4)))
    assert lo == pytest.approx([100, 0, -2]) and hi == pytest.approx([104, 1, 0])


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
    data += struct.pack("<q", 0x20) + bytes(0x18) + utf16z("M0000")

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
    assert mods == {"m0000"}
    assert insts[0]["modelo"] == "m0000"
    assert insts[0]["pos"] == [10.0, 20.0, 30.0]
    assert insts[0]["rot"] == [0.0, 45.0, 0.0]
    assert insts[0]["matriz"][12:15] == [10.0, 20.0, 30.0]


def test_cena_pronta_confere_versao_e_assinatura(tmp_path):
    (tmp_path / "geo.bin.gz").write_bytes(b"\0")
    (tmp_path / "cena.json").write_text(json.dumps({"versao": ds2cena.CENA_VERSAO, "assinatura": "a"}), encoding="utf-8")
    assert ds2cena.cena_pronta(tmp_path, "a")["assinatura"] == "a"
    assert ds2cena.cena_pronta(tmp_path, "b") is None  # jogo atualizado: extrai de novo
    (tmp_path / "cena.json").write_text(json.dumps({"versao": 1, "assinatura": "a"}), encoding="utf-8")
    assert ds2cena.cena_pronta(tmp_path) is None  # versão antiga (UV errada): extrai de novo


def test_extrair_cena_recusa_area_invalida(tmp_path):
    with pytest.raises(Exception):
        ds2cena.extrair_cena(tmp_path, "../../etc", tmp_path)


@pytest.mark.skipif(not (GAME / "GameDataEbl.bhd").exists(), reason="DS2 SotFS não instalado")
def test_extrair_cena_majula_com_o_jogo(tmp_path):
    cena = ds2cena.extrair_cena(GAME, "m10_04_00_00", tmp_path)
    pasta = tmp_path / "cena" / "m10_04_00_00"
    assert cena["versao"] == ds2cena.CENA_VERSAO and cena["area"] == "m10_04_00_00"
    assert len(cena["instancias"]) >= 100 and len(cena["texturas"]) >= 50
    assert cena["chao"] and cena["chao"]["i_count"] > 300  # o navmesh do mapa 2D, para o corte de interior
    assert cena["segundos"] < 60 and cena["mb"] <= 30  # orçamento da spec
    geo = len(__import__("gzip").decompress((pasta / "geo.bin.gz").read_bytes()))
    for mod in cena["modelos"].values():
        for m in mod["malhas"]:
            assert m["i_off"] + m["i_count"] * m["idx_size"] <= geo
            assert m["tipo"] in ds2cena.TIPOS_MATERIAL
            assert m["tex"] is None or (pasta / "tex" / f"{m['tex']}.dds").is_file()
    assert all(len(i["matriz"]) == 16 and i["modelo"] in cena["modelos"] for i in cena["instancias"])
    assert not list((tmp_path / "cena").glob(".*.tmp-*"))  # gravação atômica não deixa resto
    assert ds2cena.extrair_cena(GAME, "m10_04_00_00", tmp_path)["segundos"] == cena["segundos"]  # cache


def build_bnd4(files: dict[str, bytes], esz: int = 0x24, formato: int = 0x74) -> bytes:
    """BND4 de um arquivo só (cabeçalho e dados juntos). esz 0x24 = layout do DS2; 0x20 = sem compressão (formato 0x0A)."""
    count = len(files)
    cab = bytearray(0x40 + count * esz)
    cab[:4] = b"BND4"
    cab[0x0A] = 0  # bits invertidos: o formato é lido de trás para frente
    struct.pack_into("<i", cab, 0x0C, count)
    struct.pack_into("<q", cab, 0x10, 0x40)
    struct.pack_into("<q", cab, 0x20, esz)
    cab[0x30] = 1
    cab[0x31] = formato
    nomes = bytearray()
    base_nomes = len(cab)
    for name in files:
        nomes += name.encode("utf-16-le") + b"\0\0"
    dados_ini = base_nomes + len(nomes)
    dados = bytearray()
    off_nome = base_nomes
    for i, (name, content) in enumerate(files.items()):
        h = 0x40 + i * esz
        struct.pack_into("<q", cab, h + 0x08, len(content))
        if esz == 0x24:
            struct.pack_into("<q", cab, h + 0x10, len(content))
            struct.pack_into("<I", cab, h + 0x18, dados_ini + len(dados))
            struct.pack_into("<i", cab, h + 0x1C, i)
            struct.pack_into("<I", cab, h + 0x20, off_nome)
        else:  # sem compressão: tamanho, offset de 4 bytes, ID e nome
            struct.pack_into("<I", cab, h + 0x10, dados_ini + len(dados))
            struct.pack_into("<i", cab, h + 0x14, i)
            struct.pack_into("<I", cab, h + 0x18, off_nome)
        off_nome += len(name.encode("utf-16-le")) + 2
        dados += content
    return bytes(cab + nomes + dados)


def test_ler_binder_bnd4_com_dcx_e_layouts():
    b = build_bnd4({"N:\\FRPG2\\model\\obj\\o00_0300\\o00_0300.flv.dcx": build_dcx(b"FLVER\0x"), "o00_0300.tpf": b"TPF\0y"})
    arqs = ds2cena.ler_binder(build_dcx(b))  # o binder inteiro também pode vir em DCX
    assert arqs == {"o00_0300.flv": b"FLVER\0x", "o00_0300.tpf": b"TPF\0y"}
    assert ds2cena.ler_binder(b, ".tpf") == {"o00_0300.tpf": b"TPF\0y"}
    outro = build_bnd4({"a.flv": b"123"}, esz=0x20, formato=0x0A)  # byte 0x0A = 0: formato lido como está (IDs e nomes)
    assert ds2cena.ler_binder(outro) == {"a.flv": b"123"}
    with pytest.raises(ds2cena.CenaError):
        ds2cena.ler_binder(b"XXXX" + bytes(60))


def test_ossos_compoem_com_o_pai():
    pai = {"t": (0, 5, 0), "r": (0, math.pi / 2, 0), "s": (1, 1, 1), "pai": -1}
    filho = {"t": (2, 0, 0), "r": (0, 0, 0), "s": (1, 1, 1), "pai": 0}
    mundo = ds2cena.mundo_dos_ossos([pai, filho])
    assert ds2cena.aplicar_matriz(mundo[1], (0, 0, 0)) == pytest.approx((0, 5, -2), abs=1e-5)  # girou 90° em Y e subiu


def test_flver_malha_rigida_vai_para_o_osso_e_dinamica_fica():
    tri = lambda **k: {**tri_malha(), **k}  # noqa: E731
    ossos = [{"t": (0, 0, 0)}, {"t": (10, 0, 0)}, {"t": (0, 3, 0)}]
    rigida_no = tri(no=1)  # normal UByte4 mas sem lista de ossos: vai pelo osso da malha
    por_vertice = tri(ossos_malha=[0, 2], vertices=[((0.0, 0.0, 0.0), [127, 254, 127, 1], (0, 0)),
                                                     ((1.0, 0.0, 0.0), [127, 254, 127, 0], (0, 0)),
                                                     ((1.0, 0.0, 1.0), [127, 254, 127, 1], (0, 0))])
    dinamica = tri(dinamica=True, no=1)
    flv = build_flver([rigida_no, por_vertice, dinamica], ossos=ossos)
    a, b, c = ds2cena.ler_flver(flv, ossos=True)["malhas"]
    assert a["vertices"][1] == pytest.approx((11.0, 0.0, 0.0))
    assert [tuple(v) for v in b["vertices"]] == [pytest.approx((0, 3, 0)), pytest.approx((1, 0, 0)), pytest.approx((1, 3, 1))]
    assert c["vertices"][1] == pytest.approx((1.0, 0.0, 0.0))  # com pesos de osso: já no espaço do modelo
    assert len(a["normais"][0]) == 3  # o 4º byte da normal (osso) não vai para a geometria
    sem = ds2cena.ler_flver(flv)["malhas"][0]  # peça de mapa: sem ossos, como sempre
    assert sem["vertices"][1] == pytest.approx((1.0, 0.0, 0.0))


def test_modelo_do_binder_pega_o_flv_do_modelo_e_as_texturas():
    dds = bytearray(128 + 8)
    dds[:4] = b"DDS "
    struct.pack_into("<2I", dds, 12, 4, 4)
    dds[84:88] = b"DXT1"
    nome_tex = b"c1020_body_d.dds\0"
    tpf = bytearray(0x10 + 0x14)
    tpf[:4] = b"TPF\0"
    struct.pack_into("<i", tpf, 0x08, 1)
    struct.pack_into("<2I", tpf, 0x10, len(tpf) + len(nome_tex), len(dds))
    struct.pack_into("<I", tpf, 0x10 + 0x0C, len(tpf))
    tpf = bytes(tpf) + nome_tex + bytes(dds)
    flv = build_flver([tri_malha()])
    arquivos = {"/model/chr/c1020.bnd": build_bnd4({"c1020_x.flv": b"lixo", "c1020.flv": flv}),
                "/model/chr/c1020.texbnd": build_bnd4({"c1020.tpf": tpf})}
    modelo, tex, aviso = ds2cena.modelo_do_binder(arquivos.get, "/model/chr/c1020.bnd", "/model/chr/c1020.texbnd", "c1020")
    assert aviso is None and len(modelo["malhas"]) == 1 and list(tex) == ["c1020_body_d"]
    assert ds2cena.modelo_do_binder(arquivos.get, "/model/obj/o99.bnd") == (None, {}, "sem arquivo no jogo")


def test_pacotes_procura_em_todos_gamedata_primeiro(tmp_path, monkeypatch):
    for n in ("LqChr", "HqChr", "GameData"):
        (tmp_path / f"{n}Ebl.bhd").write_bytes(b"x")
    abertos = []

    class Falso:
        def __init__(self, _dir, nome):
            abertos.append(nome)
            self.nome = nome

        def tem(self, caminho):
            return self.nome == "HqChr" and caminho == "/model/chr/c1020.bnd"

        def ler(self, caminho):
            return b"BND4"

    monkeypatch.setattr(ds2cena.ds2arquivos, "Arquivo", Falso)
    pac = ds2cena.Pacotes(tmp_path)
    assert pac.nomes == ["GameData", "HqChr", "LqChr"]
    assert pac.ler("/model/chr/c1020.bnd") == b"BND4" and abertos == ["GameData", "HqChr"]
    assert pac.ler("/model/chr/c9999.bnd") is None and abertos == ["GameData", "HqChr", "LqChr"]


@pytest.mark.skipif(not (GAME / "GameDataEbl.bhd").exists(), reason="DS2 SotFS não instalado")
def test_extrair_cena_lost_bastille_objetos_e_inimigos(tmp_path):
    cena = ds2cena.extrair_cena(GAME, "m10_16_00_00", tmp_path)
    assert sum(1 for i in cena["instancias"] if i.get("obj")) >= 20, cena["avisos"]
    assert "c3180" in cena["personagens"], cena["avisos"]  # o Pursuer perto do McDuff
    assert 2.0 < cena["personagens"]["c3180"]["altura"] < 6.0


def test_flver_rigido_com_varias_malhas_mantem_os_materiais():
    """Bug do baú: a malha rígida por vértice não pode estragar o material da malha seguinte."""
    ossos = [{"t": (0, 0, 0)}, {"t": (0, 1, 0)}]
    rigida = {**tri_malha(mtd="Tampa.mtd"), "ossos_malha": [0, 1],
              "vertices": [((0.0, 0.0, 0.0), [127, 254, 127, 1], (0, 0)), ((1.0, 0.0, 0.0), [127, 254, 127, 1], (0, 0)),
                           ((1.0, 0.0, 1.0), [127, 254, 127, 0], (0, 0))]}
    flv = build_flver([rigida, tri_malha(mtd="Caixa.mtd"), tri_malha(mtd="Caixa.mtd")], ossos=ossos)
    malhas = ds2cena.ler_flver(flv, ossos=True)["malhas"]
    assert [m["mtd"] for m in malhas] == ["Tampa.mtd", "Caixa.mtd", "Caixa.mtd"]
    assert malhas[0]["vertices"][0] == pytest.approx((0, 1, 0))


def test_motivo_sem_malha():
    assert ds2cena.motivo_sem_malha({"malhas": [{"tipo": "opaco", "mtd": "a"}]}) is None
    assert "NoLit" in ds2cena.motivo_sem_malha({"malhas": [{"tipo": "ignorar", "mtd": "NoLit.mtd"}]})
    assert "índice" in ds2cena.motivo_sem_malha({"malhas": [], "puladas": ["índice fora dos vértices (9 ≥ 3)"]})
