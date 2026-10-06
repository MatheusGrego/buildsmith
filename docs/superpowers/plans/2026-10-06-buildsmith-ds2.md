# buildsmith (DS2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Plugin do Claude Code com skills que lê o save do Dark Souls II SotFS e publica um plano de build numa página fixa.

**Architecture:** Um único script Python (`ds2save.py`) lê o save (BND4 + AES-128-CBC), nomeia itens com listas vendorizadas e calcula custos de nível. Quatro skills (`ds2-save`, `wiki-cache`, `build-page`, `build`) orquestram leitura, pesquisa na wiki com cache e publicação da página a partir de um modelo HTML fixo + `plano.json`.

**Tech Stack:** Python 3.12, `pycryptodome`, `pytest`, Claude Code plugin (skills), HTML/CSS/JS puro para a página.

**Spec:** `docs/superpowers/specs/2026-10-06-buildsmith-design.md`

## Global Constraints

- Python 3 com dependência única de runtime: `pycryptodome`. Testes: `pytest`.
- O save original nunca é escrito; o script só lê bytes.
- Dados do jogador ficam em `~/.buildsmith/` (fora do repo).
- Custos de alma vêm sempre de `ds2save.py levels`, nunca de conta feita pelo modelo.
- Layout de save inesperado → erro claro, nunca atributo inventado.
- Cache da wiki vale 30 dias.
- Commits vão direto para `master` com push (pedido do usuário; sem PR).
- Mensagens de commit terminam com `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Estrutura de arquivos

| Arquivo | Responsabilidade |
|---|---|
| `.claude-plugin/plugin.json` | manifesto do plugin |
| `.claude-plugin/marketplace.json` | marketplace local para instalar o plugin |
| `games/ds2/level_costs.json` | custo de cada nível (2–250) — já extraído |
| `games/ds2/ids/*.txt` + `LICENSE-DS2S-META` | listas de IDs (MIT) — já vendorizadas |
| `skills/ds2-save/scripts/ds2save.py` | leitor do save + custos + CLI |
| `skills/ds2-save/SKILL.md` | como usar o leitor |
| `skills/wiki-cache/SKILL.md` | pesquisa na wiki com cache |
| `skills/build-page/template/index.html` | visual fixo da página |
| `skills/build-page/scripts/validate_plano.py` | valida `plano.json` antes de publicar |
| `skills/build-page/example/plano.json` | exemplo de plano (usado em teste) |
| `skills/build-page/SKILL.md` | como montar e publicar a página |
| `skills/build/SKILL.md` | orquestrador `/buildsmith:build ds2` |
| `tests/conftest.py` | gerador de save sintético |
| `tests/test_ds2save.py`, `tests/test_validate_plano.py` | testes |

---

### Task 1: Custos de nível + esqueleto do plugin

**Files:**
- Create: `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `skills/ds2-save/scripts/ds2save.py` (parte de níveis), `tests/conftest.py` (path), `tests/test_ds2save.py`
- Already present: `games/ds2/level_costs.json`, `games/ds2/ids/`
- Modify: `docs/superpowers/specs/2026-10-06-buildsmith-design.md` (IDs vendorizados; teste do save real por invariantes; `equipped` com `hands/armor/rings/spells`)

**Interfaces:**
- Produces: `ds2save.ROOT: Path`, `ds2save.GAME_DIR: Path`, `ds2save.SaveError`, `ds2save.level_costs() -> dict[int, int]`, `ds2save.levels_cost(frm: int, to: int) -> dict` (`{"from","to","steps":[{"level","cost"}],"total"}`), `ds2save.main(argv) -> int`.

- [ ] **Step 1: Manifesto do plugin**

`.claude-plugin/plugin.json`:
```json
{
  "name": "buildsmith",
  "version": "0.1.0",
  "description": "Lê o save do jogo e monta um plano de build numa página fixa. Primeiro jogo: Dark Souls II SotFS.",
  "author": { "name": "Matheus Grego" }
}
```

`.claude-plugin/marketplace.json`:
```json
{
  "name": "buildsmith",
  "owner": { "name": "Matheus Grego" },
  "plugins": [
    { "name": "buildsmith", "source": "./", "description": "Planejador de builds a partir do save do jogo." }
  ]
}
```

- [ ] **Step 2: Teste falhando**

`tests/conftest.py`:
```python
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "ds2-save" / "scripts"))
sys.path.insert(0, str(ROOT / "skills" / "build-page" / "scripts"))
```

`tests/test_ds2save.py`:
```python
import json

import pytest

import ds2save


def test_level_cost_65_to_66_matches_game():
    assert ds2save.levels_cost(65, 66)["total"] == 6657


def test_level_phase_vgr_to_20():
    result = ds2save.levels_cost(65, 76)
    assert result["total"] == 82736
    assert [s["level"] for s in result["steps"]] == list(range(66, 77))


def test_levels_beyond_table_raises():
    with pytest.raises(ds2save.SaveError):
        ds2save.levels_cost(65, 900)


def test_levels_requires_increasing_range():
    with pytest.raises(ds2save.SaveError):
        ds2save.levels_cost(70, 70)


def test_cli_levels_prints_json(capsys):
    assert ds2save.main(["levels", "--from", "65", "--to", "66"]) == 0
    assert json.loads(capsys.readouterr().out)["total"] == 6657
```

- [ ] **Step 3: Rodar e ver falhar**

Run: `python -m pytest tests/test_ds2save.py -q`
Expected: FAIL com `ModuleNotFoundError: No module named 'ds2save'`.

- [ ] **Step 4: Implementação mínima**

`skills/ds2-save/scripts/ds2save.py`:
```python
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
```

- [ ] **Step 5: Rodar e ver passar**

Run: `python -m pytest tests/test_ds2save.py -q`
Expected: `5 passed`.

- [ ] **Step 6: Atualizar o spec** — trocar a seção "Listas de IDs" para "vendorizadas em `games/ds2/ids/` (MIT, com `LICENSE-DS2S-META`)"; no item 2 de Testes, trocar "confere nível 65, VGR 9, INT 26, Uchigatana +5" por "confere invariantes: há personagem, nome não vazio, atributos entre 1 e 99, Uchigatana no inventário"; no JSON do `snapshot`, trocar `"equipped": {"weapons": ...}` por `"equipped": {"hands": {...}, "armor": {...}, "rings": [...], "spells": [...]}`; na tabela de Decisões, trocar "Slot mais recente" por "único slot ocupado; se houver mais de um, pergunta 1 vez e grava no perfil".

- [ ] **Step 7: Commit**
```bash
git add .claude-plugin games skills tests docs
git commit -m "feat: custos de nível do DS2 e esqueleto do plugin"
git push
```

---

### Task 2: Leitura do contêiner BND4 + gerador de save sintético

**Files:**
- Modify: `skills/ds2-save/scripts/ds2save.py`, `tests/conftest.py`, `tests/test_ds2save.py`

**Interfaces:**
- Consumes: `ds2save.SaveError`.
- Produces: `ds2save.KEY: bytes`, `ds2save.read_bnd4(data: bytes) -> dict[str, bytes]` (nome da entrada → bytes decifrados), `ds2save._utf16z(data, off, max_chars) -> str`; fixtures `build_bnd4(entries: dict[str, bytes]) -> bytes`.

- [ ] **Step 1: Teste falhando** — acrescentar em `tests/conftest.py`:
```python
import hashlib
import struct

from Crypto.Cipher import AES

import ds2save


def encrypt_entry(plain: bytes) -> bytes:
    iv = bytes(range(16))
    body = AES.new(ds2save.KEY, AES.MODE_CBC, iv).encrypt(plain + b"\0" * ((-len(plain)) % 16))
    return hashlib.md5(iv + body).digest() + iv + body


def build_bnd4(entries: dict[str, bytes]) -> bytes:
    names = list(entries)
    header = bytearray(0x40)
    header[:4] = b"BND4"
    struct.pack_into("<i", header, 0x0C, len(names))
    struct.pack_into("<q", header, 0x20, 0x20)
    headers = bytearray(0x20 * len(names))
    names_start = 0x40 + len(headers)
    name_blob, name_offsets = bytearray(), []
    for name in names:
        name_offsets.append(names_start + len(name_blob))
        name_blob += name.encode("utf-16le") + b"\0\0"
    data_start = names_start + len(name_blob)
    data_blob = bytearray()
    for i, name in enumerate(names):
        blob = encrypt_entry(entries[name])
        struct.pack_into("<q", headers, i * 0x20 + 0x08, len(blob))
        struct.pack_into("<i", headers, i * 0x20 + 0x10, data_start + len(data_blob))
        struct.pack_into("<i", headers, i * 0x20 + 0x14, name_offsets[i])
        data_blob += blob
    return bytes(header + headers + name_blob + data_blob)
```

Acrescentar em `tests/test_ds2save.py`:
```python
from conftest import build_bnd4


def test_read_bnd4_roundtrip():
    data = build_bnd4({"USER_DATA000": b"resumo", "USER_DATA001": bytes(range(40))})
    entries = ds2save.read_bnd4(data)
    assert entries["USER_DATA000"][:6] == b"resumo"
    assert entries["USER_DATA001"][:40] == bytes(range(40))


def test_read_bnd4_rejects_other_files():
    with pytest.raises(ds2save.SaveError):
        ds2save.read_bnd4(b"PK\x03\x04 isto e um zip")
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_ds2save.py -q`
Expected: FAIL com `AttributeError: module 'ds2save' has no attribute 'KEY'`.

- [ ] **Step 3: Implementação** — em `ds2save.py`, adicionar `import struct` aos imports e, abaixo de `GAME_DIR`:
```python
KEY = bytes.fromhex("599F9B699640A55236EE2D70835EC744")


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
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python -m pytest tests/test_ds2save.py -q`
Expected: `7 passed`.

- [ ] **Step 5: Commit**
```bash
git add skills tests
git commit -m "feat: leitura do contêiner BND4 do save do DS2"
git push
```

---

### Task 3: Ficha do personagem (`slots` e `snapshot`)

**Files:**
- Modify: `skills/ds2-save/scripts/ds2save.py`, `tests/conftest.py`, `tests/test_ds2save.py`

**Interfaces:**
- Consumes: `read_bnd4`, `_utf16z`, `SaveError`, `GAME_DIR`.
- Produces: `load_item_names(ids_dir=GAME_DIR/"ids") -> dict[int, tuple[str, str]]` (id → (categoria, nome)), `item_name(names, item_id) -> str`, `is_occupied(slot: bytes) -> bool`, `parse_slot(slot: bytes, names) -> dict`, `find_save(appdata: str | None = None) -> Path`, `list_slots(path) -> list[dict]`, `snapshot(path, slot: int | None = None, names=None) -> dict`; CLI `slots [--save]`, `snapshot [--save] [--slot]`. Constantes `OFF_*`, `SPELL_SLOTS`, `HAND_SLOTS`, `ARMOR_SLOTS`.

- [ ] **Step 1: Teste falhando** — acrescentar em `tests/conftest.py`:
```python
import pytest


@pytest.fixture(scope="session")
def names():
    return ds2save.load_item_names()


def id_of(names, wanted: str) -> int:
    return next(item_id for item_id, (_, name) in names.items() if name == wanted)


def make_slot(name="Teste", level=65, souls=1234, soul_memory=221118, stats=(9, 6, 5, 30, 10, 18, 26, 6, 8)) -> bytearray:
    slot = bytearray(0x11000)
    struct.pack_into("<9H", slot, ds2save.OFF_STATS, *stats)
    struct.pack_into("<3I", slot, ds2save.OFF_LEVEL, level, souls, soul_memory)
    encoded = name.encode("utf-16le")
    slot[ds2save.OFF_NAME : ds2save.OFF_NAME + len(encoded)] = encoded
    for off, count in ((ds2save.OFF_HANDS, 6), (ds2save.OFF_ARMOR, 4), (ds2save.OFF_RINGS, 4), (ds2save.OFF_SPELLS, ds2save.SPELL_SLOTS)):
        for i in range(count):
            struct.pack_into("<I", slot, off + 4 * i, 0xFFFFFFFF)
    return slot


@pytest.fixture
def save_file(tmp_path, names):
    slot = make_slot(name="Melatonina Vorcaro")
    uchi, staff = id_of(names, "Uchigatana"), id_of(names, "Sorcerer's Staff")
    struct.pack_into("<2I", slot, ds2save.OFF_HANDS, staff, uchi)  # L1, R1
    struct.pack_into("<I", slot, ds2save.OFF_RINGS, id_of(names, "Clear Bluestone Ring"))
    struct.pack_into("<I", slot, ds2save.OFF_SPELLS, id_of(names, "Soul Arrow"))
    struct.pack_into("<IIfI", slot, ds2save.OFF_INVENTORY, uchi, 0, 40.0, 5)
    struct.pack_into("<4I", slot, ds2save.OFF_INVENTORY + 16, id_of(names, "Human Effigy"), 0, 15, 0)
    struct.pack_into("<4I", slot, ds2save.OFF_INVENTORY + 32, 12345678, 0, 1, 0)
    struct.pack_into("<4I", slot, ds2save.OFF_KEY_ITEMS + 16, 0, id_of(names, "Soldier Key"), 0, 1)
    path = tmp_path / "DS2SOFS0000.sl2"
    path.write_bytes(build_bnd4({"USER_DATA000": bytes(0x100), "USER_DATA001": bytes(slot), "USER_DATA002": bytes(0x11000)}))
    return path
```

Acrescentar em `tests/test_ds2save.py`:
```python
import os
import struct
from pathlib import Path

from conftest import id_of, make_slot


def test_item_names_known_and_unknown(names):
    assert ds2save.item_name(names, 31010000) == "Soul Arrow"
    assert ds2save.item_name(names, 99) == "desconhecido #99"


def test_snapshot_reads_character(save_file):
    snap = ds2save.snapshot(save_file)
    assert snap["slot"] == 1
    assert snap["name"] == "Melatonina Vorcaro"
    assert snap["level"] == 65 and snap["souls"] == 1234 and snap["soul_memory"] == 221118
    assert snap["stats"] == {"VGR": 9, "END": 6, "VIT": 5, "ATN": 30, "STR": 10, "DEX": 18, "INT": 26, "FTH": 6, "ADP": 8}
    assert snap["equipped"]["hands"]["R1"]["name"] == "Uchigatana"
    assert snap["equipped"]["hands"]["L1"]["name"] == "Sorcerer's Staff"
    assert [r["name"] for r in snap["equipped"]["rings"]] == ["Clear Bluestone Ring"]
    assert [s["name"] for s in snap["equipped"]["spells"]] == ["Soul Arrow"]


def test_snapshot_inventory(save_file):
    inv = {i["name"]: i for i in ds2save.snapshot(save_file)["inventory"]}
    assert inv["Uchigatana"]["upgrade"] == 5 and inv["Uchigatana"]["quantity"] == 1
    assert inv["Human Effigy"]["quantity"] == 15 and inv["Human Effigy"]["upgrade"] is None
    assert inv["Soldier Key"]["category"] == "KeyItems"
    assert inv["desconhecido #12345678"]["category"] == "?"


def test_snapshot_lists_unknown_ids(save_file):
    assert 12345678 in ds2save.snapshot(save_file)["unknown_ids"]


def test_list_slots_skips_empty(save_file):
    assert ds2save.list_slots(save_file) == [{"slot": 1, "name": "Melatonina Vorcaro", "level": 65}]


def test_multiple_characters_require_slot(tmp_path, names):
    path = tmp_path / "multi.sl2"
    path.write_bytes(build_bnd4({"USER_DATA001": bytes(make_slot(name="A")), "USER_DATA002": bytes(make_slot(name="B", level=10))}))
    with pytest.raises(ds2save.SaveError, match="--slot"):
        ds2save.snapshot(path, names=names)
    assert ds2save.snapshot(path, slot=2, names=names)["name"] == "B"


def test_find_save_picks_newest(tmp_path):
    folder = tmp_path / "DarkSoulsII" / "0110000100000000"
    folder.mkdir(parents=True)
    old, new = folder / "DS2SOFS0000.sl2", folder / "DS2SOFS0000.co2"
    old.write_bytes(b"x")
    new.write_bytes(b"y")
    os.utime(old, (1, 1))
    assert ds2save.find_save(str(tmp_path)) == new


def test_cli_snapshot_prints_json(save_file, capsys):
    assert ds2save.main(["snapshot", "--save", str(save_file)]) == 0
    assert json.loads(capsys.readouterr().out)["name"] == "Melatonina Vorcaro"


def _real_save():
    try:
        return ds2save.find_save()
    except ds2save.SaveError:
        return None


@pytest.mark.skipif(_real_save() is None, reason="sem save real do DS2 nesta máquina")
def test_real_save_invariants():
    path = _real_save()
    slots = ds2save.list_slots(path)
    assert slots, "nenhum personagem encontrado no save real"
    snap = ds2save.snapshot(path, slot=slots[0]["slot"])
    assert snap["name"]
    assert all(1 <= v <= 99 for v in snap["stats"].values())
    assert any(i["name"] == "Uchigatana" for i in snap["inventory"])
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_ds2save.py -q`
Expected: FAIL com `AttributeError: module 'ds2save' has no attribute 'load_item_names'`.

- [ ] **Step 3: Implementação** — em `ds2save.py`, adicionar `import os`, `import re`, `import time` aos imports; abaixo de `KEY`:
```python
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
```

E antes de `main`:
```python
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


def find_save(appdata: str | None = None) -> Path:
    base = Path(appdata or os.environ.get("APPDATA", "")) / "DarkSoulsII"
    files = list(base.glob("*/DS2SOFS*.sl2")) + list(base.glob("*/DS2SOFS*.co2"))
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


def snapshot(path, slot: int | None = None, names=None) -> dict:
    names = names if names is not None else load_item_names()
    occupied = dict(_occupied(_read_entries(path)))
    if not occupied:
        raise SaveError("nenhum personagem encontrado no save")
    if slot is None:
        if len(occupied) > 1:
            raise SaveError(f"mais de um personagem no save; use --slot (opções: {sorted(occupied)})")
        slot = next(iter(occupied))
    if slot not in occupied:
        raise SaveError(f"slot {slot} vazio (opções: {sorted(occupied)})")
    stat = Path(path).stat()
    return {
        "game": "ds2",
        "save_file": str(path),
        "save_mtime": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(stat.st_mtime)),
        "slot": slot,
        **parse_slot(occupied[slot], names),
    }
```

Trocar `main` por:
```python
def main(argv=None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="ds2save")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sl = sub.add_parser("slots", help="lista os personagens do save")
    sl.add_argument("--save")
    sn = sub.add_parser("snapshot", help="ficha completa do personagem em JSON")
    sn.add_argument("--save")
    sn.add_argument("--slot", type=int)
    lv = sub.add_parser("levels", help="custo de cada nível entre --from e --to")
    lv.add_argument("--from", dest="frm", type=int, required=True)
    lv.add_argument("--to", type=int, required=True)
    args = parser.parse_args(argv)
    try:
        if args.cmd == "levels":
            out = levels_cost(args.frm, args.to)
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
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python -m pytest tests/test_ds2save.py -q`
Expected: `16 passed` (o teste do save real roda nesta máquina).

- [ ] **Step 5: Conferir contra o jogo**

Run: `python skills/ds2-save/scripts/ds2save.py snapshot`
Expected: JSON com `"name": "Melatonina Vorcaro"`, `"level": 65`, `R1` = Uchigatana e anéis Life Ring, Covetous Silver Serpent Ring+1, Clear Bluestone Ring, Old Leo Ring.

- [ ] **Step 6: Commit**
```bash
git add skills tests
git commit -m "feat: ficha do personagem do DS2 (slots e snapshot)"
git push
```

---

### Task 4: Skills `ds2-save` e `wiki-cache`

**Files:**
- Create: `skills/ds2-save/SKILL.md`, `skills/wiki-cache/SKILL.md`

**Interfaces:**
- Consumes: CLI de `ds2save.py`.
- Produces: instruções que a skill `build` segue; caminho do cache `~/.buildsmith/cache/ds2/<slug>.md`.

- [ ] **Step 1: `skills/ds2-save/SKILL.md`**
```markdown
---
name: ds2-save
description: Lê o save do Dark Souls II SotFS (PC) e devolve a ficha do personagem em JSON (atributos, nível, almas, equipado, inventário) ou o custo em almas de uma faixa de níveis. Use sempre que precisar de dados reais do personagem ou de custo de nível no DS2.
---

# ds2-save

Script: `scripts/ds2save.py` nesta pasta. Precisa de Python 3 e `pycryptodome` (`pip install pycryptodome`).

## Comandos

| Comando | Devolve |
|---|---|
| `python "<pasta>/scripts/ds2save.py" slots` | personagens do save: slot, nome, nível |
| `python "<pasta>/scripts/ds2save.py" snapshot [--slot N] [--save CAMINHO]` | ficha completa em JSON |
| `python "<pasta>/scripts/ds2save.py" levels --from A --to B` | custo de cada nível de A+1 até B e o total |

`<pasta>` é o diretório base desta skill. Sem `--save`, o script usa o arquivo mais recente entre `DS2SOFS*.sl2` e `DS2SOFS*.co2` (Seamless Co-op) em `%APPDATA%\DarkSoulsII\*\`. O save nunca é alterado.

## Regras

- Erro sai como `{"error": "..."}` com código 1. Mostre a mensagem ao usuário; não invente atributos.
- "mais de um personagem" → rode `slots`, pergunte qual é o personagem e passe `--slot`.
- Custo de alma: sempre use `levels`. Nunca some custos de cabeça.
- `hands` usa `L1 R1 L2 R2 L3 R3` (mão esquerda/direita, slots 1–3). `upgrade` é o +N da arma; `null` em consumíveis.
- Itens `desconhecido #ID` existem no save mas não estão nas listas de `games/ds2/ids/`; cite como desconhecidos.
- Equipamento não mostra infusão (ainda não mapeada); pergunte ao usuário se importar.
```

- [ ] **Step 2: `skills/wiki-cache/SKILL.md`**
```markdown
---
name: wiki-cache
description: Busca informação de jogo (onde pegar item, requisitos, builds de outros players) na wiki e guarda em cache local por 30 dias. Use antes de qualquer WebFetch sobre itens, locais, chefes ou builds de um jogo suportado pelo buildsmith.
---

# wiki-cache

Cache em `~/.buildsmith/cache/<jogo>/<slug>.md` (no Windows, `C:\Users\<usuário>\.buildsmith\...`).

## Passos

1. **Slug:** minúsculas, sem acento, espaços e símbolos viram `-`. Ex.: `Magic Stone` → `magic-stone`; builds → `builds-int-dex`.
2. **Ler o cache:** se o arquivo existe e `data` tem menos de 30 dias, use-o e não busque na web.
3. **Buscar:** para DS2 use `https://darksouls2.wiki.fextralife.com/<Nome+Com+Mais>` com WebFetch, pedindo só os fatos necessários (local exato, requisitos, preço, efeito). Se a página tiver tabela grande, abra no navegador embutido e extraia a tabela com JavaScript; não confie em resumo de tabela.
4. **Gravar** o arquivo:
   ~~~markdown
   ---
   assunto: Magic Stone
   fonte: https://darksouls2.wiki.fextralife.com/Magic+Stone
   data: 2026-10-06
   ---
   - Troca de Smooth & Silky Stone com Dyna & Tillo (Things Betwixt), entre outras recompensas.
   - Drop de Gyrm Warriors, Desert Sorceresses e Leydia Witches.
   ~~~
   Escreva só fatos com fonte, em listas curtas. Sem opinião.
5. **Wiki fora do ar:** use o cache mesmo vencido e marque na resposta "dados de DD/MM, podem estar desatualizados". Sem cache e sem wiki: diga que não achou; não chute local de item.

## Builds de outros players

Slug `builds-<arquetipo>`. Para cada build guarde: nome, nível alvo, atributos, armas, catalisador, magias, anéis e URL. Fontes: `PvE+Builds` da wiki e páginas de build individuais.
```

- [ ] **Step 3: Verificar** — as duas skills têm frontmatter com `name` e `description` e nenhum caminho fixo do usuário. Run: `grep -L "^name:" skills/*/SKILL.md`
Expected: saída vazia.

- [ ] **Step 4: Commit**
```bash
git add skills
git commit -m "feat: skills ds2-save e wiki-cache"
git push
```

---

### Task 5: Página do plano (`build-page`)

**Files:**
- Create: `skills/build-page/scripts/validate_plano.py`, `skills/build-page/example/plano.json`, `skills/build-page/template/index.html`, `skills/build-page/SKILL.md`, `tests/test_validate_plano.py`

**Interfaces:**
- Produces: `validate_plano.validate(plano: dict) -> list[str]` (lista de problemas; vazia = ok), CLI `python validate_plano.py <plano.json>` (código 0/1); formato de `plano.json` usado pela skill `build`.

Formato do `plano.json`:
```json
{
  "gerado_em": "2026-10-06T18:00",
  "jogo": "Dark Souls II: Scholar of the First Sin",
  "objetivo": "texto",
  "personagem": {
    "name": "Melatonina Vorcaro", "level": 65, "souls": 0, "soul_memory": 221118,
    "stats": {"VGR": 9, "END": 6, "VIT": 5, "ATN": 30, "STR": 10, "DEX": 18, "INT": 26, "FTH": 6, "ADP": 8},
    "equipado": ["R1 Uchigatana +5", "L1 Sorcerer's Staff +2"]
  },
  "alvo_stats": {"VGR": 20, "END": 15, "VIT": 5, "ATN": 30, "STR": 10, "DEX": 25, "INT": 40, "FTH": 6, "ADP": 8},
  "mudancas": ["texto"],
  "passos": [{"titulo": "texto", "detalhe": "texto", "tipo": "nivel|item|chefe|compra|equipar"}],
  "fases": [{"nome": "VGR 9 → 20", "de": 65, "ate": 76, "almas": 82736}],
  "itens": [{"nome": "texto", "por_que": "texto", "onde": "texto", "requisitos": "texto", "fonte": "url"}],
  "comparacao": [{"build": "texto", "fonte": "url", "diferencas": ["texto"], "sugestao": "texto"}],
  "fontes": [{"titulo": "texto", "url": "url", "data": "2026-10-06"}]
}
```

- [ ] **Step 1: Teste falhando** — `tests/test_validate_plano.py`:
```python
import copy
import json
from pathlib import Path

import validate_plano

EXAMPLE = Path(__file__).resolve().parents[1] / "skills" / "build-page" / "example" / "plano.json"


def example():
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


def test_example_is_valid():
    assert validate_plano.validate(example()) == []


def test_missing_key_is_reported():
    plano = example()
    del plano["fases"]
    assert "falta 'fases'" in validate_plano.validate(plano)


def test_wrong_step_type_is_reported():
    plano = copy.deepcopy(example())
    plano["passos"][0]["tipo"] = "dançar"
    assert any("tipo" in p for p in validate_plano.validate(plano))


def test_phase_souls_must_be_int():
    plano = example()
    plano["fases"][0]["almas"] = "82 mil"
    assert any("almas" in p for p in validate_plano.validate(plano))
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_validate_plano.py -q`
Expected: FAIL com `ModuleNotFoundError: No module named 'validate_plano'`.

- [ ] **Step 3: Validador** — `skills/build-page/scripts/validate_plano.py`:
```python
#!/usr/bin/env python3
"""Confere se o plano.json tem tudo que a página precisa antes de publicar."""
import json
import sys

STATS = ["VGR", "END", "VIT", "ATN", "STR", "DEX", "INT", "FTH", "ADP"]
TIPOS = {"nivel", "item", "chefe", "compra", "equipar"}
TOP = {"gerado_em": str, "jogo": str, "objetivo": str, "personagem": dict, "alvo_stats": dict,
       "mudancas": list, "passos": list, "fases": list, "itens": list, "comparacao": list, "fontes": list}


def validate(plano: dict) -> list[str]:
    problems = []
    for key, kind in TOP.items():
        if key not in plano:
            problems.append(f"falta '{key}'")
        elif not isinstance(plano[key], kind):
            problems.append(f"'{key}' deveria ser {kind.__name__}")
    if problems:
        return problems
    person = plano["personagem"]
    for key in ("name", "level", "souls", "soul_memory", "stats", "equipado"):
        if key not in person:
            problems.append(f"falta 'personagem.{key}'")
    for where, stats in (("personagem.stats", person.get("stats", {})), ("alvo_stats", plano["alvo_stats"])):
        for stat in STATS:
            if not isinstance(stats.get(stat), int):
                problems.append(f"'{where}.{stat}' deveria ser número inteiro")
    for i, step in enumerate(plano["passos"]):
        if not step.get("titulo"):
            problems.append(f"passos[{i}] sem 'titulo'")
        if step.get("tipo") not in TIPOS:
            problems.append(f"passos[{i}].tipo deveria ser um de {sorted(TIPOS)}")
    for i, phase in enumerate(plano["fases"]):
        for key in ("de", "ate", "almas"):
            if not isinstance(phase.get(key), int):
                problems.append(f"fases[{i}].{key} deveria ser número inteiro")
    for i, item in enumerate(plano["itens"]):
        for key in ("nome", "onde"):
            if not item.get(key):
                problems.append(f"itens[{i}] sem '{key}'")
    return problems


def main(argv=None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    argv = argv if argv is not None else sys.argv[1:]
    with open(argv[0], encoding="utf-8") as fh:
        problems = validate(json.load(fh))
    for problem in problems:
        print(problem)
    print("ok" if not problems else f"{len(problems)} problema(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Exemplo** — `skills/build-page/example/plano.json` com os dados reais desta sessão (personagem Melatonina Vorcaro, SL 65; fases VGR 20 = 82.736, INT 40 = 138.935, END 15 = 112.167, DEX 25 = 99.790; passos: anéis, Straid com Fragrant Branch, Dull Ember, Ruin Sentinels, Great Heavy Soul Arrow, Ring of Knowledge; itens Ring of Knowledge, Dull Ember, Magic Stone, Lizard Staff; comparação com "Moonlight Battlemage"; fontes fextralife). Todos os campos do formato acima preenchidos.

- [ ] **Step 5: Rodar e ver passar**

Run: `python -m pytest tests -q`
Expected: todos passam.

- [ ] **Step 6: Modelo HTML** — `skills/build-page/template/index.html`, seguindo a skill `artifact-design` (carregar antes de escrever). Requisitos:
  - `<title>Forja de Build</title>`; tokens de cor em `:root` com tema escuro nos dois blocos (`prefers-color-scheme` e `[data-theme="dark"]`); `body` com fundo de token.
  - Carrega `plano.json` com `fetch("plano.json")`; se falhar, mostra "Não consegui ler o plano.json publicado junto com a página" e nada mais.
  - Seções, nesta ordem: cabeçalho (nome, nível, almas, soul memory, objetivo, data); "Desde a última vez" (`mudancas`); "Próximos passos" (lista numerada, pílula por `tipo`); "Atributos" (barra atual → alvo para os 9 atributos, em escala 0–99); "Fases de nível" (tabela com almas e acumulado, `tabular-nums`); "Onde pegar" (`itens`); "Outras builds" (`comparacao`); "Fontes".
  - Todo texto vindo do JSON passa por escape de HTML. Links externos com `target="_blank" rel="noopener"`.
  - Funciona a 400px de largura sem rolagem horizontal; tabelas dentro de contêiner com `overflow-x: auto`.

- [ ] **Step 7: `skills/build-page/SKILL.md`**
```markdown
---
name: build-page
description: Publica ou atualiza a página fixa do plano de build (modelo HTML + plano.json) do buildsmith. Use no fim do /buildsmith:build, depois que o plano.json estiver pronto.
---

# build-page

## Passos

1. Monte o `plano.json` no formato descrito em `example/plano.json` desta pasta. Números de almas vêm do `ds2save.py levels`.
2. Valide: `python "<pasta>/scripts/validate_plano.py" <caminho>/plano.json`. Corrija até sair `ok`.
3. Copie `<pasta>/template/index.html` e o `plano.json` para `<scratchpad>/buildsmith-page/<jogo>/` (o Artifact só publica arquivos do diretório de trabalho ou do scratchpad).
4. Leia `~/.buildsmith/config.json`. Chave da página: `paginas.<jogo>.<personagem>`.
   - **Tem URL:** rode `Artifact` com `action: "read"` nessa URL, depois publique com `url`, `file_path` = `index.html` copiado e `files: {"plano.json": <caminho do plano.json copiado>}`.
   - **Sem URL:** publique sem `url`, com `icon: "sword"` e `description` de uma frase; grave a URL devolvida em `config.json`.
5. Responda com o link e as 2–3 mudanças mais importantes do plano.

O modelo HTML não muda entre execuções; só o `plano.json` muda.
```

- [ ] **Step 8: Commit**
```bash
git add skills tests
git commit -m "feat: página do plano (modelo, validador e skill build-page)"
git push
```

---

### Task 6: Orquestrador `build`, instalação e teste de aceitação

**Files:**
- Create: `skills/build/SKILL.md`
- Modify: `README.md`

**Interfaces:**
- Consumes: todas as skills anteriores, `~/.buildsmith/` (perfil, histórico, config).
- Produces: comando `/buildsmith:build ds2 [pedido]`.

- [ ] **Step 1: `skills/build/SKILL.md`**
```markdown
---
name: build
description: Planeja a evolução da build a partir do save real do jogo e publica a página do plano. Use quando o usuário digitar /buildsmith:build <jogo>, pedir plano de build, perguntar quanto falta de alma, o que upar, onde pegar item ou como melhorar a build. Jogo suportado: ds2 (Dark Souls II SotFS).
---

# build

Argumentos: `<jogo> [pedido livre]`. Hoje só `ds2`; outro jogo → diga que ainda não há leitor de save para ele.

Dados do usuário em `~/.buildsmith/` (crie as pastas se faltarem): `config.json`, `profiles/<jogo>/`, `history/<jogo>/<personagem>/`, `cache/<jogo>/`.

## Passos

1. **Ficha:** rode o `snapshot` da skill `ds2-save` (`<pasta>/../ds2-save/scripts/ds2save.py`). Se `config.json` tiver `slots.ds2`, passe `--slot`. Erro de "mais de um personagem": rode `slots`, pergunte, grave a escolha em `config.json`.
2. **Histórico:** grave a saída em `history/ds2/<personagem>/<AAAA-MM-DDTHH-MM>.json`. Compare com o arquivo anterior: níveis, atributos, itens novos, upgrades. Isso vira `mudancas` (vazio na primeira vez: "primeira leitura").
3. **Perfil:** leia `profiles/ds2/<personagem>.yaml`. Se não existir, pergunte (uma pergunta por vez, múltipla escolha): arquétipo, itens que não quer trocar, foco secundário. Grave no formato:
   ~~~yaml
   personagem: Melatonina Vorcaro
   slot: 1
   arquetipo: mago INT + espada DEX
   secundario: piromancia (INT+FTH, soft cap 60)
   travados: [Uchigatana]
   nao_migrar: true
   notas: []
   ~~~
   Se o `pedido` mudar o foco ("agora quero piro"), atualize o perfil e diga o que mudou.
4. **Plano:**
   - Defina `alvo_stats` a partir do perfil e dos atributos atuais. Divida em fases de 1 atributo cada, na ordem de prioridade (sobrevivência primeiro quando VGR < 20).
   - Custo de cada fase: `ds2save.py levels --from <nível inicial> --to <nível final>`. Nada de conta manual.
   - Para cada item que falta (catalisador, anel, pedra, magia, armadura), use a skill `wiki-cache`. Só entre em `itens` o que tiver fonte.
   - Compare com builds do mesmo arquétipo via `wiki-cache` (`builds-<arquetipo>`). Proponha ajustes que respeitem `travados` e `nao_migrar`; nunca proponha recomeçar a build.
   - `passos`: no máximo 7, em ordem de execução, começando pelo que dá para fazer na área atual do jogador.
5. **Página:** siga a skill `build-page`.
6. **Resposta no chat:** primeira linha = próximo passo concreto; depois o link da página; no máximo 5 linhas.
```

- [ ] **Step 2: README** — acrescentar seções "Instalar" e "Usar":
```markdown
## Instalar

```bash
pip install pycryptodome
claude plugin marketplace add C:/Users/Matheus/Dev/Projects/buildsmith
claude plugin install buildsmith@buildsmith
```

## Usar

No Claude Code: `/buildsmith:build ds2` ou `/buildsmith:build ds2 quero focar piromancia`.

## Testes

```bash
pip install pytest pycryptodome
python -m pytest -q
```

Listas de IDs do DS2: [DS2S-META](https://github.com/Nordgaren/DS2S-META) (MIT).
```

- [ ] **Step 3: Instalar o plugin** — conferir os subcomandos com `claude plugin --help`; rodar os comandos do README.
Expected: `claude plugin list` mostra `buildsmith`.

- [ ] **Step 4: Teste de aceitação (manual)** — rodar a skill `build` com `ds2` nesta sessão. Conferir:
  1. Cabeçalho da página mostra Melatonina Vorcaro, nível e almas iguais ao jogo.
  2. Fase VGR 9 → 20 mostra 82.736 almas.
  3. Rodar de novo: a URL é a mesma e "Desde a última vez" diz que nada mudou.

- [ ] **Step 5: Commit**
```bash
git add skills README.md
git commit -m "feat: orquestrador /buildsmith:build e instruções de instalação"
git push
```
