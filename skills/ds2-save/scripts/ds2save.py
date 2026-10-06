#!/usr/bin/env python3
"""Leitor do save de Dark Souls II: Scholar of the First Sin (PC) para o buildsmith."""
import argparse
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
GAME_DIR = ROOT / "games" / "ds2"
KEY = bytes.fromhex("599F9B699640A55236EE2D70835EC744")


class SaveError(Exception):
    pass


def _utf16z(data: bytes, off: int, max_chars: int) -> str:
    chars = []
    for i in range(max_chars):
        pos = off + 2 * i
        if pos + 2 > len(data):
            break
        code = struct.unpack_from("<H", data, pos)[0]
        if code == 0:
            break
        chars.append(chr(code))
    return "".join(chars)


def _decrypt(blob: bytes) -> bytes:
    from Crypto.Cipher import AES

    iv, body = blob[16:32], blob[32:]
    body = body[: len(body) // 16 * 16]
    return AES.new(KEY, AES.MODE_CBC, iv).decrypt(body)


def read_bnd4(data: bytes) -> dict[str, bytes]:
    if data[:4] != b"BND4":
        raise SaveError("o arquivo não é um save BND4 (formato inesperado)")
    count = struct.unpack_from("<i", data, 0x0C)[0]
    entry_size = struct.unpack_from("<q", data, 0x20)[0]
    entries = {}
    for i in range(count):
        head = 0x40 + i * entry_size
        size = struct.unpack_from("<q", data, head + 0x08)[0]
        offset = struct.unpack_from("<i", data, head + 0x10)[0]
        name = _utf16z(data, struct.unpack_from("<i", data, head + 0x14)[0], 64)
        entries[name] = _decrypt(data[offset : offset + size])
    return entries


def level_costs() -> dict[int, int]:
    raw = json.loads((GAME_DIR / "level_costs.json").read_text(encoding="utf-8"))
    return {int(level): cost for level, cost in raw["costs"].items()}


def levels_cost(frm: int, to: int) -> dict:
    if to <= frm:
        raise SaveError("--to precisa ser maior que --from")
    costs = level_costs()
    missing = [lvl for lvl in range(frm + 1, to + 1) if lvl not in costs]
    if missing:
        raise SaveError(f"sem custo para os níveis {missing[0]}..{missing[-1]} (tabela vai até {max(costs)})")
    steps = [{"level": lvl, "cost": costs[lvl]} for lvl in range(frm + 1, to + 1)]
    return {"from": frm, "to": to, "steps": steps, "total": sum(s["cost"] for s in steps)}


def main(argv=None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="ds2save")
    sub = parser.add_subparsers(dest="cmd", required=True)
    lv = sub.add_parser("levels", help="custo de cada nível entre --from e --to")
    lv.add_argument("--from", dest="frm", type=int, required=True)
    lv.add_argument("--to", type=int, required=True)
    args = parser.parse_args(argv)
    try:
        out = levels_cost(args.frm, args.to)
    except SaveError as err:
        print(json.dumps({"error": str(err)}, ensure_ascii=False))
        return 1
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
