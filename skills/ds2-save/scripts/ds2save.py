#!/usr/bin/env python3
"""Leitor do save de Dark Souls II: Scholar of the First Sin (PC) para o buildsmith."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
GAME_DIR = ROOT / "games" / "ds2"


class SaveError(Exception):
    pass


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
