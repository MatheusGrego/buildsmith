#!/usr/bin/env python3
"""Dano de arma no DS2 SotFS calculado com as tabelas de regras do próprio jogo.

AR físico (validado contra o menu do jogo: Uchigatana +5 = 218, Cleric's Parma = 54, punho = 49):
  base(L) = dano + (dano_max − dano) × L / nivel_max
  bônus   = escala_FOR(L) × bônus_FOR(FOR) + escala_DES(L) × bônus_DES(DES)
  AR      = floor((base + bônus) × mult_fisico / 100)
Catalisadores (cajado, chama) usam outra fórmula e não são calculados aqui.
"""
import argparse
import json
import math
import struct
import sys

import ds2regulation
from ds2save import SaveError, load_item_names


class Calc:
    def __init__(self, params: dict[str, bytes]):
        rows = ds2regulation.param_rows
        layouts = ds2regulation.LAYOUTS
        self.weapons = rows(params["WeaponParam"], layouts["WeaponParam"])
        self.reinforce = rows(params["WeaponReinforceParam"], layouts["WeaponReinforceParam"])
        self.stat_bonus = rows(params["PhysicalStatsPerLevelStatValuesParam"], layouts["PhysicalStatsPerLevelStatValuesParam"])
        self._affect_raw = params["WeaponStatsAffectParam"]
        self._affect_index = {
            row_id: offset for row_id, offset, _ in
            (struct.unpack_from("<QQQ", self._affect_raw, 0x40 + 24 * i)
             for i in range(struct.unpack_from("<H", self._affect_raw, 0x0A)[0]))
        }

    def _scaling(self, affect_id: int, level: int, kind: int) -> float:
        offset = self._affect_index[affect_id] + ds2regulation.scaling_offset(level, kind)
        return struct.unpack_from("<f", self._affect_raw, offset)[0]

    def physical_ar(self, item_id: int, level: int, stats: dict) -> int:
        if item_id not in self.weapons:
            raise SaveError(f"arma {item_id} não está na WeaponParam")
        row = self.reinforce[self.weapons[item_id]["reinforce_id"]]
        if not 0 <= level <= row["nivel_max"]:
            raise SaveError(f"nível +{level} fora do limite da arma (+{row['nivel_max']})")
        base = row["dano_fisico"] + (row["dano_fisico_max"] - row["dano_fisico"]) * level / max(row["nivel_max"], 1)
        strength = self.stat_bonus[max(1, min(99, stats["STR"]))]["bonus_str"]
        dexterity = self.stat_bonus[max(1, min(99, stats["DEX"]))]["bonus_dex"]
        bonus = (self._scaling(row["stats_affect_id"], level, 0) * strength
                 + self._scaling(row["stats_affect_id"], level, 1) * dexterity)
        return math.floor((base + bonus) * row["mult_fisico"] / 100)


def load(path=None) -> Calc:
    return Calc(ds2regulation.load_params(path))


def _item_id(value: str) -> tuple[int, str]:
    if value.isdigit():
        return int(value), value
    for item_id, (_, name) in load_item_names().items():
        if name.lower() == value.lower():
            return item_id, name
    raise SaveError(f"arma '{value}' não encontrada nas listas de itens")


def main(argv=None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="ds2calc")
    sub = parser.add_subparsers(dest="cmd", required=True)
    ar = sub.add_parser("ar", help="AR físico de uma arma com os atributos dados")
    ar.add_argument("--arma", required=True, help="nome (como nas listas de itens) ou id")
    ar.add_argument("--nivel", type=int, default=0)
    ar.add_argument("--str", type=int, required=True)
    ar.add_argument("--dex", type=int, required=True)
    ar.add_argument("--jogo", help="pasta Game do DS2 (padrão: Steam)")
    args = parser.parse_args(argv)
    try:
        item_id, name = _item_id(args.arma)
        calc = load(ds2regulation.find_regulation(args.jogo))
        value = calc.physical_ar(item_id, args.nivel, {"STR": args.str, "DEX": args.dex})
    except SaveError as err:
        print(json.dumps({"error": str(err)}, ensure_ascii=False))
        return 1
    print(json.dumps({"arma": name, "item_id": item_id, "nivel": args.nivel, "str": args.str, "dex": args.dex,
                      "ar_fisico": value}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
