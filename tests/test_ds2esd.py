import struct
from pathlib import Path

import pytest

import ds2esd

GAME = Path(r"C:/Program Files (x86)/Steam/steamapps/common/Dark Souls II Scholar of the First Sin/Game")
BASTILLE_KEY, FLAG = 50800000, 116000041


def const(v: int) -> bytes:
    """Inteiro numa expressão do EzState: -64..63 num byte (v + 64), senão 0x82 + int32."""
    return bytes([v + 64]) if -64 <= v < 64 else b"\x82" + struct.pack("<i", v)


def build_esd(grupos: dict[int, list[dict]]) -> bytes:
    """ESD "fsSL" mínimo. grupos: id -> estados; estado: {"cond": [avaliador], "cmds": [(banco, id, [args])]}.
    Offsets dos dados relativos ao início da seção de dados (0x6C), como no jogo."""
    dados = bytearray(0x48)
    pend = []  # (posição do varint, função que devolve o valor) preenchidos no fim

    def var(buf_pos, valor):
        struct.pack_into("<q", dados, buf_pos, valor)

    def poe(b: bytes) -> int:
        while len(dados) % 8:
            dados.append(0)
        o = len(dados)
        dados.extend(b)
        return o

    tabela = poe(bytes(0x20 * len(grupos)))
    for k, (gid, estados) in enumerate(grupos.items()):
        estados_off = poe(bytes(0x48 * len(estados)))
        struct.pack_into("<4q", dados, tabela + k * 0x20, gid, estados_off, len(estados), estados_off)
        for s, est in enumerate(estados):
            conds = []
            for avaliador in est.get("cond", []):
                ev = poe(avaliador + b"\xa1")
                conds.append(poe(struct.pack("<7q", -1, 0, 0, 0, 0, ev, len(avaliador) + 1)))
            cond_lista = poe(struct.pack(f"<{len(conds)}q", *conds)) if conds else 0
            cmds = b""
            for banco, cid, args in est.get("cmds", []):
                tab_args = b"".join(struct.pack("<2q", poe(a + b"\xa1"), len(a) + 1) for a in args)
                cmds += struct.pack("<ii2q", banco, cid, poe(tab_args) if args else 0, len(args))
            cmd_off = poe(cmds) if cmds else 0
            struct.pack_into("<9q", dados, estados_off + s * 0x48, s, cond_lista, len(conds), cmd_off,
                             len(est.get("cmds", [])), 0, 0, 0, 0)
    struct.pack_into("<i4ii", dados, 0, 1, 0, 0, 0, 0, 0)
    struct.pack_into("<6q", dados, 0x18, tabela, len(grupos), 0, 0, -1, -1)
    cab = bytearray(0x6C)
    cab[:4] = b"fsSL"
    struct.pack_into("<5i", cab, 4, 1, 2, 2, 0x54, len(dados))
    struct.pack_into("<i", cab, 0x28, len(grupos))
    return bytes(cab + dados)


def porta_com_chave(chave=BASTILLE_KEY, flag=FLAG):
    """O jeito do jogo: o evento chama a máquina comum de "porta com chave" (banco 6, 0x7FFFFFFA) com mensagens,
    a chave e uma flag."""
    return [{"cond": [const(1)]},
            {"cmds": [(1, 130001, []), (6, 0x7FFFFFFA, [const(1005), const(1105), const(chave), const(flag)])]}]


def test_constantes_pula_float_texto_e_operadores():
    expr = const(5) + b"\x80" + struct.pack("<f", 50800000.0) + const(BASTILLE_KEY) + b"\xa5" + "x\x82".encode("utf-16-le") \
        + b"\0\0" + const(-3) + b"\x8c\x84" + const(FLAG) + b"\xa1"
    assert ds2esd.constantes(expr) == [5, BASTILLE_KEY, -3, FLAG]


def test_ler_esd_junta_avaliadores_e_argumentos_por_grupo():
    esd = build_esd({18010: porta_com_chave(), 18011: [{"cond": [const(7) + b"\x8c"]}]})
    grupos = ds2esd.ler_esd(esd)
    assert set(grupos) == {18010, 18011}
    assert [c for e in grupos[18010] for c in ds2esd.constantes(e)] == [1, 1005, 1105, BASTILLE_KEY, FLAG]
    with pytest.raises(ds2esd.EsdError):
        ds2esd.ler_esd(b"XXXX" + bytes(0x100))


def test_chave_de_cada_objeto_pelo_eventparam():
    """eventparam: (evento, ref da parte do MSB, ...). Evento sem chave, com duas chaves ou sem linha não entra."""
    esd = build_esd({18010: porta_com_chave(), 18030: porta_com_chave(50830000),
                     18050: porta_com_chave() + [{"cond": [const(50830000)]}], 18070: [{"cond": [const(3)]}],
                     19000: porta_com_chave()})
    linhas = [(18010, struct.pack("<4i", 18010, 10160432, 0x2000000, 1)), (18030, struct.pack("<4i", 18030, 10160440, 0x2000000, 1)),
              (18050, struct.pack("<4i", 18050, 10160443, 0x2000000, 1)), (18070, struct.pack("<4i", 18070, 10160444, 0x2000000, 1))]
    chaves = {BASTILLE_KEY: "Bastille Key", 50830000: "Brightstone Key"}
    assert ds2esd.chaves_por_objeto(esd, linhas, chaves) == {10160432: BASTILLE_KEY, 10160440: 50830000}


@pytest.mark.skipif(not (GAME / "GameDataEbl.bhd").exists(), reason="DS2 SotFS não instalado")
def test_chaves_das_portas_com_o_jogo():
    """Conferido na wiki: a Bastille Key abre a cela ao lado da do Straid (ref 10160432), a Antiquated Key a porta de
    madeira do primeiro pátio da Lost Bastille (10160400); a Forgotten Key de Majula bate com o nome do modelo."""
    import ds2arquivos
    import ds2mapa
    import ds2save

    arq = ds2arquivos.Arquivo(GAME, "GameData")
    nomes = {i: n for i, (cat, n) in ds2save.load_item_names().items() if cat == "KeyItems"}

    def chaves(area):
        return ds2esd.chaves_por_objeto(arq.ler(f"/ezstate/event_{area}.esd"),
                                        ds2mapa.linhas_param(arq.ler(f"/param/eventparam_{area}.param")), nomes)

    bastille = chaves("m10_16_00_00")
    assert bastille[10160432] == 50800000 and bastille[10160400] == 50840000
    assert sum(1 for k in bastille.values() if k == 50800000) == 7
    assert chaves("m10_04_00_00")[10040420] == 50820000  # Large Stone Door (Forgotten Key)
