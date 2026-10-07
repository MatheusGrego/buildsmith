import json
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
import serve  # noqa: E402


@pytest.fixture
def server(tmp_path):
    page = tmp_path / "paginas" / "ds2" / "melatonina-vorcaro"
    (page / "icons").mkdir(parents=True)
    (page / "index.html").write_text("<title>Forja de Build</title><p>olá</p>", encoding="utf-8")
    (page / "plano.json").write_text(json.dumps({"personagem": {"name": "Melatonina Vorcaro"}}), encoding="utf-8")
    (page / "icons" / "a.png").write_bytes(b"\x89PNG")
    httpd = serve.make_server(tmp_path, port=0)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}", tmp_path
    httpd.shutdown()


def get(url):
    with urllib.request.urlopen(url, timeout=5) as resp:
        return resp.status, resp.headers.get("Content-Type"), resp.read()


def post(url, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST", headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read())


def test_page_is_served_with_doctype_and_charset(server):
    base, _ = server
    status, ctype, body = get(f"{base}/p/ds2/melatonina-vorcaro/")
    assert status == 200 and "charset=utf-8" in ctype
    assert body.startswith(b"<!doctype html>") and "olá".encode() in body


def test_files_of_the_page(server):
    base, _ = server
    assert json.loads(get(f"{base}/p/ds2/melatonina-vorcaro/plano.json")[2])["personagem"]["name"] == "Melatonina Vorcaro"
    assert get(f"{base}/p/ds2/melatonina-vorcaro/icons/a.png")[1] == "image/png"


def test_index_lists_characters(server):
    base, _ = server
    assert b"/p/ds2/melatonina-vorcaro/" in get(f"{base}/")[2]


def test_state_round_trip(server):
    base, home = server
    api = f"{base}/api/ds2/melatonina-vorcaro"
    post(f"{api}/feitos/equipar-trocar-anel", {"marcado": True})
    state = post(f"{api}/pedidos/bonfire-ascetic", {"texto": "Bonfire Ascetic", "estado": "na_fila"})
    assert state["feitos"]["equipar-trocar-anel"]["marcado"] is True
    on_disk = json.loads((home / "estado" / "ds2" / "melatonina-vorcaro.json").read_text(encoding="utf-8"))
    assert on_disk["pedidos"]["bonfire-ascetic"]["estado"] == "na_fila"
    assert json.loads(get(f"{api}/estado")[2]) == on_disk


def test_path_traversal_is_refused(server):
    base, _ = server
    for path in ("/p/ds2/../../segredo.txt", "/p/ds2/melatonina-vorcaro/..%2F..%2Fx", "/api/ds2/x/outra/y"):
        with pytest.raises(urllib.error.HTTPError) as err:
            if path.startswith("/api"):
                post(base + path, {})
            else:
                get(base + path)
        assert err.value.code in (400, 404)


def test_ping(server):
    base, _ = server
    assert json.loads(get(f"{base}/api/ping")[2])["app"] == "buildsmith"


def test_cli_answers_a_request(tmp_path, capsys):
    serve.write_doc(tmp_path, "ds2", "melatonina-vorcaro", "pedidos", "bonfire-ascetic", {"texto": "Bonfire Ascetic", "estado": "na_fila"})
    assert serve.main(["responder", "--home", str(tmp_path), "--personagem", "Melatonina Vorcaro", "--pedido", "bonfire-ascetic", "--item", "bonfire-ascetic"]) == 0
    capsys.readouterr()
    assert serve.main(["estado", "--home", str(tmp_path), "--personagem", "Melatonina Vorcaro"]) == 0
    state = json.loads(capsys.readouterr().out)
    assert state["pedidos"]["bonfire-ascetic"]["estado"] == "respondido"
    assert state["pedidos"]["bonfire-ascetic"]["item_id"] == "bonfire-ascetic"
