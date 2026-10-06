import json

import pytest

import ds2save
from conftest import build_bnd4, make_slot, set_flags


def progresso(path, **kw):
    return ds2save.snapshot(path, regulation=False, **kw)["progresso"]


def test_bosses_come_from_world_flags(world_save):
    chefes = {c["nome"]: c["derrotado"] for c in progresso(world_save)["chefes"]}
    assert chefes["The Pursuer"] is True and chefes["The Last Giant"] is True
    assert chefes["Ruin Sentinels"] is False


def test_purchases_are_read_with_shop_owner(world_save):
    compras = progresso(world_save)["compras"]
    assert [(c["linha"], c["loja"], c["qtd"]) for c in compras] == [
        (76600301, "Carhillion of the Fold", 1), (76430000, "Steady Hand McDuff", 1)]
    assert compras[0]["item"] is None  # sem regulation não há nome do item


def test_all_global_flags_are_listed(world_save):
    assert progresso(world_save)["flags"] == [100968, 100971, 102480]


def test_learned_events(world_save, tmp_path):
    learned = tmp_path / "ds2.json"
    learned.write_text(json.dumps({"eventos": [
        {"nome": "McDuff libertado", "flags": [102480]},
        {"nome": "Straid libertado", "flags": [102999]}]}), encoding="utf-8")
    eventos = {e["nome"]: e["feito"] for e in progresso(world_save, learned=learned)["eventos"]}
    assert eventos == {"McDuff libertado": True, "Straid libertado": False}


def test_missing_world_entry_is_an_error(tmp_path):
    path = tmp_path / "s.sl2"
    path.write_bytes(build_bnd4({"USER_DATA001": bytes(make_slot())}))
    with pytest.raises(ds2save.SaveError, match="USER_DATA011"):
        ds2save.snapshot(path, regulation=False)


def test_flags_diff(tmp_path, capsys):
    before, after = tmp_path / "a.json", tmp_path / "b.json"
    before.write_text(json.dumps({"progresso": {"flags": [100968, 102490]}}), encoding="utf-8")
    after.write_text(json.dumps({"progresso": {"flags": [100968, 102480, 102481]}}), encoding="utf-8")
    assert ds2save.main(["flags-diff", "--antes", str(before), "--depois", str(after)]) == 0
    assert json.loads(capsys.readouterr().out) == {"ligou": [102480, 102481], "desligou": [102490]}


def _real():
    try:
        return ds2save.find_save()
    except ds2save.SaveError:
        return None


@pytest.mark.skipif(_real() is None, reason="sem save real do DS2 nesta máquina")
def test_real_save_progress():
    snap = ds2save.snapshot(_real(), slot=1)
    chefes = {c["nome"]: c["derrotado"] for c in snap["progresso"]["chefes"]}
    assert chefes["The Pursuer"] and chefes["Flexile Sentry"] and not chefes["Ruin Sentinels"]
    compras = {c["item"] for c in snap["progresso"]["compras"]}
    assert "Great Soul Arrow" in compras or None in compras
