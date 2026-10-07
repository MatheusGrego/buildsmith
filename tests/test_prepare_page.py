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
