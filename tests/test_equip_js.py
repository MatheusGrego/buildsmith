import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "skills" / "build-page" / "template" / "equip.js"
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="sem node para rodar o JS da página")


def rodar(tmp_path, corpo: str):
    script = tmp_path / "t.js"
    script.write_text("global.window = {};\neval(require('fs').readFileSync(process.argv[2], 'utf8'));\n"
                      f"const t = window.buildsmithEquip._teste;\nconsole.log(JSON.stringify((() => {{ {corpo} }})()));",
                      encoding="utf-8")
    out = subprocess.run(["node", str(script), str(JS)], capture_output=True, text=True, encoding="utf-8", timeout=20, check=True)
    return json.loads(out.stdout)


def test_goal_text_shows_upgrade_and_infusion(tmp_path):
    out = rodar(tmp_path, """return [t.metaTexto({nivel: 8, infusao: 1, infusao_nome: "Fogo"}),
                                     t.metaTexto({nivel: 10, infusao: 0, infusao_nome: "Normal"})];""")
    assert out == ["+8 Fogo", "+10"]


def test_what_is_missing_lists_materials_with_what_you_have_and_the_souls(tmp_path):
    falta = {"almas": 11460, "almas_tem": 11583, "ferreiro": "Steady Hand McDuff", "avisos": [],
             "materiais": [{"item": "Titanite Chunk", "qtd": 3, "tem": 0}, {"item": "Firedrake Stone", "qtd": 1, "tem": 1}]}
    out = rodar(tmp_path, f"""return [t.faltaTexto({json.dumps(falta)}),
                                      t.faltaTexto({{almas: 0, almas_tem: 5, materiais: [], avisos: []}})];""")
    assert out == ["3 Titanite Chunk (tem 0) · 1 Firedrake Stone (tem 1) · 11.460 almas (tem 11.583)", "nada: já está assim"]


def test_infusion_options_name_the_stone_and_total_sums_the_damage(tmp_path):
    out = rodar(tmp_path, """return [t.infusaoOpcoes([{k: 0, nome: "Normal", pedra: null}, {k: 1, nome: "Fogo", pedra: "Firedrake Stone"}]),
                                     t.total({ar: {fisico: 161, fogo: 120}}), t.total({ar: 250}), t.total(null)];""")
    assert out == [[{"k": 0, "rotulo": "Normal"}, {"k": 1, "rotulo": "Fogo · Firedrake Stone"}], 281, 250, None]
