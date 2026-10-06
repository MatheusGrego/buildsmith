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


from conftest import build_bnd4


def test_read_bnd4_roundtrip():
    data = build_bnd4({"USER_DATA000": b"resumo", "USER_DATA001": bytes(range(40))})
    entries = ds2save.read_bnd4(data)
    assert entries["USER_DATA000"][:6] == b"resumo"
    assert entries["USER_DATA001"][:40] == bytes(range(40))


def test_read_bnd4_rejects_other_files():
    with pytest.raises(ds2save.SaveError):
        ds2save.read_bnd4(b"PK\x03\x04 isto e um zip")
