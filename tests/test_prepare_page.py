import json
from pathlib import Path

import pytest

import prepare_page

EXAMPLE = Path(__file__).resolve().parents[1] / "skills" / "build-page" / "example" / "plano.json"
PNG = b"\x89PNG falso"


class FakeFetch:
    def __init__(self, fail=()):
        self.calls = []
        self.fail = set(fail)

    def __call__(self, url):
        self.calls.append(url)
        if url in self.fail:
            raise OSError("sem rede")
        if url.startswith("https://darksouls2.wiki.fextralife.com/"):  # página do item: quadro com o ícone
            nome = url.rsplit("/", 1)[-1]
            return (f'<div class="infobox"><table><tr><td><img src="https://static0.fextralifeimages.com/file/'
                    f'darksouls2/x/{nome}.png"></td></tr></table></div>').encode()
        return PNG


def example():
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


def run(tmp_path, fetch, plano=None):
    src = tmp_path / "plano-entrada.json"
    src.write_text(json.dumps(plano or example(), ensure_ascii=False), encoding="utf-8")
    return prepare_page.prepare(src, tmp_path / "saida", "ds2", cache_root=tmp_path / "cache", fetch=fetch)


def final_plan(tmp_path):
    return json.loads((tmp_path / "saida" / "plano.json").read_text(encoding="utf-8"))


def test_rewrites_icons_to_local_files(tmp_path):
    out = run(tmp_path, FakeFetch())
    icons = [node["icone"] for step in final_plan(tmp_path)["passos"] for node in step["fluxo"] if "icone" in node]
    assert icons and all(icon.startswith("icons/") for icon in icons)
    for rel in icons:
        assert Path(out["files"][rel]).read_bytes() == PNG


def test_includes_stat_icons_template_and_plan(tmp_path):
    out = run(tmp_path, FakeFetch())
    assert {f"icons/stat-{s}.png" for s in ("VGR", "END", "VIT", "ATN", "STR", "DEX", "INT", "FTH", "ADP")} <= set(out["files"])
    assert "icons/almas.png" in out["files"]
    assert Path(out["files"]["plano.json"]).exists()
    assert Path(out["index"]).read_text(encoding="utf-8").startswith("<title>")


def test_cache_avoids_second_download(tmp_path):
    fetch = FakeFetch()
    run(tmp_path, fetch)
    first = len(fetch.calls)
    run(tmp_path, fetch)
    assert first > 0 and len(fetch.calls) == first


def test_same_icon_is_downloaded_once(tmp_path):
    fetch = FakeFetch()
    run(tmp_path, fetch)
    assert len(fetch.calls) == len(set(fetch.calls))


def test_failed_download_becomes_warning(tmp_path):
    plano = example()
    url = plano["passos"][0]["fluxo"][0]["icone"]
    out = run(tmp_path, FakeFetch(fail={url}), plano)
    assert "icone" not in final_plan(tmp_path)["passos"][0]["fluxo"][0]
    assert any(url in aviso for aviso in out["avisos"])


def test_invalid_plan_is_rejected(tmp_path):
    plano = example()
    plano["versao"] = 1
    with pytest.raises(ValueError, match="versao"):
        run(tmp_path, FakeFetch(), plano)


def test_cli_prints_files(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(prepare_page, "default_fetch", FakeFetch())
    src = tmp_path / "p.json"
    src.write_text(json.dumps(example(), ensure_ascii=False), encoding="utf-8")
    code = prepare_page.main([str(src), str(tmp_path / "saida"), "--jogo", "ds2", "--cache", str(tmp_path / "cache")])
    assert code == 0
    assert "plano.json" in json.loads(capsys.readouterr().out)["files"]


def test_progress_and_damage_icons_are_local(tmp_path):
    run(tmp_path, FakeFetch())
    plano = final_plan(tmp_path)
    nodes = [plano["dano"][0]["arma"], *plano["dano"][0]["por_causa"]]
    nodes += [c["loja"] for c in plano["progresso"]["compras"] if "icone" in c["loja"]]
    assert nodes and all(n["icone"].startswith("icons/") for n in nodes if "icone" in n)


def test_bonfire_checkbox_and_new_sections_get_icons(tmp_path):
    out = run(tmp_path, FakeFetch())
    assert "icons/fogueira.png" in out["files"]
    plano = final_plan(tmp_path)
    nodes = [plano["feiticos"]["catalisador"], *[s["no"] for s in plano["feiticos"]["lista"]], *plano["agora"]["faltam"]]
    assert all(n["icone"].startswith("icons/") for n in nodes if "icone" in n)


def test_icons_only_come_from_the_wiki(tmp_path):
    plano = example()
    fluxo = plano["passos"][0]["fluxo"]
    fluxo[0]["icone"] = "https://evil.example/pixel.png?d=segredo"
    fluxo[1]["icone"] = "https://static0.fextralifeimages.com.evil.example/x.png"
    fetch = FakeFetch()
    out = run(tmp_path, fetch, plano)
    assert not any("evil.example" in url for url in fetch.calls)
    nodes = final_plan(tmp_path)["passos"][0]["fluxo"]
    assert "icone" not in nodes[0] and "icone" not in nodes[1]
    assert sum("fora da wiki" in aviso for aviso in out["avisos"]) == 2


def test_icon_download_does_not_follow_redirects_off_the_wiki():
    handler = prepare_page.WikiRedirects()
    req = prepare_page.urllib.request.Request("https://static0.fextralifeimages.com/x.png")
    with pytest.raises(prepare_page.urllib.error.HTTPError):
        handler.redirect_request(req, None, 302, "Found", {}, "https://evil.example/?d=segredo")
    assert handler.redirect_request(req, None, 302, "Found", {}, "https://static1.fextralifeimages.com/y.png") is not None


def test_index_is_assembled_from_template_parts():
    html = prepare_page.montar_index(prepare_page.SKILL_DIR / "template")
    assert html.startswith("<title>") and "<!--CSS-->" not in html and "<!--JS-->" not in html
    assert "const limpaPedido" in html
    assert html.count("<script>") == 1 and html.count("<style>") == 1


def test_assembly_refuses_part_that_closes_its_own_tag(tmp_path):
    for name, text in (("index.html", "<title>x</title><!--CSS--><!--JS-->"), ("pagina.css", "a{}"), ("pagina.js", "x()")):
        (tmp_path / name).write_text(text, encoding="utf-8")
    (tmp_path / "pagina.js").write_text("x() </script><script>alert(1)", encoding="utf-8")
    with pytest.raises(ValueError):
        prepare_page.montar_index(tmp_path)


def faixa_area():
    v = [0, 0, 0, 0, 0, 1, 1, 0, 0, 1, 0, 1, 2, 0, 0, 2, 0, 1, 3, 0, 0, 3, 0, 1, 90, 0, 90, 91, 0, 90, 90, 0, 91]
    f = [0, 2, 1, 1, 2, 3, 2, 4, 3, 3, 4, 5, 4, 6, 5, 5, 6, 7, 8, 9, 10]
    return {"area": "m10_16_00_00", "nome": "The Lost Bastille", "assinatura": "x", "origem": [0, 0, 0],
            "malhas": [{"v": v, "f": f}],
            "fogueiras": [{"id": 16675, "nome": "Servants' Quarters", "pos": [0.2, 0, 0.3]}],
            "itens": [{"lote": 10165010, "pos": [2.9, 0, 0.6], "itens": [{"id": 1, "nome": "Soul Vessel", "qtd": 1}]},
                      {"lote": 10165020, "pos": [1.5, 0, 0.5], "itens": [{"id": 3, "nome": "Radiant Lifegem", "qtd": 1},
                                                                           {"id": 2, "nome": "Large Titanite Shard", "qtd": 2}]}],
            "inimigos": [{"id": 145, "pos": [1.0, 0, 0.5]}],
            "npcs": [{"id": 7680, "nome": "Straid of Olaphis", "pos": [2.5, 0, 0.5]},
                     {"id": 7520, "nome": "Lucatiel of Mirrah", "pos": [0.5, 0, 0.5]}],
            "chefes": [{"flag": 100962, "nome": "Ruin Sentinels", "wiki": "https://darksouls2.wiki.fextralife.com/Ruin+Sentinels",
                        "pos": [2.0, 0, 0.8]}],
            "inicio": [0.1, 0, 0.1]}


def plano_com_pontos():
    plano = example()
    fonte = plano["itens"][0]["fontes"][0]
    fonte["fluxo"][0]["ponto"] = {"area": "m10_16_00_00", "tipo": "fogueira", "ref": 16675}
    fonte["fluxo"][-1]["ponto"] = {"area": "m10_16_00_00", "tipo": "item", "ref": 10165010}
    return plano


def test_plan_points_become_area_and_route(tmp_path):
    src = tmp_path / "p.json"
    src.write_text(json.dumps(plano_com_pontos(), ensure_ascii=False), encoding="utf-8")
    out = prepare_page.prepare(src, tmp_path / "saida", "ds2", cache_root=tmp_path / "cache", fetch=FakeFetch(),
                               carregar_area=lambda area: faixa_area())
    mapa = final_plan(tmp_path)["itens"][0]["fontes"][0]["mapa"]
    assert mapa["area"] == "m10_16_00_00" and mapa["nome"] == "The Lost Bastille"
    assert [p["tipo"] for p in mapa["pontos"]] == ["fogueira", "item"] and mapa["pontos"][0]["n"] == 1
    assert len(mapa["trechos"]) == 1 and mapa["trechos"][0][0] == [0.2, 0, 0.3] and 2.7 <= mapa["metros"] <= 4
    assert all("andar" in p for p in mapa["pontos"])
    area = json.loads(Path(out["files"]["mapas/m10_16_00_00.json"]).read_text(encoding="utf-8"))
    assert area["nome"] == "The Lost Bastille" and "malhas" not in area and area["planta"]["andares"]
    pontos = {p["lote"]: p for p in area["itens"]}
    assert pontos[10165020]["plano"] is True and pontos[10165020]["item_id"] == "large-titanite-shard"
    assert pontos[10165020]["itens"][0]["nome"] == "Large Titanite Shard"  # o item do plano vem primeiro (rótulo e ícone)
    assert pontos[10165010]["plano"] is False and pontos[10165010]["icone"].startswith("icons/")
    assert Path(out["files"][pontos[10165020]["icone"]]).exists()
    assert all("andar" in p for p in area["fogueiras"] + area["itens"] + area["inimigos"])
    indice = json.loads(Path(out["files"]["mapas/indice.json"]).read_text(encoding="utf-8"))
    assert indice == [{"area": "m10_16_00_00", "nome": "The Lost Bastille", "itens_plano": 1}]


def test_area_is_included_only_by_plan_item_name(tmp_path):
    outra = {**faixa_area(), "area": "m10_04_00_00", "nome": "Majula",
             "itens": [{"lote": 9, "pos": [1, 0, 1], "itens": [{"id": 9, "nome": "Rubbish", "qtd": 1}]}]}
    areas = {"m10_16_00_00": faixa_area(), "m10_04_00_00": outra}
    src = tmp_path / "p.json"
    src.write_text(json.dumps(example(), ensure_ascii=False), encoding="utf-8")
    out = prepare_page.prepare(src, tmp_path / "saida", "ds2", cache_root=tmp_path / "cache", fetch=FakeFetch(),
                               carregar_area=lambda area: areas[area], listar_areas=lambda: list(areas))
    assert "mapas/m10_16_00_00.json" in out["files"] and "mapas/m10_04_00_00.json" not in out["files"]


def test_unknown_point_is_an_error(tmp_path):
    plano = plano_com_pontos()
    plano["itens"][0]["fontes"][0]["fluxo"][-1]["ponto"]["ref"] = 999
    src = tmp_path / "p.json"
    src.write_text(json.dumps(plano, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="item:999"):
        prepare_page.prepare(src, tmp_path / "saida", "ds2", cache_root=tmp_path / "cache", fetch=FakeFetch(),
                             carregar_area=lambda area: faixa_area())


def test_without_game_the_page_has_no_map_and_a_warning(tmp_path):
    def sem_jogo(area):
        raise OSError("DS2 SotFS não encontrado")

    src = tmp_path / "p.json"
    src.write_text(json.dumps(plano_com_pontos(), ensure_ascii=False), encoding="utf-8")
    out = prepare_page.prepare(src, tmp_path / "saida", "ds2", cache_root=tmp_path / "cache", fetch=FakeFetch(),
                               carregar_area=sem_jogo)
    assert any("mapa indisponível" in a for a in out["avisos"])
    assert "mapa" not in final_plan(tmp_path)["itens"][0]["fontes"][0]



def test_page_area_has_zones_plan_npcs_and_boss_state(tmp_path):
    plano = plano_com_pontos()
    plano["progresso"]["chefes"].append({"no": {"tipo": "chefe", "nome": "Ruin Sentinels"}, "estado": "derrotado"})
    src = tmp_path / "p.json"
    src.write_text(json.dumps(plano, ensure_ascii=False), encoding="utf-8")
    out = prepare_page.prepare(src, tmp_path / "saida", "ds2", cache_root=tmp_path / "cache", fetch=FakeFetch(),
                               carregar_area=lambda area: faixa_area())
    area = json.loads(Path(out["files"]["mapas/m10_16_00_00.json"]).read_text(encoding="utf-8"))
    assert area["zonas"]["lista"] and area["zonas"]["lista"][0]["ordem"] == 1
    assert all(p.get("zona") for p in area["itens"] + area["npcs"] + area["chefes"] + area["fogueiras"])
    npcs = {n["nome"]: n for n in area["npcs"]}
    assert npcs["Straid of Olaphis"]["plano"] is True
    assert {"Ring of Knowledge", "Heavy Homing Soul Arrow"} <= set(npcs["Straid of Olaphis"]["precisa"])
    assert npcs["Lucatiel of Mirrah"]["plano"] is False and npcs["Lucatiel of Mirrah"]["precisa"] == []
    assert npcs["Straid of Olaphis"]["retrato"].startswith("icons/")
    chefe = area["chefes"][0]
    assert chefe["estado"] == "derrotado" and chefe["retrato"].startswith("icons/")


def test_page_enemies_carry_game_data_and_the_player_area_comes_in(tmp_path):
    area = faixa_area()
    area["inimigos"] = [{"id": 145, "pos": [1.0, 0, 0.5], "tipo": 152002, "papel": None},
                        {"id": 146, "pos": [2.5, 0, 0.5], "tipo": 768000, "papel": "npc"}]
    area["tipos_inimigo"] = {"152002": {"hp": 450, "almas": 180, "drops": ["Royal Greatsword"]}}
    areas = {"m10_16_00_00": area, "m10_04_00_00": {**faixa_area(), "area": "m10_04_00_00", "nome": "Majula", "itens": []}}
    src = tmp_path / "p.json"
    src.write_text(json.dumps(plano_com_pontos(), ensure_ascii=False), encoding="utf-8")
    out = prepare_page.prepare(src, tmp_path / "saida", "ds2", cache_root=tmp_path / "cache", fetch=FakeFetch(),
                               carregar_area=lambda a: areas[a], area_jogador="m10_04_00_00")
    doc = json.loads(Path(out["files"]["mapas/m10_16_00_00.json"]).read_text(encoding="utf-8"))
    assert [e["tipo"] for e in doc["inimigos"]] == ["152002"]  # gerador de NPC não vira inimigo
    assert doc["tipos_inimigo"]["152002"] == {"nome": None, "wiki": None, "prova": None, "n": 1, "hp": 450, "almas": 180,
                                              "drops": ["Royal Greatsword"]}
    assert "mapas/m10_04_00_00.json" in out["files"]


def test_player_area_uses_the_plan_character_name(monkeypatch):
    prepare_page._ds2mapa()
    import ds2save
    vistos = []
    monkeypatch.setattr(ds2save, "find_save", lambda: "save")
    monkeypatch.setattr(ds2save, "slot_by_name", lambda save, nome: vistos.append(nome) or 2)
    monkeypatch.setattr(ds2save, "posicao", lambda save, slot: {"area": "m10_04_00_00", "pos": [0, 0, 0]})
    assert prepare_page.area_do_jogador_real(example()) == "m10_04_00_00"
    assert vistos == [example()["personagem"]["name"]]
    monkeypatch.setattr(ds2save, "find_save", lambda: (_ for _ in ()).throw(ds2save.SaveError("sem save")))
    assert prepare_page.area_do_jogador_real(example()) is None


class FetchComEscala(FakeFetch):
    def __call__(self, url):
        if url.endswith("/Uchigatana"):
            self.calls.append(url)
            linha = "".join(f"<td>{c}</td>" for c in ["Regular", 115, "-", "-", "-", "-", "150 20", "E", "B", "-", "-", "-", "-", "-"])
            return (f'<div class="infobox"><img src="https://static0.fextralifeimages.com/file/darksouls2/x/Uchigatana.png"></div>'
                    f'<div id="mw-content-text"><table><tr>{linha}</tr></table></div>').encode()
        return super().__call__(url)


def test_equipment_gets_icons_and_scaling_letters(tmp_path):
    plano = example()
    plano["equipamento"] = {
        "slots": [{"slot": "R1", "grupo": "direita", "muda": False,
                   "agora": {"nome": "Uchigatana", "tipo": "arma", "nivel": 5, "ar": 218},
                   "plano": {"nome": "Uchigatana", "tipo": "arma", "nivel": 6, "ar": 231}},
                  {"slot": "peito", "grupo": "armadura", "muda": True, "agora": None,
                   "plano": {"nome": "Black Witch Robe", "categoria": "Armor"}}],
        "sintonia": {"agora": [{"nome": "Soul Arrow", "ar": 174}], "plano": []},
        "resumo": [{"dado": "R1", "agora": "Uchigatana +5 · AR 218", "depois": "Uchigatana +6 · AR 231", "efeito": "+13", "sinal": "+"}]}
    run(tmp_path, FetchComEscala(), plano)
    eq = final_plan(tmp_path)["equipamento"]
    uchi = eq["slots"][0]["agora"]
    assert uchi["escala"] == {"STR": "E", "DEX": "B"} and uchi["escala_nivel"] == 0
    assert uchi["escala_fonte"].endswith("/Uchigatana") and uchi["icone"].startswith("icons/")
    assert eq["slots"][1]["plano"]["icone"].startswith("icons/") and "escala" not in eq["slots"][1]["plano"]  # armadura: sem letra
    assert eq["sintonia"]["agora"][0]["icone"].startswith("icons/")


def test_invalid_equipment_block_is_rejected(tmp_path):
    plano = example()
    plano["equipamento"] = {"slots": [{"slot": "R1", "grupo": "pé", "agora": None, "plano": None}]}
    with pytest.raises(ValueError, match="equipamento.slots"):
        run(tmp_path, FakeFetch(), plano)
