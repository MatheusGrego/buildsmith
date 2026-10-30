import json

import ds2save
import plano_base
import validate_plano


def test_plan_without_ai_is_valid_and_comes_from_the_save(save_file, names):
    snap = ds2save.snapshot(save_file, names=names, regulation=False)
    plano = plano_base.plano_base(snap, "2026-10-11T10:00:00Z")
    assert validate_plano.validate(plano) == []
    assert plano["sem_ia"] is True and plano["itens"] == [] and plano["passos"] == [] and plano["objetivo"] == ""
    p = plano["personagem"]
    assert p["name"] == "Personagem Um" and p["level"] == 65 and p["stats"] == snap["stats"]
    assert {"tipo": "item", "nome": "Uchigatana", "sub": "R1"} in p["equipado"]
    assert {"tipo": "item", "nome": "Sorcerer's Staff", "sub": "L1"} in p["equipado"]
    assert {"tipo": "item", "nome": "Clear Bluestone Ring", "sub": "anel"} in p["equipado"]


def test_pages_are_created_only_for_characters_without_a_page(save_file, tmp_path):
    feitas = []

    def preparar(plano_path, jogo):
        feitas.append((plano_path.parent.name, jogo))
        return {"index": "x"}

    home = tmp_path / "home"
    criadas = plano_base.criar_paginas(home, save_file, preparar=preparar, regulation=False)
    assert criadas == ["ds2/personagem-um"] and feitas == [("personagem-um", "ds2")]
    plano = json.loads((home / "paginas" / "ds2" / "personagem-um" / "plano.json").read_text(encoding="utf-8"))
    assert plano["sem_ia"] and plano["personagem"]["name"] == "Personagem Um"
    assert plano_base.criar_paginas(home, save_file, preparar=preparar, regulation=False) == [] and len(feitas) == 1


def test_failed_page_is_not_left_half_made(save_file, tmp_path):
    home = tmp_path / "home"
    out = plano_base.criar_paginas(home, save_file, preparar=lambda plano, jogo: {"error": "sem jogo"}, regulation=False)
    assert out == [] and not (home / "paginas" / "ds2" / "personagem-um" / "plano.json").exists()


def test_no_save_creates_nothing_and_says_why(tmp_path, monkeypatch):
    avisos = []
    assert plano_base.criar_paginas(tmp_path, tmp_path / "nao-existe.sl2", preparar=lambda p, j: {}, avisa=avisos.append) == []
    assert len(avisos) == 1 and avisos[0].startswith("não li o save do DS2") and "nao-existe.sl2" in avisos[0]
    monkeypatch.setattr(ds2save, "find_save", lambda: (_ for _ in ()).throw(ModuleNotFoundError("No module named 'Crypto'")))
    assert plano_base.criar_paginas(tmp_path, preparar=lambda p, j: {}, avisa=avisos.append) == []
    assert avisos[1].endswith(ds2save.SEM_PYCRYPTODOME)
