#!/usr/bin/env python3
"""Scripts de evento do DS2 SotFS (EzState, /ezstate/event_<área>.esd): qual chave cada evento pede, e a que objeto
do mapa o evento pertence.

Formato "fsSL" (64 bits), pela leitura do SoulsFormats (MIT; só como referência, sem código copiado):
- cabeçalho de 0x6C bytes; tudo depois é relativo ao início dos dados (0x6C). Dados: +0x18 offset da tabela de grupos
  (máquinas de estado) e +0x20 quantos.
- grupo (0x20): id, offset dos estados, quantos estados, offset de novo. Estado (0x48, 9 int64): id, condições
  (offset da lista, quantas), comandos de entrada, de saída e "enquanto" (offset, quantos cada).
- condição (0x38, 7 int64): estado de destino, comandos ao passar (offset, quantos), subcondições (offset da lista,
  quantas), avaliador (offset, tamanho). Comando (0x18): banco (i32), id (i32), argumentos (offset, quantos);
  argumento (0x10): offset e tamanho da expressão.
- expressão: bytecode de pilha. Inteiro de -64 a 63 num byte (valor + 64), 0x80 float32, 0x81 double, 0x82 int32,
  0xA5 texto UTF-16 até 00 00; o resto é operador, chamada de função ou fim (0xA1).

Conferido no jogo (2026-10-11): a porta com chave é um evento que chama a máquina comum (banco 6, 0x7FFFFFFA) com
(mensagem, mensagem, ID da chave, flag); o ID do evento é a linha do eventparam_<área>, cujo +0x04 é o ref da parte do
MSB (o mesmo de mapobjectinstanceparam). Ex.: evento 18010 da Lost Bastille pede a Bastille Key e aponta a Prison Door
10160432, a cela ao lado da do Straid (wiki). Nas 28 áreas, 29 portas ganham chave; as 4 cujo nome do modelo cita a
chave (Forgotten Key, Key to King's Passage) dão a mesma.
"""
import struct
import sys

DADOS = 0x6C


class EsdError(Exception):
    pass


def constantes(expr: bytes) -> list[int]:
    """Inteiros empilhados numa expressão do EzState, na ordem."""
    out, i = [], 0
    while i < len(expr):
        b = expr[i]
        if b < 0x80:
            out.append(b - 64)
            i += 1
        elif b == 0x80:
            i += 5
        elif b == 0x81:
            i += 9
        elif b == 0x82:
            out.append(struct.unpack_from("<i", expr, i + 1)[0])
            i += 5
        elif b == 0xA5:
            j = i + 1
            while j + 1 < len(expr) and expr[j:j + 2] != b"\0\0":
                j += 2
            i = j + 2
        else:
            i += 1
    return out


def ler_esd(data: bytes) -> dict[int, list[bytes]]:
    """Máquina de estado (id) -> todas as expressões dela: avaliadores das condições (com as subcondições) e
    argumentos dos comandos (entrada, saída, enquanto e ao passar)."""
    if data[:4] != b"fsSL" or len(data) < DADOS + 0x48:
        raise EsdError("ESD em formato inesperado (esperado fsSL)")

    def q(rel: int, k: int = 0) -> int:
        return struct.unpack_from("<q", data, DADOS + rel + 8 * k)[0]

    def comandos(off: int, n: int, exprs: list) -> None:
        for c in range(n):
            o = off + c * 0x18
            args_off, args_n = q(o + 8), q(o + 16)
            for a in range(args_n):
                inicio, tam = q(args_off + a * 0x10), q(args_off + a * 0x10, 1)
                exprs.append(data[DADOS + inicio:DADOS + inicio + tam])

    def condicao(off: int, exprs: list, vistas: set) -> None:
        if off in vistas:
            return
        vistas.add(off)
        _destino, cmd_off, cmd_n, sub_off, sub_n, ev_off, ev_n = (q(off, k) for k in range(7))
        exprs.append(data[DADOS + ev_off:DADOS + ev_off + ev_n])
        comandos(cmd_off, cmd_n, exprs)
        for k in range(sub_n):
            condicao(q(sub_off, k), exprs, vistas)

    try:
        tabela, n_grupos = q(0x18), q(0x20)
        out = {}
        for g in range(n_grupos):
            gid, estados, n_estados = q(tabela + g * 0x20), q(tabela + g * 0x20, 1), q(tabela + g * 0x20, 2)
            exprs, vistas = [], set()
            for s in range(n_estados):
                v = [q(estados + s * 0x48, k) for k in range(9)]
                for k in range(v[2]):
                    condicao(q(v[1], k), exprs, vistas)
                for off, n in ((v[3], v[4]), (v[5], v[6]), (v[7], v[8])):
                    comandos(off, n, exprs)
            out[gid] = exprs
        return out
    except struct.error as err:
        raise EsdError(f"ESD cortado ({err})") from err


def chaves_por_objeto(esd: bytes, linhas_eventparam: list[tuple[int, bytes]], chaves: dict[int, str]) -> dict[int, int]:
    """ref da parte do MSB -> ID da chave que o evento dela pede. Só evento com exatamente uma chave e com linha no
    eventparam (o +0x04 da linha é o ref)."""
    alvo = {rid: struct.unpack_from("<i", raw, 4)[0] for rid, raw in linhas_eventparam if len(raw) >= 8}
    out = {}
    for gid, exprs in ler_esd(esd).items():
        if gid not in alvo:
            continue
        achadas = {c for e in exprs for c in constantes(e) if c in chaves}
        if len(achadas) == 1:
            out[alvo[gid]] = achadas.pop()
    return out


def main(argv=None) -> int:
    import argparse
    import json

    import ds2arquivos
    import ds2mapa
    import ds2save

    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Chaves pedidas pelos eventos de uma área do DS2")
    sub = parser.add_subparsers(dest="comando", required=True)
    p = sub.add_parser("chaves", help="objeto do mapa -> chave que o evento dele pede")
    p.add_argument("--area", required=True)
    p.add_argument("--game", default=None)
    args = parser.parse_args(argv)
    area = args.area
    ds2mapa.nome_mapa_id(area)
    arq = ds2arquivos.Arquivo(args.game or ds2arquivos.game_dir_padrao(), "GameData")
    nomes = {i: n for i, (cat, n) in ds2save.load_item_names().items() if cat == "KeyItems"}
    partes = {p["ref"]: p for p in ds2mapa.partes_msb(arq.ler(f"/map/{area}/{area}.msb")) if p["ref"]}
    achadas = chaves_por_objeto(arq.ler(f"/ezstate/event_{area}.esd"),
                                ds2mapa.linhas_param(arq.ler(f"/param/eventparam_{area}.param")), nomes)
    print(json.dumps([{"ref": ref, "parte": partes.get(ref, {}).get("nome"), "modelo": partes.get(ref, {}).get("modelo"),
                       "chave": nomes[k], "chave_id": k} for ref, k in sorted(achadas.items())], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
