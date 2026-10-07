#!/usr/bin/env python3
"""Leitor do save de Dark Souls II: Scholar of the First Sin (PC) para o buildsmith."""
import argparse
import json
import os
import re
import struct
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
GAME_DIR = ROOT / "games" / "ds2"
KEY = bytes.fromhex("599F9B699640A55236EE2D70835EC744")

STAT_NAMES = ["VGR", "END", "VIT", "ATN", "STR", "DEX", "INT", "FTH", "ADP"]
EMPTY = (0, 0xFFFFFFFF)
EQUIP_CATEGORIES = {"MeleeWeapons", "RangedWeapons", "Shields", "SpellTools", "Armor", "Rings"}

OFF_STATS = 0x24
OFF_LEVEL = 0x3C  # nível, almas em mãos e soul memory em sequência (3x uint32)
OFF_HANDS = 0x190
HAND_SLOTS = ["L1", "R1", "L2", "R2", "L3", "R3"]
OFF_ARMOR = 0x1A8
ARMOR_SLOTS = ["cabeca", "peito", "maos", "pernas"]
OFF_RINGS = 0x1D0
OFF_SPELLS = 0x208
SPELL_SLOTS = 14
OFF_NAME = 0x3C4
NAME_CHARS = 32
OFF_INVENTORY = 0x1E30
OFF_KEY_ITEMS = 0x10E00
END_KEY_ITEMS = 0x11000
RECORD = 16
OFF_SHOP = 0x830  # histórico de compras: pares (u32 linha da ShopLineupParam, u32 quantidade) até um zero
SHOP_MAX = 256

# Flags globais no bloco de mundo do slot (USER_DATA0(10+slot)): flag N no byte
# FLAG_BASE_OFFSET + (N - FLAG_BASE_ID) // 8, bit mais alto primeiro. Validado em 10 backups reais.
FLAG_BASE_ID = 100944
FLAG_BASE_OFFSET = 0x26DAA
FLAG_MIN, FLAG_MAX = 100000, 110000
LEARNED_DEFAULT = Path.home() / ".buildsmith" / "flags" / "ds2.json"
GAME_DIRS = [
    Path(r"C:\Program Files (x86)\Steam\steamapps\common\Dark Souls II Scholar of the First Sin\Game"),
    Path(r"C:\Program Files\Steam\steamapps\common\Dark Souls II Scholar of the First Sin\Game"),
]


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


def bnd4_entries(data: bytes) -> dict[str, bytes]:
    """Arquivos de um contêiner BND4 sem decifrar (nomes UTF-16 ou ASCII conforme o cabeçalho)."""
    if data[:4] != b"BND4":
        raise SaveError("o arquivo não é um contêiner BND4 (formato inesperado)")
    count = struct.unpack_from("<i", data, 0x0C)[0]
    entry_size = struct.unpack_from("<q", data, 0x20)[0]
    unicode = data[0x30] != 0
    entries = {}
    for i in range(count):
        head = 0x40 + i * entry_size
        size = struct.unpack_from("<q", data, head + 0x08)[0]
        offset, name_off = struct.unpack_from("<II", data, head + 0x10)
        name = _utf16z(data, name_off, 256) if unicode else data[name_off : data.index(b"\0", name_off)].decode("latin-1")
        entries[name] = data[offset : offset + size]
    return entries


def read_bnd4(data: bytes) -> dict[str, bytes]:
    return {name: _decrypt(blob) for name, blob in bnd4_entries(data).items()}


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


def load_item_names(ids_dir: Path = GAME_DIR / "ids") -> dict[int, tuple[str, str]]:
    names = {}
    for file in sorted(Path(ids_dir).glob("*.txt")):
        for line in file.read_text(encoding="utf-8", errors="replace").splitlines():
            match = re.match(r"\s*(\d+)\s+(.+)", line)
            if match:
                names[int(match.group(1))] = (file.stem, match.group(2).strip())
    return names


def item_name(names, item_id: int) -> str:
    return names[item_id][1] if item_id in names else f"desconhecido #{item_id}"


def is_occupied(slot: bytes) -> bool:
    if len(slot) < OFF_LEVEL + 12:
        return False
    level = struct.unpack_from("<I", slot, OFF_LEVEL)[0]
    stats = struct.unpack_from("<9H", slot, OFF_STATS)
    return 1 <= level <= 838 and all(1 <= s <= 99 for s in stats)


def _ids(slot: bytes, off: int, count: int) -> list[int]:
    return [struct.unpack_from("<I", slot, off + 4 * i)[0] for i in range(count)]


def parse_slot(slot: bytes, names) -> dict:
    if not is_occupied(slot):
        raise SaveError("slot vazio ou com layout inesperado")
    unknown = set()

    def named(item_id):
        if item_id not in names:
            unknown.add(item_id)
        return {"id": item_id, "name": item_name(names, item_id)}

    def item(item_id, quantity, upgrade):
        category = names[item_id][0] if item_id in names else "?"
        return {**named(item_id), "category": category, "quantity": quantity, "upgrade": upgrade}

    level, souls, soul_memory = struct.unpack_from("<3I", slot, OFF_LEVEL)
    inventory = []
    for off in range(OFF_INVENTORY, OFF_KEY_ITEMS, RECORD):
        item_id, _, quantity, extra = struct.unpack_from("<4I", slot, off)
        if item_id in EMPTY or not 1_000_000 <= item_id < 100_000_000:
            continue
        if item_id in names and names[item_id][0] in EQUIP_CATEGORIES:
            inventory.append(item(item_id, 1, extra & 0xFF))
        else:
            inventory.append(item(item_id, quantity, None))
    for off in range(OFF_KEY_ITEMS, min(END_KEY_ITEMS, len(slot) - RECORD + 1), RECORD):
        _, item_id, _, quantity = struct.unpack_from("<4I", slot, off)
        if item_id in names and names[item_id][0] == "KeyItems":
            inventory.append(item(item_id, quantity, None))
    return {
        "name": _utf16z(slot, OFF_NAME, NAME_CHARS),
        "level": level,
        "souls": souls,
        "soul_memory": soul_memory,
        "stats": dict(zip(STAT_NAMES, struct.unpack_from("<9H", slot, OFF_STATS))),
        "equipped": {
            "hands": {k: named(i) for k, i in zip(HAND_SLOTS, _ids(slot, OFF_HANDS, 6)) if i not in EMPTY},
            "armor": {k: named(i) for k, i in zip(ARMOR_SLOTS, _ids(slot, OFF_ARMOR, 4)) if i not in EMPTY},
            "rings": [named(i) for i in _ids(slot, OFF_RINGS, 4) if i not in EMPTY],
            "spells": [named(i) for i in _ids(slot, OFF_SPELLS, SPELL_SLOTS) if i not in EMPTY],
        },
        "inventory": inventory,
        "unknown_ids": sorted(unknown),
    }


def world_flag(world: bytes, flag: int) -> bool:
    k = flag - FLAG_BASE_ID
    return bool((world[FLAG_BASE_OFFSET + k // 8] >> (7 - k % 8)) & 1)


def world_flags(world: bytes) -> list[int]:
    return [flag for flag in range(FLAG_MIN, FLAG_MAX) if world_flag(world, flag)]


def purchases(slot: bytes) -> list[tuple[int, int]]:
    out = []
    for i in range(SHOP_MAX):
        row, qty = struct.unpack_from("<II", slot, OFF_SHOP + 8 * i)
        if row == 0:
            break
        out.append((row, qty))
    return out


def _game_json(name: str) -> dict:
    return json.loads((GAME_DIR / name).read_text(encoding="utf-8"))


def _shop_items(regulation) -> dict[int, int]:
    import ds2regulation

    params = ds2regulation.load_params(regulation)
    rows = ds2regulation.param_rows(params["ShopLineupParam"], ds2regulation.LAYOUTS["ShopLineupParam"])
    return {row_id: row["item_id"] for row_id, row in rows.items()}


def progress(slot: bytes, world: bytes, names, shop_items: dict | None, learned: list[dict]) -> dict:
    on = set(world_flags(world))
    lojas = _game_json("lojas.json")["lojas"]
    compras = []
    for row, qty in purchases(slot):
        item_id = shop_items.get(row) if shop_items else None
        compras.append({"linha": row, "loja": lojas.get(str(row // 10000)), "item_id": item_id,
                        "item": item_name(names, item_id) if item_id else None, "qtd": qty})
    return {
        "chefes": [{**boss, "derrotado": boss["flag"] in on} for boss in _game_json("bosses.json")["chefes"]],
        "compras": compras,
        "flags": sorted(on),
        "eventos": [{"nome": e["nome"], "flags": e["flags"], "feito": all(f in on for f in e["flags"])} for e in learned],
    }


def load_learned(path=None) -> list[dict]:
    path = Path(path) if path else LEARNED_DEFAULT
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8")).get("eventos", [])


def game_dirs(game_dir=None) -> list[Path]:
    if game_dir:
        return [Path(game_dir)]
    extra = [Path(os.environ["BUILDSMITH_DS2_GAME"])] if os.environ.get("BUILDSMITH_DS2_GAME") else []
    return extra + GAME_DIRS


def seamless_extension(game_dir=None) -> str | None:
    """Extensão de save configurada no Seamless Co-op (save_file_extension), se o mod estiver instalado."""
    for folder in game_dirs(game_dir):
        ini = folder / "SeamlessCoop" / "ds2sc_settings.ini"
        if ini.exists():
            match = re.search(r"^\s*save_file_extension\s*=\s*([A-Za-z0-9]+)", ini.read_text(encoding="utf-8", errors="replace"), re.M)
            if match:
                return match.group(1)
    return None


def find_save(appdata: str | None = None, game_dir=None) -> Path:
    base = Path(appdata or os.environ.get("APPDATA", "")) / "DarkSoulsII"
    ext = seamless_extension(game_dir)
    active = list(base.glob(f"*/DS2SOFS*.{ext}")) if ext else []
    files = active or list(base.glob("*/DS2SOFS*.sl2")) + list(base.glob("*/DS2SOFS*.co2"))
    if not files:
        raise SaveError(f"nenhum save do DS2 encontrado em {base}")
    return max(files, key=lambda p: p.stat().st_mtime)


def _read_entries(path) -> dict[str, bytes]:
    for attempt in (1, 2):
        try:
            return read_bnd4(Path(path).read_bytes())
        except (SaveError, struct.error, ValueError):
            if attempt == 2:
                raise
            time.sleep(1)


def _occupied(entries) -> list[tuple[int, bytes]]:
    found = []
    for number in range(1, 11):
        slot = entries.get(f"USER_DATA{number:03d}")
        if slot and is_occupied(slot):
            found.append((number, slot))
    return found


def list_slots(path) -> list[dict]:
    return [
        {"slot": n, "name": _utf16z(s, OFF_NAME, NAME_CHARS), "level": struct.unpack_from("<I", s, OFF_LEVEL)[0]}
        for n, s in _occupied(_read_entries(path))
    ]


def snapshot(path, slot: int | None = None, names=None, regulation=None, learned=None) -> dict:
    """regulation: None = procura o do jogo instalado; False = não usa; caminho = usa esse arquivo."""
    names = names if names is not None else load_item_names()
    entries = _read_entries(path)
    occupied = dict(_occupied(entries))
    if not occupied:
        raise SaveError("nenhum personagem encontrado no save")
    if slot is None:
        if len(occupied) > 1:
            raise SaveError(f"mais de um personagem no save; use --slot (opções: {sorted(occupied)})")
        slot = next(iter(occupied))
    if slot not in occupied:
        raise SaveError(f"slot {slot} vazio (opções: {sorted(occupied)})")
    world_name = f"USER_DATA{10 + slot:03d}"
    if world_name not in entries:
        raise SaveError(f"o save não tem o bloco de mundo {world_name} do slot {slot}")
    avisos, shop_items = [], None
    if regulation is not False:
        try:
            shop_items = _shop_items(regulation)
        except (SaveError, OSError, KeyError) as err:
            avisos.append(f"sem nomes das compras: {err}")
    stat = Path(path).stat()
    return {
        "game": "ds2",
        "save_file": str(path),
        "save_mtime": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(stat.st_mtime)),
        "slot": slot,
        **parse_slot(occupied[slot], names),
        "progresso": progress(occupied[slot], entries[world_name], names, shop_items, load_learned(learned)),
        "avisos": avisos,
    }


def main(argv=None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="ds2save")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sl = sub.add_parser("slots", help="lista os personagens do save")
    sl.add_argument("--save")
    sn = sub.add_parser("snapshot", help="ficha completa do personagem em JSON")
    sn.add_argument("--save")
    sn.add_argument("--slot", type=int)
    fd = sub.add_parser("flags-diff", help="flags globais que ligaram/desligaram entre dois snapshots")
    fd.add_argument("--antes", required=True)
    fd.add_argument("--depois", required=True)
    lv = sub.add_parser("levels", help="custo de cada nível entre --from e --to")
    lv.add_argument("--from", dest="frm", type=int, required=True)
    lv.add_argument("--to", type=int, required=True)
    args = parser.parse_args(argv)
    try:
        if args.cmd == "levels":
            out = levels_cost(args.frm, args.to)
        elif args.cmd == "flags-diff":
            before, after = (set(json.loads(Path(p).read_text(encoding="utf-8"))["progresso"]["flags"])
                             for p in (args.antes, args.depois))
            out = {"ligou": sorted(after - before), "desligou": sorted(before - after)}
        else:
            path = Path(args.save) if args.save else find_save()
            out = list_slots(path) if args.cmd == "slots" else snapshot(path, args.slot)
    except SaveError as err:
        print(json.dumps({"error": str(err)}, ensure_ascii=False))
        return 1
    except ImportError:
        print(json.dumps({"error": "falta a biblioteca pycryptodome: rode 'pip install pycryptodome'"}, ensure_ascii=False))
        return 1
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
