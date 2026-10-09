import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
import retrato  # noqa: E402

PNG = b"\x89PNG\r\n\x1a\n" + b"\0" * 20
JPG = b"\xff\xd8\xff\xe0" + b"\0" * 20


def test_only_png_or_jpeg_up_to_2mb(tmp_path):
    assert retrato.tipo_imagem(PNG) == "png" and retrato.tipo_imagem(JPG) == "jpg"
    for ruim in (b"<svg onload=x>", b"GIF89a", b""):
        with pytest.raises(ValueError):
            retrato.gravar(tmp_path, "ds2", "a", ruim)
    with pytest.raises(ValueError):
        retrato.gravar(tmp_path, "ds2", "a", PNG + b"\0" * retrato.MAX_RETRATO)
    assert retrato.achar(tmp_path, "ds2", "a") is None


def test_save_replaces_other_extension_and_clear(tmp_path):
    retrato.gravar(tmp_path, "ds2", "a", PNG)
    retrato.gravar(tmp_path, "ds2", "a", JPG)
    assert retrato.achar(tmp_path, "ds2", "a").suffix == ".jpg"
    assert not (tmp_path / "retratos" / "ds2" / "a.png").exists()
    retrato.limpar(tmp_path, "ds2", "a")
    assert retrato.achar(tmp_path, "ds2", "a") is None


def test_rejects_bad_names(tmp_path):
    for jogo, slug in (("ds2", "../x"), ("../ds2", "a"), ("ds2", "A B")):
        with pytest.raises(ValueError):
            retrato.gravar(tmp_path, jogo, slug, PNG)


def test_latest_steam_print_of_ds2_only(tmp_path):
    shots = tmp_path / "userdata" / "1" / "760" / "remote" / "335300" / "screenshots"
    shots.mkdir(parents=True)
    old, new = shots / "a.jpg", shots / "b.jpg"
    old.write_bytes(JPG)
    new.write_bytes(JPG)
    os.utime(old, (1, 1))
    other = tmp_path / "userdata" / "1" / "760" / "remote" / "999" / "screenshots"
    other.mkdir(parents=True)
    (other / "z.jpg").write_bytes(JPG)
    assert retrato.ultimo_print([tmp_path]) == new
    assert retrato.ultimo_print([tmp_path / "nada"]) is None
