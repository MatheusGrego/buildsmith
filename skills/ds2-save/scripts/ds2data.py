#!/usr/bin/env python3
"""Dados do jogo para o plano: quem vende cada item, trocas de alma de chefe, custo de upgrade e acesso às áreas.

Tudo sai das tabelas de regras instaladas (enc_regulation.bnd.dcx) e dos arquivos de games/ds2/.
"""
import argparse
import json
import struct
import sys
from pathlib import Path

import ds2regulation
from ds2save import GAME_DIR, SaveError, item_name, load_item_names

INFINITO = 255  # quantidade de loja que o jogo usa para estoque ilimitado


def _game_json(name: str) -> dict:
    return json.loads((GAME_DIR / name).read_text(encoding="utf-8"))


def _row_index(raw: bytes) -> dict[int, int]:
    count = struct.unpack_from("<H", raw, 0x0A)[0]
    return {row_id: offset for row_id, offset, _ in (struct.unpack_from("<QQQ", raw, 0x40 + 24 * i) for i in range(count))}


class Data:
    def __init__(self, params: dict[str, bytes]):
        rows, layouts = ds2regulation.param_rows, ds2regulation.LAYOUTS
        self.shop = rows(params["ShopLineupParam"], layouts["ShopLineupParam"])
        self.items = rows(params["ItemParam"], layouts["ItemParam"])
        self.weapons = rows(params["WeaponParam"], layouts["WeaponParam"])
        self.reinforce = rows(params["WeaponReinforceParam"], layouts["WeaponReinforceCost"])
        self._cost_raw = params["ReinforceCostParam"]
        self._cost_index = _row_index(self._cost_raw)
        self.lojas = _game_json("lojas.json")["lojas"]

    def _npc(self, row_id: int) -> str | None:
        return self.lojas.get(str(row_id // 10000))

    def _price(self, item_id: int, rate: float) -> int:
        return round(self.items.get(item_id, {}).get("base_price", 0) * rate)

    def shops_for(self, item_id: int) -> list[dict]:
        """Lojas que vendem o item. estoque None = ilimitado."""
        return [{"linha": row_id, "loja": self._npc(row_id),
                 "estoque": None if row["quantidade"] >= INFINITO else row["quantidade"],
                 "preco": self._price(item_id, row["price_rate"])}
                for row_id, row in sorted(self.shop.items()) if row["item_id"] == item_id and row["material_id"] == 0]

    def trades(self, item_id: int | None = None, soul_id: int | None = None) -> list[dict]:
        """Trocas que pedem um material (alma de chefe) além das almas."""
        return [{"linha": row_id, "npc": self._npc(row_id), "item_id": row["item_id"], "alma_id": row["material_id"],
                 "preco": self._price(row["item_id"], row["price_rate"])}
                for row_id, row in sorted(self.shop.items())
                if row["material_id"] and (item_id is None or row["item_id"] == item_id)
                and (soul_id is None or row["material_id"] == soul_id)]

    def upgrade_cost(self, item_id: int, de: int, ate: int) -> dict:
        if item_id not in self.weapons:
            raise SaveError(f"arma {item_id} não está na WeaponParam")
        if not 0 <= de < ate <= 10:
            raise SaveError("faixa de upgrade inválida: use 0 ≤ --de < --ate ≤ 10")
        cost_id = self.reinforce[self.weapons[item_id]["reinforce_id"]]["reinforce_cost_id"]
        base = self._cost_index[cost_id]
        levels, materials = [], {}
        for level in range(de + 1, ate + 1):
            souls = struct.unpack_from("<i", self._cost_raw, base + 4 * (level - 1))[0]
            material = struct.unpack_from("<i", self._cost_raw, base + 40 + 4 * (level - 1))[0]
            amount = struct.unpack_from("<H", self._cost_raw, base + 80 + 2 * (level - 1))[0]
            levels.append({"nivel": level, "almas": souls, "material_id": material, "qtd": amount})
            materials[material] = materials.get(material, 0) + amount
        return {"niveis": levels, "almas_total": sum(n["almas"] for n in levels), "materiais": materials}


def load(path=None) -> Data:
    return Data(ds2regulation.load_params(path))


def _norm(area: str) -> str:
    return area.lower().replace("the ", "").replace("-", " ").strip()


def area_status(snapshot: dict) -> dict:
    """Acesso de cada área da rota principal a partir dos chefes derrotados."""
    route = _game_json("rota.json")
    order = route["rota"]
    index = {_norm(area): i for i, area in enumerate(order)}
    done = [index[_norm(b["area"])] for b in snapshot["progresso"]["chefes"]
            if b.get("derrotado") and b.get("area") and _norm(b["area"]) in index]
    furthest = max(done, default=0)

    def acesso(i: int) -> str:
        return "agora" if i <= furthest + 1 else "em_breve" if i <= furthest + 4 else "tarde"

    areas = [{"area": hub, "indice": None, "acesso": "agora"} for hub in route["hubs"] if _norm(hub) not in index]
    areas += [{"area": area, "indice": i, "acesso": "agora" if area in route["hubs"] else acesso(i)} for i, area in enumerate(order)]
    return {"mais_avancada": order[furthest], "areas": areas}


def _resolve(names, value: str) -> int:
    if value.isdigit():
        return int(value)
    for item_id, (_, name) in names.items():
        if name.lower() == value.lower():
            return item_id
    raise SaveError(f"item '{value}' não encontrado nas listas de itens")


def main(argv=None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="ds2data")
    sub = parser.add_subparsers(dest="cmd", required=True)
    buy = sub.add_parser("onde-comprar", help="lojas que vendem o item, com preço e estoque")
    buy.add_argument("--item", required=True)
    trade = sub.add_parser("trocas", help="trocas de alma de chefe por item")
    trade.add_argument("--item")
    trade.add_argument("--alma")
    up = sub.add_parser("custo-upgrade", help="materiais e almas para subir uma arma de --de até --ate")
    up.add_argument("--arma", required=True)
    up.add_argument("--de", type=int, required=True)
    up.add_argument("--ate", type=int, required=True)
    acc = sub.add_parser("acesso", help="acesso das áreas (agora / em breve / tarde) a partir de um snapshot")
    acc.add_argument("--snapshot", required=True)
    for p in (buy, trade, up):
        p.add_argument("--jogo", help="pasta Game do DS2 (padrão: Steam)")
    args = parser.parse_args(argv)
    try:
        if args.cmd == "acesso":
            out = area_status(json.loads(Path(args.snapshot).read_text(encoding="utf-8")))
        else:
            names = load_item_names()
            data = load(ds2regulation.find_regulation(args.jogo))
            if args.cmd == "onde-comprar":
                item_id = _resolve(names, args.item)
                out = {"item": item_name(names, item_id), "item_id": item_id, "lojas": data.shops_for(item_id)}
            elif args.cmd == "trocas":
                if not (args.item or args.alma):
                    raise SaveError("use --item ou --alma")
                found = data.trades(item_id=_resolve(names, args.item) if args.item else None,
                                    soul_id=_resolve(names, args.alma) if args.alma else None)
                out = {"trocas": [{**t, "item": item_name(names, t["item_id"]), "alma": item_name(names, t["alma_id"])} for t in found]}
            else:
                item_id = _resolve(names, args.arma)
                cost = data.upgrade_cost(item_id, args.de, args.ate)
                out = {"arma": item_name(names, item_id), "de": args.de, "ate": args.ate, "almas_total": cost["almas_total"],
                       "materiais": [{"item": item_name(names, m), "item_id": m, "qtd": q} for m, q in cost["materiais"].items()],
                       "niveis": [{**n, "material": item_name(names, n["material_id"])} for n in cost["niveis"]]}
    except SaveError as err:
        print(json.dumps({"error": str(err)}, ensure_ascii=False))
        return 1
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
