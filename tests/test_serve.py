import json
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
import serve  # noqa: E402
from conftest import build_bnd4, make_slot  # noqa: E402

PNG = b"\x89PNG\r\n\x1a\n" + b"\0" * 20
JPG = b"\xff\xd8\xff\xe0" + b"\0" * 20

FAKE = r'''
import json
print(json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "[etapa:fila] Lendo a fila"}]}}), flush=True)
print(json.dumps({"type": "result", "is_error": False, "result": "ok", "total_cost_usd": 0.1}), flush=True)
'''


@pytest.fixture
def server(tmp_path):
    page = tmp_path / "paginas" / "ds2" / "melatonina-vorcaro"
    (page / "icons").mkdir(parents=True)
    (page / "index.html").write_text("<title>Forja de Build</title><p>olá</p>", encoding="utf-8")
    (page / "plano.json").write_text(json.dumps({"personagem": {"name": "Melatonina Vorcaro"}}), encoding="utf-8")
    (page / "icons" / "a.png").write_bytes(b"\x89PNG")
    fake = tmp_path / "fake_claude.py"
    fake.write_text(FAKE, encoding="utf-8")
    seen = []

    def command(prompt):
        seen.append(prompt)
        return [sys.executable, str(fake)]

    save = tmp_path / "DS2SOFS0000.co2"
    save.write_bytes(build_bnd4({"USER_DATA001": bytes(make_slot(name="Melatonina Vorcaro")),
                                 "USER_DATA002": bytes(make_slot(name="Melatonina (teste)", level=70)),
                                 "USER_DATA011": bytes(0x30000), "USER_DATA012": bytes(0x30000)}))
    steam = tmp_path / "steam"
    httpd = serve.make_server(tmp_path, port=0, runner=serve.Runner(command=command, cwd=tmp_path),
                              save=save, steam_dirs=[steam])
    httpd.prompts = seen
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}", tmp_path
    httpd.shutdown()


def get(url):
    with urllib.request.urlopen(url, timeout=5) as resp:
        return resp.status, resp.headers.get("Content-Type"), resp.read()


def post(url, body, headers=None):
    headers = {"Content-Type": "application/json", "X-Buildsmith": "1", **(headers or {})}
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST", headers=headers)
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


def test_index_opens_latest_page_and_lists_on_request(server):
    base, _ = server
    req = urllib.request.Request(f"{base}/")
    opener = urllib.request.build_opener(NoRedirect)
    with pytest.raises(urllib.error.HTTPError) as err:
        opener.open(req, timeout=5)
    assert err.value.code == 302 and err.value.headers["Location"] == "/p/ds2/melatonina-vorcaro/"
    assert b"/p/ds2/melatonina-vorcaro/" in get(f"{base}/?lista=1")[2]


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def post_raw(url, data, ctype, headers=None):
    headers = {"Content-Type": ctype, "X-Buildsmith": "1", **(headers or {})}
    req = urllib.request.Request(url, data=data, method="POST", headers=headers)
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read())


def test_characters_come_from_the_save(server):
    base, _ = server
    data = json.loads(get(f"{base}/api/ds2/personagens")[2])
    lista = data["personagens"]
    assert [(p["slug"], p["nivel"], p["pagina"]) for p in lista] == [("melatonina-vorcaro", 65, True), ("melatonina-teste", 70, False)]
    assert lista[0]["url"] == "/p/ds2/melatonina-vorcaro/" and lista[1]["url"] is None
    assert lista[0]["retrato"] is None and data["print"] is False


def test_portrait_upload_rules(server):
    base, home = server
    url = f"{base}/api/ds2/melatonina-vorcaro/retrato"
    with pytest.raises(urllib.error.HTTPError) as err:
        post_raw(url, b"<svg onload=alert(1)>", "image/png")
    assert err.value.code == 400
    with pytest.raises(urllib.error.HTTPError) as err:
        post_raw(url, PNG, "image/png", headers={"X-Buildsmith": ""})
    assert err.value.code == 403
    with pytest.raises(urllib.error.HTTPError) as err:
        post_raw(url, PNG + b"\0" * (2 * 1024 * 1024), "image/png")
    assert err.value.code == 413
    assert not (home / "retratos").exists() or not any((home / "retratos").rglob("*.*"))
    post_raw(url, PNG, "image/png")
    status, ctype, body = get(url)
    assert ctype == "image/png" and body == PNG
    personagem = json.loads(get(f"{base}/api/ds2/personagens")[2])["personagens"][0]
    assert personagem["retrato"].startswith("/api/ds2/melatonina-vorcaro/retrato")
    post(f"{base}/api/ds2/melatonina-vorcaro/retrato-limpar", {})
    with pytest.raises(urllib.error.HTTPError) as err:
        get(url)
    assert err.value.code == 404


def test_portrait_from_latest_steam_print(server):
    base, home = server
    with pytest.raises(urllib.error.HTTPError) as err:
        post(f"{base}/api/ds2/melatonina-vorcaro/retrato-print", {})
    assert err.value.code == 404
    shots = home / "steam" / "userdata" / "7" / "760" / "remote" / "335300" / "screenshots"
    shots.mkdir(parents=True)
    (shots / "x.jpg").write_bytes(JPG)
    assert json.loads(get(f"{base}/api/ds2/personagens")[2])["print"] is True
    post(f"{base}/api/ds2/melatonina-vorcaro/retrato-print", {})
    assert get(f"{base}/api/ds2/melatonina-vorcaro/retrato")[2] == JPG


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


def test_post_needs_own_header_and_local_origin(server):
    base, _ = server
    api = f"{base}/api/ds2/melatonina-vorcaro/pedidos/x"
    for headers in ({"X-Buildsmith": ""}, {"Origin": "https://evil.example"}, {"Host": "evil.example"}):
        with pytest.raises(urllib.error.HTTPError) as err:
            post(api, {"texto": "x"}, headers)
        assert err.value.code == 403


def test_run_button_starts_skill_and_reports_stages(server):
    base, _ = server
    api = f"{base}/api/ds2/melatonina-vorcaro"
    with pytest.raises(urllib.error.HTTPError) as err:
        post(f"{api}/rodar", {"modo": "apagar"})
    assert err.value.code == 400
    post(f"{api}/rodar", {"modo": "fila"})
    for _ in range(100):
        st = json.loads(get(f"{api}/execucao?desde=-1")[2])
        if st["estado"] != "rodando":
            break
        time.sleep(0.05)
    assert st["estado"] == "ok" and st["alvo"] == {"jogo": "ds2", "personagem": "melatonina-vorcaro"}
    assert [e["texto"] for e in st["eventos"]][:2] == ["Fila", "Lendo a fila"]


def test_prompt_uses_only_the_page_slug(tmp_path):
    assert serve.build_prompt(tmp_path, "ds2", "melatonina-vorcaro", "fila") == "/buildsmith:build ds2 fila (pela página, personagem: melatonina-vorcaro)"
    assert serve.build_prompt(tmp_path, "ds2", "outro", "plano") == "/buildsmith:build ds2 (pela página, personagem: outro)"


def test_cli_refuses_odd_game_names(tmp_path):
    with pytest.raises(SystemExit):
        serve.main(["estado", "--home", str(tmp_path), "--jogo", "../../x", "--personagem", "Melatonina"])
    assert not (tmp_path / "estado").exists()
