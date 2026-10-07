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


def test_old_version_is_rejected():
    plano = example()
    plano["versao"] = 1
    assert "versao deveria ser 2" in validate_plano.validate(plano)


def test_wrong_step_type_is_reported():
    plano = example()
    plano["passos"][0]["tipo"] = "item"
    assert any("passos[0].tipo" in p for p in validate_plano.validate(plano))


def test_wrong_node_type_is_reported():
    plano = example()
    plano["passos"][0]["fluxo"][0]["tipo"] = "arma"
    assert any("passos[0].fluxo[0].tipo" in p for p in validate_plano.validate(plano))


def test_wrong_sign_is_reported():
    plano = example()
    plano["passos"][0]["dados"][0]["sinal"] = "++"
    assert any("sinal" in p for p in validate_plano.validate(plano))


def test_row_without_data_name_is_reported():
    plano = example()
    del plano["passos"][0]["dados"][0]["dado"]
    assert any("sem 'dado'" in p for p in validate_plano.validate(plano))


def test_long_title_is_reported():
    plano = example()
    plano["passos"][0]["titulo"] = "x" * 41
    assert any("40 caracteres" in p for p in validate_plano.validate(plano))


def test_phase_souls_must_be_int():
    plano = example()
    plano["fases"][0]["almas"] = "82 mil"
    assert any("almas" in p for p in validate_plano.validate(plano))


def test_progress_and_damage_are_valid_in_example():
    plano = example()
    assert plano["progresso"]["chefes"] and plano["dano"]
    assert validate_plano.validate(plano) == []


def test_progress_and_damage_are_optional():
    plano = example()
    del plano["progresso"], plano["dano"]
    assert validate_plano.validate(plano) == []


def test_wrong_boss_state_is_reported():
    plano = example()
    plano["progresso"]["chefes"][0]["estado"] = "morto"
    assert any("progresso.chefes[0].estado" in p for p in validate_plano.validate(plano))


def test_wrong_event_state_is_reported():
    plano = example()
    plano["progresso"]["eventos"] = [{"nome": "Straid libertado", "estado": "talvez"}]
    assert any("progresso.eventos[0].estado" in p for p in validate_plano.validate(plano))


def test_damage_value_must_be_int_or_dash():
    plano = example()
    plano["dano"][0]["depois"] = "muito"
    assert any("dano[0].depois" in p for p in validate_plano.validate(plano))


def test_every_step_type_is_accepted():
    for tipo in validate_plano.GRUPOS:
        plano = example()
        plano["passos"][0]["tipo"] = tipo
        assert validate_plano.validate(plano) == [], tipo


def test_item_sources_need_valid_access():
    plano = example()
    plano["itens"][0]["fontes"][0]["acesso"] = "logo"
    assert any("acesso" in p for p in validate_plano.validate(plano))


def test_each_item_has_exactly_one_earliest_source():
    plano = example()
    for fonte in plano["itens"][0]["fontes"]:
        fonte["destaques"] = [d for d in fonte.get("destaques", []) if d != "mais_cedo"]
    assert any("mais_cedo" in p for p in validate_plano.validate(plano))


def test_sources_are_sorted_by_access():
    plano = example()
    fontes = next(i["fontes"] for i in plano["itens"] if len({f["acesso"] for f in i["fontes"]}) > 1)
    fontes.reverse()
    assert any("ordem" in p for p in validate_plano.validate(plano))


def test_every_cited_item_needs_a_source():
    plano = example()
    plano["passos"][0]["fluxo"].append({"tipo": "item", "nome": "Item Sem Fonte"})
    assert any("Item Sem Fonte" in p for p in validate_plano.validate(plano))


def test_owned_items_are_exempt_from_sources():
    plano = example()
    plano["passos"][0]["fluxo"].append({"tipo": "item", "nome": "Item Que Já Tenho", "tem": True})
    assert validate_plano.validate(plano) == []


def test_steps_and_items_need_unique_ids():
    plano = example()
    plano["passos"][1]["id"] = plano["passos"][0]["id"]
    assert any("id repetido" in p for p in validate_plano.validate(plano))
    plano = example()
    del plano["itens"][0]["id"]
    assert any("itens[0] sem 'id'" in p for p in validate_plano.validate(plano))


def test_requirement_link_must_point_to_item():
    plano = example()
    plano["itens"][0]["fontes"][0]["requisito"] = {"texto": "algo", "item": "nao-existe"}
    assert any("nao-existe" in p for p in validate_plano.validate(plano))


def test_now_panel_points_to_existing_steps():
    plano = example()
    assert plano["agora"]["acoes"]
    plano["agora"]["acoes"] = ["passo-fantasma"]
    assert any("passo-fantasma" in p for p in validate_plano.validate(plano))


def test_spells_block_is_validated():
    plano = example()
    assert plano["feiticos"]["lista"]
    plano["feiticos"]["lista"][0]["estado"] = "talvez"
    assert any("feiticos.lista[0].estado" in p for p in validate_plano.validate(plano))


def test_links_must_be_http_and_icons_https_or_local():
    plano = example()
    node = plano["passos"][0]["fluxo"][0]
    node["link"] = "javascript:alert(1)"
    node["icone"] = "data:image/png;base64,AAAA"
    plano["fontes"][0]["url"] = "file:///etc/passwd"
    problems = validate_plano.validate(plano)
    assert "passos[0].fluxo[0].link deveria ser um link http(s)" in problems
    assert "passos[0].fluxo[0].icone deveria ser https://... ou icons/<arquivo>" in problems
    assert "fontes[0].url deveria ser um link http(s)" in problems
    node["link"], node["icone"], plano["fontes"][0]["url"] = "https://darksouls2.wiki.fextralife.com/X", "icons/x.png", ""
    assert validate_plano.validate(plano) == []
