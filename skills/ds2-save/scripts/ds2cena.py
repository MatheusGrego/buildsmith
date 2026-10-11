#!/usr/bin/env python3
"""Cena 3D de uma área do DS2 SotFS (peças de mapa FLVER2, texturas DDS, instâncias do MSB e o chão andável) para
a vista isométrica da página.

Formatos (conferidos no Huntsman's Copse, m10_23_00_00, e em Majula, m10_04_00_00):
- BHF4/BDF4 (.mapbhd/.mapbdt e .tpfbhd/.tpfbdt): entradas de 0x24 bytes; tamanho em +0x08, offset no .bdt em +0x18,
  nome pelo offset nos últimos 4 bytes. Conteúdo em DCX.
- FLVER2 "L" versão 0x20010. Membro de layout = (unk, offset, tipo, semântica, índice). Posição Float3 (0x02);
  normal Byte4B (0x11) = (b - 127) / 127; UV tipo 0x15 = int16 / 2048 (1024 antes da versão 0x2000F): as UVs de
  barris e estátuas fecham em 0..2047. Facesets com flag 0x01000000/0x02000000 são LOD e ficam de fora.
- Material: o .mtd diz o tipo. SkyDome e NoLit (céu, cartões pretos de neblina/escuridão nas entradas de caverna,
  feixes de luz) e difusa "dummy*" (caixas de oclusão, como a m1800 do Drangleic Castle) ficam de fora;
  _Alp_1bit = recorte (folhagem, grade); _Alp/[decal] = decal translúcido; Water = água.
- MSB (PARTS_PARAM_ST, tipo 0 = peça de mapa): modelo em +0x0C, posição +0x10, rotação em graus +0x1C, escala +0x28.
  Matriz = T · Ry · Rz · Rx · S (gira em X, depois Z, depois Y; o sinal padrão bateu com o navmesh).
- O chão andável (navmesh, as mesmas malhas do mapa 2D) entra no geo.bin: a página usa para o corte de interior.
- O geo.bin fica no cache em gzip (geo.bin.gz, ~3× menor); o servidor manda com Content-Encoding: gzip.
"""
import gzip
import json
import math
import os
import shutil
import struct
import threading
import time
from array import array
from pathlib import Path

import ds2arquivos
import ds2mapa

CENA_VERSAO = 2  # 2: UV int16, normais por tipo, LOD0, céu/NoLit fora, matriz, chão andável, cache atômico
TEX_MAX = 512  # lado máximo das texturas (descarta os mipmaps maiores)
FORA_M = 40.0  # peças além desta margem do chão andável (céu, montanhas de fundo) ficam de fora
LOD_FLAGS = 0x01000000 | 0x02000000
GEO = "geo.bin.gz"
TIPOS_MATERIAL = ("opaco", "recorte", "decal", "agua")


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


def classe_material(mtd: str) -> str:
    """Tipo de desenho pelo nome do .mtd: opaco, recorte, decal, agua ou ignorar."""
    n = mtd.replace("\\", "/").rsplit("/", 1)[-1].lower()
    if "skydome" in n or n.startswith("nolit") or n.startswith("sky"):
        return "ignorar"
    if n.startswith("water") or "_water" in n:
        return "agua"
    if "_alp_1bit" in n:
        return "recorte"
    if "_alp" in n or "[decal]" in n:
        return "decal"
    return "opaco"


def _stem(caminho: str) -> str:
    return caminho.replace("\\", "/").rsplit("/", 1)[-1].rsplit(".", 1)[0].lower()


def textura_difusa(texturas: list[tuple[str, str]]) -> str | None:
    """A difusa principal do material: g_DiffuseTexture (DS2/DS3), g_Diffuse (DS1) ou, sem tipo, a 1ª que termina em _d."""
    for caminho, tipo in texturas:
        if tipo in ("g_DiffuseTexture", "g_Diffuse", "g_AlbedoTexture") and caminho:
            return _stem(caminho)
    for caminho, _tipo in texturas:
        if caminho and _stem(caminho).endswith("_d"):
            return _stem(caminho)
    return None


def triangulos_de_strip(indices: list[int], restart: bool = True) -> list[int]:
    """Triangle strip -> lista de triângulos (alternando a ordem; 0xFFFF reinicia; degenerados saem)."""
    out = []
    flip = False
    for i in range(len(indices) - 2):
        a, b, c = indices[i], indices[i + 1], indices[i + 2]
        if restart and 0xFFFF in (a, b, c):
            flip = False
            continue
        if a != b and b != c and a != c:
            out += (c, b, a) if flip else (a, b, c)
        flip = not flip
    return out


# tipo de membro do layout -> (formato struct, decodificação)
def _membro(tipo: int, semantica: int, uv_fator: float):
    """(formato struct, função que leva a tupla lida ao valor) para posição, normal e UV; None se não usado."""
    if semantica == 0:  # posição
        if tipo == 0x02:
            return "3f", lambda v: v
        if tipo == 0x03:
            return "4f", lambda v: v[:3]
    elif semantica == 3:  # normal
        if tipo in (0x10, 0x11, 0x13, 0x2F):
            return "4B", lambda v: ((v[0] - 127) / 127.0, (v[1] - 127) / 127.0, (v[2] - 127) / 127.0)
        if tipo == 0x02:
            return "3f", lambda v: v
        if tipo == 0x03:
            return "4f", lambda v: v[:3]
        if tipo == 0x1A:
            return "4h", lambda v: (v[0] / 32767.0, v[1] / 32767.0, v[2] / 32767.0)
        if tipo == 0x2E:
            return "4H", lambda v: ((v[0] - 32767) / 32767.0, (v[1] - 32767) / 32767.0, (v[2] - 32767) / 32767.0)
    elif semantica == 5:  # UV
        if tipo == 0x01:
            return "2f", lambda v: v
        if tipo == 0x03:
            return "4f", lambda v: v[:2]
        if tipo in (0x15, 0x12):
            return "2h", lambda v: (v[0] / uv_fator, v[1] / uv_fator)
        if tipo == 0x16:
            return "4h", lambda v: (v[0] / uv_fator, v[1] / uv_fator)
    return None


def _ler_vertices(data: bytes, vb: dict, layout: list[dict], uv_fator: float, exigir_pos: bool = True) -> dict:
    """Posições, normais e UV (a de menor índice) de um vertex buffer, lidas de uma vez por struct."""
    escolhidos = {}
    for m in layout:
        sem = m["semantic"]
        if sem == 5 and "uv" in escolhidos and escolhidos["uv"][0]["idx"] <= m["idx"]:
            continue
        if sem in (0, 3) and ({0: "pos", 3: "nrm"}[sem]) in escolhidos:
            continue
        dec = _membro(m["type"], sem, uv_fator)
        if dec:
            escolhidos[{0: "pos", 3: "nrm", 5: "uv"}[sem]] = (m, dec)
    if exigir_pos and "pos" not in escolhidos:
        raise CenaError("vertex buffer sem posição legível")
    if not escolhidos:
        return {}
    campos = sorted(escolhidos.items(), key=lambda kv: kv[1][0]["off"])
    fmt, cursor, ordem = "<", 0, []
    for nome, (m, (f, conv)) in campos:
        if m["off"] < cursor:
            raise CenaError("membros de layout sobrepostos")
        fmt += "x" * (m["off"] - cursor) + f
        cursor = m["off"] + struct.calcsize("<" + f)
        ordem.append((nome, int(f[0]), conv))
    if cursor > vb["vsize"]:
        raise CenaError("layout maior que o vértice")
    fmt += "x" * (vb["vsize"] - cursor)
    st = struct.Struct(fmt)
    bloco = data[vb["off"]:vb["off"] + vb["vsize"] * vb["vcount"]]
    if len(bloco) != vb["vsize"] * vb["vcount"]:
        raise CenaError("vertex buffer fora do arquivo")
    out = {nome: [] for nome, _, _ in ordem}
    for valores in st.iter_unpack(bloco):
        k = 0
        for nome, n, conv in ordem:
            out[nome].append(conv(valores[k:k + n]))
            k += n
    return out


def ler_flver(data: bytes) -> dict:
    """Modelo FLVER2 do DS2: malhas (LOD0) com posições, normais, UV, índices em lista, difusa e tipo de material."""
    if data[:6] != b"FLVER\0":
        raise CenaError("formato FLVER2 não reconhecido")
    if data[6:8] != b"L\0":
        raise CenaError("FLVER big-endian não suportado")

    version, data_off, _data_len, n_dummy, n_mat, n_bone, n_mesh, n_vb = struct.unpack_from("<8i", data, 0x08)
    bb_min = struct.unpack_from("<3f", data, 0x28)
    bb_max = struct.unpack_from("<3f", data, 0x34)
    idx_size, unicode_flv = data[0x48], data[0x49] != 0
    n_fs, n_lay, n_tex = struct.unpack_from("<3i", data, 0x50)
    uv_fator = 2048.0 if version >= 0x2000F else 1024.0

    off = 0x80 + n_dummy * 0x40
    mats = []
    for i in range(n_mat):
        name_o, mtd_o, tcount, tidx = struct.unpack_from("<4i", data, off + i * 0x20)
        mats.append({"nome": _cstr(data, name_o, unicode_flv), "mtd": _cstr(data, mtd_o, unicode_flv),
                     "tcount": tcount, "tidx": tidx})
    off += n_mat * 0x20 + n_bone * 0x80

    meshes = []
    for i in range(n_mesh):
        o = off + i * 0x30
        mat = struct.unpack_from("<i", data, o + 4)[0]
        fs_count, fs_idx_off, vb_count, vb_idx_off = struct.unpack_from("<4i", data, o + 0x20)
        meshes.append({"mat": mat, "fs": list(struct.unpack_from(f"<{fs_count}i", data, fs_idx_off)),
                       "vb": list(struct.unpack_from(f"<{vb_count}i", data, vb_idx_off))})
    off += n_mesh * 0x30

    fsets = []
    for i in range(n_fs):
        o = off + i * 0x20
        flags, strip, _cull = struct.unpack_from("<I??", data, o)
        icount, ioff, _ilen, _z, isize = struct.unpack_from("<5i", data, o + 8)
        fsets.append({"flags": flags, "strip": strip, "count": icount, "off": data_off + ioff, "size": isize or idx_size})
    off += n_fs * 0x20

    vbs = []
    for i in range(n_vb):
        _bidx, lay, vsize, vcount, _a1, _a2, _blen, boff = struct.unpack_from("<8i", data, off + i * 0x20)
        vbs.append({"lay": lay, "vsize": vsize, "vcount": vcount, "off": data_off + boff})
    off += n_vb * 0x20

    lays = []
    for i in range(n_lay):
        mcount, _a1, _a2, moff = struct.unpack_from("<4i", data, off + i * 0x10)
        members = []
        for k in range(mcount):
            _unk, m_off, m_type, m_sem, m_idx = struct.unpack_from("<5i", data, moff + k * 0x14)
            members.append({"off": m_off, "type": m_type, "semantic": m_sem, "idx": m_idx})
        lays.append(members)
    off += n_lay * 0x10

    texs = []
    for i in range(n_tex):
        p_o, t_o = struct.unpack_from("<2i", data, off + i * 0x20)
        texs.append((_cstr(data, p_o, unicode_flv), _cstr(data, t_o, unicode_flv)))

    malhas_saida = []
    for m in meshes:
        if not m["fs"] or not m["vb"]:
            continue
        mat_info = mats[m["mat"]] if 0 <= m["mat"] < len(mats) else {"mtd": "", "tcount": 0, "tidx": 0}
        tipo = classe_material(mat_info["mtd"])
        cand = [fsets[k] for k in m["fs"] if 0 <= k < len(fsets)]
        fs = next((f for f in cand if not f["flags"] & LOD_FLAGS), cand[0] if cand else None)
        if fs is None:
            continue
        largura = 2 if fs["size"] in (16, 2) else 4
        indices = list(struct.unpack_from(f"<{fs['count']}{'H' if largura == 2 else 'I'}", data, fs["off"]))
        if fs["strip"]:
            indices = triangulos_de_strip(indices, restart=largura == 2)
        else:
            indices = indices[:len(indices) - len(indices) % 3]

        # posição/normal/UV podem vir em buffers diferentes da mesma malha
        attrs = {}
        for k in m["vb"]:
            vb = vbs[k]
            for nome, valores in _ler_vertices(data, vb, lays[vb["lay"]], uv_fator, exigir_pos=False).items():
                attrs.setdefault(nome, valores)
        if "pos" not in attrs or not indices or max(indices) >= len(attrs["pos"]):
            continue

        tex_difusa = None
        if mat_info["tcount"] > 0:
            tex_difusa = textura_difusa(texs[mat_info["tidx"]:mat_info["tidx"] + mat_info["tcount"]])
        if tex_difusa and tex_difusa.startswith("dummy"):
            tipo = "ignorar"  # volume auxiliar (oclusão/sombra): caixa lisa gigante que o jogo nunca desenha

        malhas_saida.append({
            "material_idx": m["mat"],
            "mtd": mat_info["mtd"].replace("\\", "/").rsplit("/", 1)[-1],
            "tipo": tipo,
            "indices": indices,
            "vertices": attrs["pos"],
            "normais": attrs.get("nrm", []),
            "uvs": attrs.get("uv", []),
            "textura_difusa": tex_difusa,
        })

    return {"version": hex(version), "bb": (bb_min, bb_max), "materiais": mats, "malhas": malhas_saida}


def limitar_dds(dds: bytes, max_dim: int = TEX_MAX) -> bytes:
    """Limita resolução do DDS para max_dim descartando mipmaps maiores (sem decodificar pixels)."""
    if len(dds) < 128 or dds[:4] != b"DDS ":
        return dds
    h, w = struct.unpack_from("<2I", dds, 12)
    mips = struct.unpack_from("<I", dds, 28)[0]
    fourcc = dds[84:88].decode("ascii", errors="replace")
    if fourcc not in ("DXT1", "DXT3", "DXT5") or (w <= max_dim and h <= max_dim):
        return dds
    block_bytes = 8 if fourcc == "DXT1" else 16
    cw, ch = w, h
    k = 0
    skipped = 0
    while (cw > max_dim or ch > max_dim) and (mips - k) > 1:
        bw = max(1, (cw + 3) // 4)
        bh = max(1, (ch + 3) // 4)
        skipped += bw * bh * block_bytes
        cw = max(1, cw >> 1)
        ch = max(1, ch >> 1)
        k += 1
    if k == 0 or 128 + skipped > len(dds):
        return dds
    head = bytearray(dds[:128])
    struct.pack_into("<2I", head, 12, ch, cw)
    struct.pack_into("<I", head, 28, max(1, mips - k))
    lin_size = max(1, (cw + 3) // 4) * max(1, (ch + 3) // 4) * block_bytes
    struct.pack_into("<I", head, 20, lin_size)
    return bytes(head) + dds[128 + skipped:]


def extrair_dds_tpf(tpf_bytes: bytes, max_dim: int = TEX_MAX) -> dict[str, bytes]:
    """Extrai arquivos DDS contidos em um contêiner TPF (nome em minúsculas, sem extensão)."""
    if len(tpf_bytes) < 0x20 or tpf_bytes[:4] != b"TPF\0":
        raise CenaError("contêiner TPF inválido")
    n_tex = struct.unpack_from("<i", tpf_bytes, 0x08)[0]
    out = {}
    for i in range(n_tex):
        o = 0x10 + i * 0x14
        tex_off, tex_sz = struct.unpack_from("<2I", tpf_bytes, o)
        name_off = struct.unpack_from("<I", tpf_bytes, o + 0x0C)[0]
        end = tpf_bytes.find(b"\0", name_off)
        nome = tpf_bytes[name_off:end].decode("latin-1", errors="replace") if end != -1 else f"tex_{i}"
        stem = nome.rsplit(".", 1)[0].lower()
        out[stem] = limitar_dds(tpf_bytes[tex_off:tex_off + tex_sz], max_dim=max_dim)
    return out


def _alinhar(buf: bytearray, n: int = 4) -> None:
    if len(buf) % n:
        buf += bytes(n - len(buf) % n)


def empacotar_geometria(modelos_flver: dict[str, dict]) -> tuple[bytes, dict]:
    """geo.bin com um bloco por submalha: posições float32×3, normais int8×4 (÷127), UV float32×2, índices u16/u32.

    Cada bloco começa alinhado em 4 bytes; o catálogo guarda offset e contagem de cada um."""
    geo = bytearray()
    catalogo = {"modelos": {}}
    for nome_modelo, modelo in modelos_flver.items():
        malhas_info = []
        for m in modelo.get("malhas", []):
            verts, indices = m.get("vertices", []), m.get("indices", [])
            if not verts or not indices or m.get("tipo") == "ignorar":
                continue
            n = len(verts)
            norms = m.get("normais") or []
            uvs = m.get("uvs") or []
            _alinhar(geo)
            pos_off = len(geo)
            geo += array("f", [c for v in verts for c in v]).tobytes()
            nrm_off = len(geo)
            nrm = array("b")
            for i in range(n):
                nx, ny, nz = norms[i] if i < len(norms) else (0.0, 1.0, 0.0)
                nrm.extend((max(-127, min(127, round(nx * 127))), max(-127, min(127, round(ny * 127))),
                            max(-127, min(127, round(nz * 127))), 0))
            geo += nrm.tobytes()
            uv_off = len(geo)
            geo += array("f", [c for i in range(n) for c in (uvs[i] if i < len(uvs) else (0.0, 0.0))]).tobytes()
            idx_size = 2 if n <= 65535 else 4
            _alinhar(geo)
            i_off = len(geo)
            geo += array("H" if idx_size == 2 else "I", indices).tobytes()
            malhas_info.append({
                "tipo": m.get("tipo", "opaco"),
                "tex": m.get("textura_difusa"),
                "v_count": n,
                "pos": pos_off,
                "nrm": nrm_off,
                "uv": uv_off,
                "i_off": i_off,
                "i_count": len(indices),
                "idx_size": idx_size,
            })
        if malhas_info:
            catalogo["modelos"][nome_modelo] = {"bb": modelo.get("bb"), "malhas": malhas_info}
    return bytes(geo), catalogo


def matriz_instancia(pos, rot_graus, esc) -> list[float]:
    """Matriz 4×4 (coluna a coluna, como a Matrix4.fromArray do three.js) = T · Ry · Rz · Rx · S, em coordenadas do jogo."""
    rx, ry, rz = (math.radians(a) for a in rot_graus)
    cx, sx, cy, sy, cz, sz = math.cos(rx), math.sin(rx), math.cos(ry), math.sin(ry), math.cos(rz), math.sin(rz)
    rot_x = ((1, 0, 0), (0, cx, -sx), (0, sx, cx))
    rot_y = ((cy, 0, sy), (0, 1, 0), (-sy, 0, cy))
    rot_z = ((cz, -sz, 0), (sz, cz, 0), (0, 0, 1))

    def mul(a, b):
        return tuple(tuple(sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)) for i in range(3))

    r = mul(mul(rot_y, rot_z), rot_x)
    m = [0.0] * 16
    for col in range(3):
        for lin in range(3):
            m[col * 4 + lin] = round(r[lin][col] * esc[col], 6)
    m[12], m[13], m[14], m[15] = float(pos[0]), float(pos[1]), float(pos[2]), 1.0
    return m


def aplicar_matriz(m: list[float], p) -> tuple[float, float, float]:
    x, y, z = p
    return (m[0] * x + m[4] * y + m[8] * z + m[12], m[1] * x + m[5] * y + m[9] * z + m[13],
            m[2] * x + m[6] * y + m[10] * z + m[14])


def caixa_mundo(m: list[float], bb) -> tuple[list[float], list[float]]:
    """Caixa alinhada aos eixos da caixa do modelo depois da matriz da instância."""
    (x0, y0, z0), (x1, y1, z1) = bb
    pts = [aplicar_matriz(m, (x, y, z)) for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)]
    return [min(p[k] for p in pts) for k in range(3)], [max(p[k] for p in pts) for k in range(3)]


def msb_instancias(msb_bytes: bytes) -> tuple[list[dict], set[str]]:
    """Peças de mapa do MSB: modelo, posição, rotação (graus), escala e a matriz."""
    listas = ds2mapa._listas_msb(msb_bytes)
    modelos_msb = []
    for e in listas.get("MODEL_PARAM_ST", []):
        modelos_msb.append(_wstr(msb_bytes, e + struct.unpack_from("<q", msb_bytes, e)[0]))

    instancias = []
    modelos_usados = set()
    for e in listas.get("PARTS_PARAM_ST", []):
        if msb_bytes[e + 8] != 0:  # 0 = peça de mapa
            continue
        nome = _wstr(msb_bytes, e + struct.unpack_from("<q", msb_bytes, e)[0])
        m_idx = struct.unpack_from("<h", msb_bytes, e + 0x0C)[0]
        pos = struct.unpack_from("<3f", msb_bytes, e + 0x10)
        rot = struct.unpack_from("<3f", msb_bytes, e + 0x1C)
        esc = struct.unpack_from("<3f", msb_bytes, e + 0x28)
        mod_nome = modelos_msb[m_idx] if 0 <= m_idx < len(modelos_msb) else "?"
        modelos_usados.add(mod_nome.lower())
        instancias.append({
            "nome": nome,
            "modelo": mod_nome.lower(),
            "pos": [round(c, 3) for c in pos],
            "rot": [round(c, 3) for c in rot],
            "esc": [round(c, 4) for c in esc],
            "matriz": matriz_instancia(pos, rot, esc),
        })
    return instancias, modelos_usados


def chao_area(arq, area: str, msb_bytes: bytes) -> tuple[list[float], list[int]]:
    """Navmesh da área (as mesmas malhas do mapa 2D), em coordenadas do jogo: vértices achatados e triângulos."""
    caminho = f"/map/{area}/{area}.ngp"
    if not arq.tem(caminho):
        return [], []
    base = ds2mapa.origem(ds2mapa.partes_msb(msb_bytes))
    verts, tris = [], []
    for malha in ds2mapa.malhas_nvg2(arq.ler(caminho), base):
        b = len(verts) // 3
        verts += [round(c, 3) for v in malha["v"] for c in v]
        tris += [b + i for f in malha["f"] for i in f]
    return verts, tris


def _limites(verts: list[float]):
    if not verts:
        return None
    xs, ys, zs = verts[0::3], verts[1::3], verts[2::3]
    return [min(xs), min(ys), min(zs)], [max(xs), max(ys), max(zs)]


def _dentro(caixa_inst, jogavel, margem: float) -> bool:
    (a0, a1), (j0, j1) = caixa_inst, jogavel
    return (a1[0] >= j0[0] - margem and a0[0] <= j1[0] + margem and a1[2] >= j0[2] - margem and a0[2] <= j1[2] + margem)


_travas: dict[str, threading.Lock] = {}
_travas_lock = threading.Lock()


def _trava(area: str) -> threading.Lock:
    with _travas_lock:
        return _travas.setdefault(area, threading.Lock())


def cena_pronta(area_dir: Path, assinatura: str | None = None) -> dict | None:
    """cena.json do cache se for desta versão (e, com assinatura, do mesmo jogo); None se precisa extrair."""
    try:
        dados = json.loads((Path(area_dir) / "cena.json").read_text("utf-8"))
    except (OSError, ValueError):
        return None
    if dados.get("versao") != CENA_VERSAO or not (Path(area_dir) / GEO).is_file():
        return None
    if assinatura is not None and dados.get("assinatura") != assinatura:
        return None
    return dados


def extrair_cena(game_dir=None, area: str = "m10_04_00_00", cache_dir=None, forcar: bool = False,
                 progresso_callback=None) -> dict:
    """Extrai a cena 3D da área para <cache>/cena/<area>/ (cena.json, geo.bin.gz, tex/*.dds). Uma extração por vez por área."""
    ds2mapa.nome_mapa_id(area)  # valida o nome antes de virar caminho
    game_dir = game_dir or ds2arquivos.game_dir_padrao()
    if game_dir is None:
        raise CenaError("DS2 SotFS não encontrado")
    cache_base = Path(cache_dir) if cache_dir else (Path.home() / ".buildsmith" / "cache" / "ds2")
    area_dir = cache_base / "cena" / area
    assinatura = ds2arquivos.assinatura(game_dir)
    avisa = progresso_callback or (lambda _msg, _p: None)

    with _trava(area):
        if not forcar:
            pronto = cena_pronta(area_dir, assinatura)
            if pronto:
                return pronto
        t0 = time.time()
        avisa("Lendo MSB e chão andável...", 0.05)
        arq = ds2arquivos.Arquivo(game_dir, "GameData")
        msb_bytes = arq.ler(f"/map/{area}/{area}.msb")
        if not arq.tem(f"/model/map/{area}.mapbhd"):
            raise CenaError(f"área {area} sem modelos de mapa")
        instancias, modelos_usados = msb_instancias(msb_bytes)
        chao_v, chao_f = chao_area(arq, area, msb_bytes)

        avisa(f"Lendo {len(modelos_usados)} modelos FLVER...", 0.2)
        flvs_raw = ler_bhf4(arq.ler(f"/model/map/{area}.mapbhd"), arq.ler(f"/model/map/{area}.mapbdt"), ".flv")
        avisos = []
        modelos = {}
        for k, data in flvs_raw.items():
            stem = k.rsplit(".", 1)[0].lower()
            if stem not in modelos_usados:
                continue
            try:
                modelos[stem] = ler_flver(data)
            except (CenaError, struct.error, IndexError, ValueError) as err:
                avisos.append(f"modelo {stem} pulado: {err}")

        # peças fora do chão andável (céu, montanhas de fundo) e modelos só de céu/NoLit ficam de fora
        jogavel = _limites(chao_v)
        mantidas, fora = [], 0
        for inst in instancias:
            mod = modelos.get(inst["modelo"])
            if not mod or not any(m["tipo"] != "ignorar" for m in mod["malhas"]):
                continue
            caixa = caixa_mundo(inst["matriz"], mod["bb"])
            if jogavel and not _dentro(caixa, jogavel, FORA_M):
                fora += 1
                continue
            inst["caixa"] = [round(c, 2) for c in caixa[0] + caixa[1]]
            mantidas.append(inst)
        usados = {i["modelo"] for i in mantidas}
        modelos = {k: v for k, v in modelos.items() if k in usados}
        if fora:
            avisos.append(f"{fora} peças fora da área jogável (fundo/céu) ficaram de fora")

        tex_necessarias = {m["textura_difusa"] for mod in modelos.values() for m in mod["malhas"]
                           if m["textura_difusa"] and m["tipo"] != "ignorar"}
        avisa(f"Extraindo {len(tex_necessarias)} texturas...", 0.55)
        t_area = "t" + area[1:]
        tex_salvas = {}
        if arq.tem(f"/model/map/{t_area}.tpfbhd") and arq.tem(f"/model/map/{t_area}.tpfbdt"):
            tpfs = ler_bhf4(arq.ler(f"/model/map/{t_area}.tpfbhd"), arq.ler(f"/model/map/{t_area}.tpfbdt"), ".tpf")
            for k, data in tpfs.items():
                if k.rsplit(".", 1)[0].lower() not in tex_necessarias:
                    continue
                try:
                    for stem, dds in extrair_dds_tpf(data, TEX_MAX).items():
                        if stem in tex_necessarias and dds[:4] == b"DDS " and dds[84:88] in (b"DXT1", b"DXT3", b"DXT5"):
                            tex_salvas[stem] = dds
                except (CenaError, struct.error) as err:
                    avisos.append(f"textura {k} pulada: {err}")
        faltam = sorted(tex_necessarias - set(tex_salvas))
        if faltam:
            avisos.append(f"{len(faltam)} texturas sem DDS legível (ficam cinza): {', '.join(faltam[:8])}")

        avisa("Empacotando geometria...", 0.8)
        geo, catalogo = empacotar_geometria(modelos)
        geo = bytearray(geo)
        for mod in catalogo["modelos"].values():
            for m in mod["malhas"]:
                if m["tex"] not in tex_salvas:
                    m["tex"] = None
        chao = None
        if chao_f:
            _alinhar(geo)
            v_off = len(geo)
            geo += array("f", chao_v).tobytes()
            i_off = len(geo)
            geo += array("I", chao_f).tobytes()
            chao = {"v_off": v_off, "v_count": len(chao_v) // 3, "i_off": i_off, "i_count": len(chao_f)}

        if jogavel:
            limites = {"min": [round(c, 1) for c in jogavel[0]], "max": [round(c, 1) for c in jogavel[1]]}
        else:
            caixas = [i["caixa"] for i in mantidas] or [[-100, -100, -100, 100, 100, 100]]
            limites = {"min": [min(c[k] for c in caixas) for k in range(3)],
                       "max": [max(c[k + 3] for c in caixas) for k in range(3)]}

        cena = {
            "versao": CENA_VERSAO,
            "assinatura": assinatura,
            "area": area,
            "limites": limites,
            "margem": FORA_M,
            "instancias": [{k: i[k] for k in ("nome", "modelo", "matriz", "caixa")} for i in mantidas],
            "modelos": catalogo["modelos"],
            "texturas": sorted(tex_salvas),
            "chao": chao,
            "avisos": avisos,
        }

        # gravação atômica: pasta temporária completa, depois troca pela definitiva
        tmp = cache_base / "cena" / f".{area}.tmp-{os.getpid()}-{threading.get_ident()}"
        if tmp.exists():
            shutil.rmtree(tmp)
        (tmp / "tex").mkdir(parents=True)
        geo_gz = gzip.compress(bytes(geo), compresslevel=6, mtime=0)
        (tmp / GEO).write_bytes(geo_gz)
        for stem, dds in tex_salvas.items():
            (tmp / "tex" / f"{stem}.dds").write_bytes(dds)
        cena["mb"] = round((len(geo_gz) + sum(len(d) for d in tex_salvas.values())) / 1e6, 1)
        cena["segundos"] = round(time.time() - t0, 1)
        (tmp / "cena.json").write_text(json.dumps(cena, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        if area_dir.exists():
            shutil.rmtree(area_dir)
        os.replace(tmp, area_dir)
        avisa("Concluído", 1.0)
        return cena


def main():
    import argparse
    import sys

    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Extrator de cena 3D do Dark Souls 2")
    subparsers = parser.add_subparsers(dest="comando")
    p_ext = subparsers.add_parser("extrair", help="Extrai cena 3D de uma área")
    p_ext.add_argument("--area", default="m10_04_00_00", help="ID da área (ex: m10_04_00_00)")
    p_ext.add_argument("--game-dir", default=None, help="Caminho do jogo")
    p_ext.add_argument("--cache-dir", default=None, help="Caminho do cache")
    p_ext.add_argument("--forcar", action="store_true", help="Força re-extração mesmo se em cache")
    args = parser.parse_args()
    if args.comando != "extrair":
        parser.print_help()
        return
    cena = extrair_cena(args.game_dir, args.area, args.cache_dir, forcar=args.forcar,
                        progresso_callback=lambda msg, p: print(f"[{int(p * 100):3d}%] {msg}", file=sys.stderr))
    print(json.dumps({"area": cena["area"], "instancias": len(cena["instancias"]), "modelos": len(cena["modelos"]),
                      "texturas": len(cena["texturas"]), "mb": cena.get("mb"), "segundos": cena.get("segundos"),
                      "chao_triangulos": (cena["chao"] or {}).get("i_count", 0) // 3, "avisos": cena["avisos"]},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
