import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "skills" / "build-page" / "template" / "catalogo.js"
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="sem node para rodar o JS da página")


def rodar(tmp_path, corpo: str):
    script = tmp_path / "t.js"
    script.write_text(f"const C = require(process.argv[2]);\nconsole.log(JSON.stringify((() => {{ {corpo} }})()));",
                      encoding="utf-8")
    out = subprocess.run(["node", str(script), str(JS)], capture_output=True, text=True, encoding="utf-8", timeout=20, check=True)
    return json.loads(out.stdout)


ITENS = [{"id": 1700000, "nome": "Uchigatana", "cat": "arma", "req": {"STR": 10, "DEX": 16}, "fontes": {"compra": 2}},
         {"id": 31090000, "nome": "Soul Spear", "cat": "feitico", "req": {"INT": 40}, "fontes": {}},
         {"id": 61140000, "nome": "Magic Stone", "cat": "material", "req": {}, "fontes": {"compra": 1, "chao": 3, "drop": 1}},
         {"id": 33010000, "nome": "Fireball", "cat": "piromancia", "req": {}, "fontes": {"troca": 1}}]


def test_filter_by_group_search_without_accents_and_marked(tmp_path):
    out = rodar(tmp_path, f"""
      const itens = {json.dumps(ITENS)};
      const quero = {{"61140000": {{marcado: true}}, "1700000": {{marcado: false}}, "x": {{marcado: true}}}};
      return [C.filtrar(itens, {{cat: "outros"}}).map((i) => i.nome), C.filtrar(itens, {{busca: "  SOUL spéar "}}).map((i) => i.nome),
              C.filtrar(itens, {{quero, soMarcados: true}}).map((i) => i.nome), C.marcados(quero)];""")
    assert out == [["Magic Stone"], ["Soul Spear"], ["Magic Stone"], ["61140000"]]


def test_source_summary_and_requirement_text(tmp_path):
    out = rodar(tmp_path, """return [C.resumoFontes({compra: 2, chao: 1, drop: 3}), C.resumoFontes({}), C.reqTexto({STR: 10, DEX: 16}),
                                     C.grupo("municao"), C.grupo("hex")];""")
    assert out == ["2 lojas · 1 no chão · 3 drops", "sem fonte no jogo", "STR 10 · DEX 16", "outros", "hex"]


def test_marked_items_join_the_plan_without_repeating(tmp_path):
    out = rodar(tmp_path, """
      const plano = {itens: [{id: "large-titanite-shard", item: {nome: "Large Titanite Shard"}}], passos: [{id: "comprar-pedra"}], agora: null};
      const extras = [
        {item: {id: "quero-60975000", item: {nome: "large titanite shard"}}, passos: [{id: "quero-60975000-compra"}]},
        {item: {id: "quero-61140000", item: {nome: "Magic Stone"}}, passos: [{id: "quero-61140000-farm"}, {id: "comprar-pedra"}]},
        null];
      const p = C.juntar(plano, extras);
      return [p.itens.map((i) => [i.id, Boolean(i.marcado)]), p.passos.map((s) => [s.id, Boolean(s.marcado)]), plano.itens.length,
              C.idDoItem(p.itens[1]), C.idDoItem(p.itens[0])];""")
    assert out == [[["large-titanite-shard", False], ["quero-61140000", True]],
                   [["comprar-pedra", False], ["quero-61140000-farm", True]], 1,  # o plano já tem o shard: os passos dele valem
                   "61140000", None]


def test_link_goes_to_the_plan_entry_when_the_plan_has_the_item(tmp_path):
    out = rodar(tmp_path, """
      const plano = {itens: [{id: "magic-stone", item: {nome: "Magic Stone"}}, {id: "quero-1", item: {nome: "Dagger"}}]};
      return [C.idNoPlano(plano, {id: 61140000, nome: "magic stone"}), C.idNoPlano(plano, {id: 1700000, nome: "Uchigatana"})];""")
    assert out == ["magic-stone", "quero-1700000"]


def test_catalog_order_follows_the_category_filters(tmp_path):
    out = rodar(tmp_path, f"return C.ordenar({json.dumps(ITENS)}).map((i) => i.nome);")
    assert out == ["Uchigatana", "Soul Spear", "Fireball", "Magic Stone"]
