#!/usr/bin/env python3
"""Extrator de cena 3D do DS2 SotFS (modelos FLVER2, texturas DDS e instâncias MSB)."""
import os
import struct
from pathlib import Path

import ds2arquivos

CENA_VERSAO = 1


class CenaError(Exception):
    pass


def _wstr(data: bytes, off: int) -> str:
    end = off
    while end + 2 <= len(data) and data[end:end + 2] != b"\0\0":
        end += 2
    return data[off:end].decode("utf-16-le", errors="replace")


def _cstr(data: bytes, off: int, unicode: bool = True) -> str:
    if unicode:
        return _wstr(data, off)
    try:
        end = data.index(b"\0", off)
        return data[off:end].decode("latin-1", errors="replace")
    except ValueError:
        return ""


def ler_bhf4(bhd: bytes, bdt: bytes, filtro_ext: str = None) -> dict[str, bytes]:
    """Lê arquivos de um contêiner BHF4/BDF4 descompactando DCX onde couber."""
    if bhd[:4] != b"BHF4":
        raise CenaError("cabeçalho BHF4 inválido")
    count = struct.unpack_from("<i", bhd, 0x0C)[0]
    esz = struct.unpack_from("<q", bhd, 0x20)[0]
    unicode = bhd[0x30] != 0
    out = {}
    for i in range(count):
        h = 0x40 + i * esz
        size = struct.unpack_from("<q", bhd, h + 0x08)[0]
        off = struct.unpack_from("<I", bhd, h + 0x18)[0]
        name_off = struct.unpack_from("<I", bhd, h + esz - 4)[0]
        nome = _cstr(bhd, name_off, unicode)
        short = nome.split("\\")[-1]
        nome_sem_dcx = short[:-4] if short.endswith(".dcx") else short
        if filtro_ext and not nome_sem_dcx.endswith(filtro_ext):
            continue
        raw = bdt[off:off + size]
        out[nome_sem_dcx] = ds2arquivos.dcx(raw)
    return out


def ler_flver(data: bytes) -> dict:
    """Decodifica modelo FLVER2 do DS2 com malhas, materiais e geometria."""
    if data[:6] != b"FLVER\0":
        raise CenaError("formato FLVER2 não reconhecido")
    is_little = data[6:8] == b"L\0"
    if not is_little:
        raise CenaError("FLVER big-endian não suportado")

    version, data_off, data_len, n_dummy, n_mat, n_bone, n_mesh, n_vb = struct.unpack_from("<8i", data, 0x08)
    bb_min = struct.unpack_from("<3f", data, 0x28)
    bb_max = struct.unpack_from("<3f", data, 0x34)
    idx_size, unicode_flv = data[0x48], data[0x49] != 0
    n_fs, n_lay, n_tex = struct.unpack_from("<3i", data, 0x50)

    # Materiais
    off = 0x80 + n_dummy * 0x40
    mats = []
    for i in range(n_mat):
        name_o, mtd_o, tcount, tidx = struct.unpack_from("<4i", data, off + i * 0x20)
        mats.append({
            "nome": _cstr(data, name_o, unicode_flv),
            "mtd": _cstr(data, mtd_o, unicode_flv),
            "tcount": tcount,
            "tidx": tidx,
        })
    off += n_mat * 0x20 + n_bone * 0x80

    # Malhas
    meshes = []
    for i in range(n_mesh):
        o = off + i * 0x30
        mat = struct.unpack_from("<i", data, o + 4)[0]
        fs_count, fs_idx_off, vb_count, vb_idx_off = struct.unpack_from("<4i", data, o + 0x20)
        fs_indices = list(struct.unpack_from(f"<{fs_count}i", data, fs_idx_off))
        vb_indices = list(struct.unpack_from(f"<{vb_count}i", data, vb_idx_off))
        meshes.append({"mat": mat, "fs": fs_indices, "vb": vb_indices})
    off += n_mesh * 0x30

    # Facesets
    fsets = []
    for i in range(n_fs):
        o = off + i * 0x20
        flags, strip, cull = struct.unpack_from("<I??", data, o)
        icount, ioff, ilen, z, isize = struct.unpack_from("<5i", data, o + 8)
        fsets.append({
            "flags": flags, "strip": strip, "cull": cull,
            "count": icount, "off": data_off + ioff, "size": isize or idx_size,
        })
    off += n_fs * 0x20

    # Vertex Buffers
    vbs = []
    for i in range(n_vb):
        bidx, lay, vsize, vcount, a1, a2, blen, boff = struct.unpack_from("<8i", data, off + i * 0x20)
        vbs.append({"lay": lay, "vsize": vsize, "vcount": vcount, "off": data_off + boff})
    off += n_vb * 0x20

    # Layouts
    lays = []
    for i in range(n_lay):
        mcount, a1, a2, moff = struct.unpack_from("<4i", data, off + i * 0x10)
        members = []
        for k in range(mcount):
            unk, m_off, m_type, m_sem, m_idx = struct.unpack_from("<5i", data, moff + k * 0x14)
            members.append({"off": m_off, "type": m_type, "semantic": m_sem, "idx": m_idx})
        lays.append(members)
    off += n_lay * 0x10

    # Texturas
    texs = []
    for i in range(n_tex):
        p_o, t_o = struct.unpack_from("<2i", data, off + i * 0x20)
        texs.append((_cstr(data, p_o, unicode_flv), _cstr(data, t_o, unicode_flv)))

    # Constrói submalhas prontas
    malhas_saida = []
    for m in meshes:
        if not m["fs"] or not m["vb"]:
            continue
        fs = fsets[m["fs"][0]]
        vb = vbs[m["vb"][0]]
        lay = lays[vb["lay"]]

        # Índices
        fmt = "<H" if fs["size"] in (16, 2) else "<I"
        stride_idx = 2 if fmt == "<H" else 4
        indices = [struct.unpack_from(fmt, data, fs["off"] + k * stride_idx)[0] for k in range(fs["count"])]

        # Membros do layout
        pos_m = next((item for item in lay if item["semantic"] == 0), None)
        norm_m = next((item for item in lay if item["semantic"] == 3), None)
        uv_m = next((item for item in lay if item["semantic"] == 5 and item["idx"] == 0), None)

        vertices = []
        normais = []
        uvs = []
        vsize = vb["vsize"]
        v_base = vb["off"]

        for vi in range(vb["vcount"]):
            vo = v_base + vi * vsize
            if pos_m:
                vertices.append(struct.unpack_from("<3f", data, vo + pos_m["off"]))
            if norm_m:
                raw_n = data[vo + norm_m["off"]:vo + norm_m["off"] + 3]
                if len(raw_n) == 3:
                    # int8 snorm ou uint8 unorm normalizado
                    normais.append(tuple((b - 127) / 127.0 for b in raw_n))
            if uv_m:
                if uv_m["type"] == 21:  # float16
                    uvs.append(struct.unpack_from("<2e", data, vo + uv_m["off"]))
                else:  # float32
                    uvs.append(struct.unpack_from("<2f", data, vo + uv_m["off"]))

        # Acha textura difusa associada ao material da malha
        mat_info = mats[m["mat"]] if 0 <= m["mat"] < len(mats) else None
        tex_difusa = None
        if mat_info and mat_info["tcount"] > 0:
            t_slice = texs[mat_info["tidx"]:mat_info["tidx"] + mat_info["tcount"]]
            for p, tipo in t_slice:
                if tipo in ("g_DiffuseTexture", "g_AlbedoTexture") or not tex_difusa:
                    nome_arq = p.replace("\\", "/").split("/")[-1]
                    stem = nome_arq.rsplit(".", 1)[0]
                    if tipo in ("g_DiffuseTexture", "g_AlbedoTexture"):
                        tex_difusa = stem
                        break
                    tex_difusa = stem

        malhas_saida.append({
            "material_idx": m["mat"],
            "indices": indices,
            "vertices": vertices,
            "normais": normais,
            "uvs": uvs,
            "textura_difusa": tex_difusa,
        })

    return {
        "version": hex(version),
        "bb": (bb_min, bb_max),
        "materiais": mats,
        "malhas": malhas_saida,
    }
