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
