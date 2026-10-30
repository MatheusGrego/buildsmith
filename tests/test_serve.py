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
from conftest import build_bnd4, make_slot, registro_eventos  # noqa: E402

PNG = b"\x89PNG\r\n\x1a\n" + b"\0" * 20
JPG = b"\xff\xd8\xff\xe0" + b"\0" * 20

FAKE = r'''
import json
print(json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "[etapa:fila] Lendo a fila"}]}}), flush=True)
print(json.dumps({"type": "result", "is_error": False, "result": "ok", "total_cost_usd": 0.1}), flush=True)
'''


@pytest.fixture
def server(tmp_path):
    page = tmp_path / "paginas" / "ds2" / "personagem-um"
    (page / "icons").mkdir(parents=True)
    (page / "index.html").write_text("<title>Forja de Build</title><p>olá</p>", encoding="utf-8")
    (page / "plano.json").write_text(json.dumps({"personagem": {"name": "Personagem Um"}}), encoding="utf-8")
    (page / "icons" / "a.png").write_bytes(b"\x89PNG")
    fake = tmp_path / "fake_claude.py"
    fake.write_text(FAKE, encoding="utf-8")
    seen = []

    def command(prompt):
        seen.append(prompt)
        return [sys.executable, str(fake)]

    save = tmp_path / "DS2SOFS0000.co2"
    save.write_bytes(build_bnd4({"USER_DATA001": bytes(make_slot(name="Personagem Um")),
                                 "USER_DATA002": bytes(make_slot(name="Personagem (teste)", level=70)),
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
    status, ctype, body = get(f"{base}/p/ds2/personagem-um/")
    assert status == 200 and "charset=utf-8" in ctype
    assert body.startswith(b"<!doctype html>") and "olá".encode() in body


def test_files_of_the_page(server):
    base, _ = server
    assert json.loads(get(f"{base}/p/ds2/personagem-um/plano.json")[2])["personagem"]["name"] == "Personagem Um"
    assert get(f"{base}/p/ds2/personagem-um/icons/a.png")[1] == "image/png"


def test_index_opens_latest_page_and_lists_on_request(server):
    base, _ = server
    req = urllib.request.Request(f"{base}/")
    opener = urllib.request.build_opener(NoRedirect)
    with pytest.raises(urllib.error.HTTPError) as err:
        opener.open(req, timeout=5)
    assert err.value.code == 302 and err.value.headers["Location"] == "/p/ds2/personagem-um/"
    assert b"/p/ds2/personagem-um/" in get(f"{base}/?lista=1")[2]


def test_index_without_pages_says_why_the_save_did_not_open(tmp_path, monkeypatch):
    import ds2save

    monkeypatch.setattr(ds2save, "find_save", lambda: (_ for _ in ()).throw(ds2save.SaveError("nenhum save do DS2 encontrado em <aqui>")))
    httpd = serve.make_server(tmp_path, port=0, steam_dirs=[tmp_path / "steam"])
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        body = get(f"http://127.0.0.1:{httpd.server_address[1]}/")[2].decode("utf-8")
    finally:
        httpd.shutdown()
    assert "Não li o save do DS2: nenhum save do DS2 encontrado em &lt;aqui&gt;" in body


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
    assert [(p["slug"], p["nivel"], p["pagina"]) for p in lista] == [("personagem-um", 65, True), ("personagem-teste", 70, False)]
    assert lista[0]["url"] == "/p/ds2/personagem-um/" and lista[1]["url"] is None
    assert lista[0]["retrato"] is None and data["print"] is False


def test_portrait_upload_rules(server):
    base, home = server
    url = f"{base}/api/ds2/personagem-um/retrato"
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
    assert personagem["retrato"].startswith("/api/ds2/personagem-um/retrato")
    post(f"{base}/api/ds2/personagem-um/retrato-limpar", {})
    with pytest.raises(urllib.error.HTTPError) as err:
        get(url)
    assert err.value.code == 404


def test_portrait_from_latest_steam_print(server):
    base, home = server
    with pytest.raises(urllib.error.HTTPError) as err:
        post(f"{base}/api/ds2/personagem-um/retrato-print", {})
    assert err.value.code == 404
    shots = home / "steam" / "userdata" / "7" / "760" / "remote" / "335300" / "screenshots"
    shots.mkdir(parents=True)
    (shots / "x.jpg").write_bytes(JPG)
    assert json.loads(get(f"{base}/api/ds2/personagens")[2])["print"] is True
    post(f"{base}/api/ds2/personagem-um/retrato-print", {})
    assert get(f"{base}/api/ds2/personagem-um/retrato")[2] == JPG


def test_state_round_trip(server):
    base, home = server
    api = f"{base}/api/ds2/personagem-um"
    post(f"{api}/feitos/equipar-trocar-anel", {"marcado": True})
    state = post(f"{api}/pedidos/bonfire-ascetic", {"texto": "Bonfire Ascetic", "estado": "na_fila"})
    assert state["feitos"]["equipar-trocar-anel"]["marcado"] is True
    on_disk = json.loads((home / "estado" / "ds2" / "personagem-um.json").read_text(encoding="utf-8"))
    assert on_disk["pedidos"]["bonfire-ascetic"]["estado"] == "na_fila"
    assert json.loads(get(f"{api}/estado")[2]) == on_disk


def test_path_traversal_is_refused(server):
    base, _ = server
    for path in ("/p/ds2/../../segredo.txt", "/p/ds2/personagem-um/..%2F..%2Fx", "/api/ds2/x/outra/y"):
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
    serve.write_doc(tmp_path, "ds2", "personagem-um", "pedidos", "bonfire-ascetic", {"texto": "Bonfire Ascetic", "estado": "na_fila"})
    assert serve.main(["responder", "--home", str(tmp_path), "--personagem", "Personagem Um", "--pedido", "bonfire-ascetic", "--item", "bonfire-ascetic"]) == 0
    capsys.readouterr()
    assert serve.main(["estado", "--home", str(tmp_path), "--personagem", "Personagem Um"]) == 0
    state = json.loads(capsys.readouterr().out)
    assert state["pedidos"]["bonfire-ascetic"]["estado"] == "respondido"
    assert state["pedidos"]["bonfire-ascetic"]["item_id"] == "bonfire-ascetic"


def test_post_needs_own_header_and_local_origin(server):
    base, _ = server
    api = f"{base}/api/ds2/personagem-um/pedidos/x"
    for headers in ({"X-Buildsmith": ""}, {"Origin": "https://evil.example"}, {"Host": "evil.example"}):
        with pytest.raises(urllib.error.HTTPError) as err:
            post(api, {"texto": "x"}, headers)
        assert err.value.code == 403


def test_run_button_starts_skill_and_reports_stages(server):
    base, _ = server
    api = f"{base}/api/ds2/personagem-um"
    with pytest.raises(urllib.error.HTTPError) as err:
        post(f"{api}/rodar", {"modo": "apagar"})
    assert err.value.code == 400
    post(f"{api}/rodar", {"modo": "fila"})
    for _ in range(100):
        st = json.loads(get(f"{api}/execucao?desde=-1")[2])
        if st["estado"] != "rodando":
            break
        time.sleep(0.05)
    assert st["estado"] == "ok" and st["alvo"] == {"jogo": "ds2", "personagem": "personagem-um"}
    assert [e["texto"] for e in st["eventos"]][:2] == ["Fila", "Lendo a fila"]


def test_prompt_uses_only_the_page_slug(tmp_path):
    assert serve.build_prompt(tmp_path, "ds2", "personagem-um", "fila") == "/buildsmith:build ds2 fila (pela página, personagem: personagem-um)"
    assert serve.build_prompt(tmp_path, "ds2", "outro", "plano") == "/buildsmith:build ds2 (pela página, personagem: outro)"


def test_cli_refuses_odd_game_names(tmp_path):
    with pytest.raises(SystemExit):
        serve.main(["estado", "--home", str(tmp_path), "--jogo", "../../x", "--personagem", "Personagem"])
    assert not (tmp_path / "estado").exists()


def area_faixa(area):
    v = [0, 0, 0, 0, 0, 1, 1, 0, 0, 1, 0, 1, 2, 0, 0, 2, 0, 1]
    return {"area": area, "malhas": [{"v": v, "f": [0, 2, 1, 1, 2, 3, 2, 4, 3, 3, 4, 5]}]}


@pytest.fixture
def server_mapa(tmp_path):
    import struct
    slot = make_slot(name="Personagem (teste)")
    struct.pack_into("<3f", slot, 0x3A0, -150.5, 12.25, 481.0)
    slot[0x3C0:0x3C4] = bytes([0, 0, 0x10, 0x0A])
    save = tmp_path / "DS2SOFS0000.co2"
    save.write_bytes(build_bnd4({"USER_DATA001": bytes(slot), "USER_DATA011": bytes(0x30000)}))
    chamadas = []

    def carregar(area):
        chamadas.append(area)
        return area_faixa(area)

    httpd = serve.make_server(tmp_path, port=0, runner=serve.Runner(command=lambda p: [sys.executable, "-c", "0"], cwd=tmp_path),
                              save=save, mapa=serve.MapaVivo(tmp_path, save, carregar_area=carregar))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}", chamadas
    httpd.shutdown()


def test_position_comes_from_the_save(server_mapa):
    base, _ = server_mapa
    p = json.loads(get(f"{base}/api/ds2/personagem-teste/posicao")[2])
    assert p["area"] == "m10_16_00_00" and p["pos"] == [-150.5, 12.25, 481.0] and p["slot"] == 1 and p["gravado_em"]
    with pytest.raises(urllib.error.HTTPError) as err:
        get(f"{base}/api/ds2/outro/posicao")
    assert err.value.code == 404


def test_route_on_the_floor_keeps_the_area_in_memory(server_mapa):
    base, chamadas = server_mapa
    url = f"{base}/api/ds2/rota?area=m10_16_00_00&de=0.2,0,0.3&ate=1.8,0,0.6"
    r = json.loads(get(url)[2])
    assert r["rota"]["pontos"][0] == [0.2, 0.0, 0.3] and r["rota"]["pontos"][-1] == [1.8, 0.0, 0.6] and r["rota"]["metros"] > 1.5
    get(url)
    assert chamadas == ["m10_16_00_00"]


def test_route_lists_the_doors_it_crosses_with_the_real_doorway(tmp_path):
    """Porta de dobradiça girada 90° em x = 1, com a dobradiça em z = 0,5: centrada (sem cena) o vão pega z = 0,9;
    com a caixa do modelo na cena 3D (x de 0 a 1,4: o vão vai de z 0,5 a -0,9), a rota em z = 0,9 passa ao lado."""
    porta = {"parte": "o00_0308_0000", "modelo": "o00_0308", "cat": "porta", "nome": "Iron Door", "pos": [1.0, 0.0, 0.5],
             "rot": [0.0, 90.0, 0.0], "chave": None, "estado_ref": "porta:10160300"}
    mapa = serve.MapaVivo(tmp_path, None, carregar_area=lambda area: {**area_faixa(area), "objetos": [porta]})
    r = mapa.rota("m10_16_00_00", [0.2, 0, 0.9], [1.8, 0, 0.9])
    assert [(p["parte"], p["estado_ref"]) for p in r["portas"]] == [("o00_0308_0000", "porta:10160300")]
    cena = tmp_path / "cache" / "ds2" / "cena" / "m10_16_00_00"
    cena.mkdir(parents=True)
    (cena / "cena.json").write_text(json.dumps({"modelos": {"o00_0308": {"bb": [[0, 0, -0.1], [1.4, 2.4, 0.1]]}}}), encoding="utf-8")
    assert mapa.rota("m10_16_00_00", [0.2, 0, 0.9], [1.8, 0, 0.9])["portas"] == []
    assert [p["parte"] for p in mapa.rota("m10_16_00_00", [0.2, 0, 0.2], [1.8, 0, 0.2])["portas"]] == ["o00_0308_0000"]


@pytest.mark.parametrize("query", ["area=../x&de=0,0,0&ate=1,0,0", "area=m10_16_00_00&de=0,0&ate=1,0,0",
                                   "area=m10_16_00_00&de=nan,0,0&ate=1,0,0", "area=m10_16_00_00&de=0,0,0&ate=1e9,0,0"])
def test_route_rejects_bad_input(server_mapa, query):
    base, _ = server_mapa
    with pytest.raises(urllib.error.HTTPError) as err:
        get(f"{base}/api/ds2/rota?{query}")
    assert err.value.code == 400


def test_route_and_position_refuse_other_hosts(server_mapa):
    base, _ = server_mapa
    req = urllib.request.Request(f"{base}/api/ds2/personagem-teste/posicao", headers={"Host": "evil.example"})
    with pytest.raises(urllib.error.HTTPError) as err:
        urllib.request.urlopen(req, timeout=5)
    assert err.value.code == 400


def test_cena_json_geo_and_textures(server):
    import ds2cena
    base, tmp_path = server
    area_dir = tmp_path / "cache" / "ds2" / "cena" / "m10_04_00_00"
    (area_dir / "tex").mkdir(parents=True)
    (area_dir / "cena.json").write_text(json.dumps({"versao": ds2cena.CENA_VERSAO, "area": "m10_04_00_00"}), encoding="utf-8")
    (area_dir / "geo.bin.gz").write_bytes(__import__("gzip").compress(b"\x00\x01\x02\x03"))
    (area_dir / "tex" / "pedra_d.dds").write_bytes(b"DDS " + bytes(124))

    status, ctype, body = get(f"{base}/api/ds2/cena/m10_04_00_00/cena.json")
    assert status == 200 and "application/json" in ctype and json.loads(body)["area"] == "m10_04_00_00"
    status, ctype, body = get(f"{base}/api/ds2/cena/m10_04_00_00/geo.bin")
    assert (status, ctype, body) == (200, "application/octet-stream", b"\x00\x01\x02\x03")  # aberto para quem não aceita gzip
    req = urllib.request.Request(f"{base}/api/ds2/cena/m10_04_00_00/geo.bin", headers={"Accept-Encoding": "gzip, br"})
    with urllib.request.urlopen(req, timeout=5) as resp:
        assert resp.headers["Content-Encoding"] == "gzip"
        assert __import__("gzip").decompress(resp.read()) == b"\x00\x01\x02\x03"
    status, ctype, body = get(f"{base}/api/ds2/cena/m10_04_00_00/tex/pedra_d.dds")
    assert status == 200 and body.startswith(b"DDS ")
    for caminho in ("tex/fantasma.dds", "tex/Pedra_D.dds", "tex/pedra_d.png", "tex/..%2Fcena.json"):
        with pytest.raises(urllib.error.HTTPError) as err:
            get(f"{base}/api/ds2/cena/m10_04_00_00/{caminho}")
        assert err.value.code in (400, 404)


def test_cena_of_an_old_version_counts_as_not_extracted(server):
    base, tmp_path = server
    area_dir = tmp_path / "cache" / "ds2" / "cena" / "m10_04_00_00"
    area_dir.mkdir(parents=True)
    (area_dir / "cena.json").write_text(json.dumps({"versao": 1}), encoding="utf-8")
    (area_dir / "geo.bin.gz").write_bytes(b"\0")
    with pytest.raises(urllib.error.HTTPError) as err:
        get(f"{base}/api/ds2/cena/m10_04_00_00/cena.json")
    assert err.value.code == 404
    corpo = json.loads(err.value.read())
    assert corpo["erro"] == "cena não extraída" and "ds2cena.py extrair --area m10_04_00_00" in corpo["comando"]


@pytest.fixture
def server_cena(tmp_path):
    import ds2cena
    liberar = threading.Event()
    chamadas = []

    def extrair(area, cache_dir):
        chamadas.append(area)
        liberar.wait(5)
        if area == "m10_10_00_00":
            raise OSError("sem o jogo")
        pasta = cache_dir / "cena" / area
        pasta.mkdir(parents=True)
        (pasta / "geo.bin.gz").write_bytes(b"\0")
        (pasta / "cena.json").write_text(json.dumps({"versao": ds2cena.CENA_VERSAO, "area": area}), encoding="utf-8")

    httpd = serve.make_server(tmp_path, port=0, runner=serve.Runner(command=lambda p: [sys.executable, "-c", "0"], cwd=tmp_path),
                              extrair_cena=extrair)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}", liberar, chamadas
    liberar.set()
    httpd.shutdown()


def post_status(url, headers=None):
    req = urllib.request.Request(url, data=b"", method="POST", headers={"X-Buildsmith": "1"} if headers is None else headers)
    with urllib.request.urlopen(req, timeout=5) as resp:
        return resp.status, json.loads(resp.read())


def esperar(url, status, tentativas=60):
    import time
    for _ in range(tentativas):
        try:
            if get(url)[0] == status:
                return True
        except urllib.error.HTTPError as err:
            if err.code == status:
                return True
        time.sleep(0.05)
    return False


def test_cena_extraction_runs_in_background_once(server_cena):
    base, liberar, chamadas = server_cena
    url = f"{base}/api/ds2/cena/m10_04_00_00/cena.json"
    with pytest.raises(urllib.error.HTTPError) as err:
        get(url)
    assert err.value.code == 404  # o GET nunca extrai
    assert post_status(f"{base}/api/ds2/cena/m10_04_00_00/extrair") == (202, {"estado": "extraindo"})
    assert post_status(f"{base}/api/ds2/cena/m10_04_00_00/extrair")[0] == 202  # pedido repetido não começa outra
    status, _, body = get(url)
    assert status == 202 and json.loads(body) == {"estado": "extraindo"}
    liberar.set()
    assert esperar(url, 200)
    assert chamadas == ["m10_04_00_00"]


def test_cena_extraction_error_is_reported(server_cena):
    base, liberar, _ = server_cena
    liberar.set()
    post_status(f"{base}/api/ds2/cena/m10_10_00_00/extrair")
    url = f"{base}/api/ds2/cena/m10_10_00_00/cena.json"
    assert esperar(url, 500)
    with pytest.raises(urllib.error.HTTPError) as err:
        get(url)
    assert "sem o jogo" in json.loads(err.value.read())["erro"]


def test_cena_extraction_needs_the_page_header(server_cena):
    base, _, chamadas = server_cena
    with pytest.raises(urllib.error.HTTPError) as err:
        post_status(f"{base}/api/ds2/cena/m10_04_00_00/extrair", headers={})
    assert err.value.code == 403 and chamadas == []


def test_page_scripts_are_served_as_javascript(server):
    base, tmp_path = server
    vendor = tmp_path / "paginas" / "ds2" / "personagem-um" / "vendor"
    vendor.mkdir()
    (vendor / "three.module.js").write_text("export const REVISION = '160';", encoding="utf-8")
    status, ctype, _ = get(f"{base}/p/ds2/personagem-um/vendor/three.module.js")
    assert status == 200 and ctype.startswith("text/javascript")  # módulo ES não carrega com text/plain


def test_live_save_level_stats_and_items(server_mapa):
    base, _ = server_mapa
    v = json.loads(get(f"{base}/api/ds2/personagem-teste/save")[2])
    assert v["nivel"] == 65 and v["stats"]["INT"] == 26 and v["gravado_em"] and v["chefes"] == []
    assert isinstance(v["itens"], list) and isinstance(v["equipado"], list)
    with pytest.raises(urllib.error.HTTPError) as err:
        get(f"{base}/api/ds2/outro/save")
    assert err.value.code == 404


def area_com_objetos(area):
    return {**area_faixa(area),
            "objetos": [{"parte": "o00_0316_0002", "cat": "porta", "estado_ref": "porta:10160432"},
                        {"parte": "o00_0316_0010", "cat": "porta", "estado_ref": "porta:10160440"},
                        {"parte": "o00_0720_0000", "cat": "alavanca", "estado_ref": "alavanca:10161015"},
                        {"parte": "o16_9999_0000", "cat": "elevador", "estado_ref": None}],
            "itens": [{"lote": 10166180, "estado_ref": "lote:10166180"}, {"lote": 10166190, "estado_ref": "lote:10166190"},
                      {"lote": 10169990, "estado_ref": "lote:10169990"}]}


@pytest.fixture
def server_mundo(tmp_path):
    slot = make_slot(name="Personagem (teste)")
    mundo = bytearray(0x50000)
    regs = [registro_eventos(0x0A100000, [(10160432, 30), (10160440, 10), (10161015, 50)],
                             [(10166180, 0x1100001), (10166190, 0x100401)]),
            registro_eventos(0x0A110000), registro_eventos(0x0A040000)]
    mundo[0x2EF2C:0x2EF2C + 3 * 0xC08] = b"".join(regs)
    save = tmp_path / "DS2SOFS0000.co2"
    save.write_bytes(build_bnd4({"USER_DATA001": bytes(slot), "USER_DATA011": bytes(mundo)}))
    httpd = serve.make_server(tmp_path, port=0, runner=serve.Runner(command=lambda p: [sys.executable, "-c", "0"], cwd=tmp_path),
                              save=save, mapa=serve.MapaVivo(tmp_path, save, carregar_area=area_com_objetos))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}", save
    httpd.shutdown()


def test_world_state_of_the_open_area(server_mundo):
    base, _ = server_mundo
    r = json.loads(get(f"{base}/api/ds2/personagem-teste/mundo?area=m10_16_00_00")[2])
    # só o que tem regra: alavanca com estado 50 e lote fora do vetor ficam de fora (sem estado)
    assert r == {"area": "m10_16_00_00", "objetos": {"o00_0316_0002": True, "o00_0316_0010": False},
                 "lotes": {"10166180": True, "10166190": False}}
    for url, codigo in ((f"{base}/api/ds2/outro/mundo?area=m10_16_00_00", 404), (f"{base}/api/ds2/personagem-teste/mundo?area=../x", 400),
                        (f"{base}/api/ds2/personagem-teste/mundo", 400)):
        with pytest.raises(urllib.error.HTTPError) as err:
            get(url)
        assert err.value.code == codigo


def test_world_state_keeps_the_last_good_one_while_the_game_writes(server_mundo):
    base, save = server_mundo
    url = f"{base}/api/ds2/personagem-teste/mundo?area=m10_16_00_00"
    bom = json.loads(get(url)[2])
    save.write_bytes(save.read_bytes()[:5000])  # o jogo no meio da gravação
    assert json.loads(get(url)[2]) == bom


# ---- Catálogo, fontes por código e itens marcados (sem IA) --------------------------------------------------------

def mundo_com_fogueiras(acesas) -> bytes:
    import struct
    import ds2save
    mundo = bytearray(0x30000)
    for i, fog in enumerate(acesas):
        struct.pack_into("<H", mundo, ds2save.OFF_FOGUEIRAS + 2 * i, fog)
        mundo[ds2save.OFF_FOGUEIRAS + 2 * ds2save.FOGUEIRAS_MAX + i] = 1
    return bytes(mundo)


@pytest.fixture
def server_catalogo(tmp_path):
    from test_ds2fontes import INDICE, MAPAS
    page = tmp_path / "paginas" / "ds2" / "personagem-teste"
    page.mkdir(parents=True)
    (page / "index.html").write_text("<p>ok</p>", encoding="utf-8")
    (page / "plano.json").write_text("{}", encoding="utf-8")
    save = tmp_path / "DS2SOFS0000.co2"
    save.write_bytes(build_bnd4({"USER_DATA001": bytes(make_slot(name="Personagem (teste)", souls=1500)),
                                 "USER_DATA011": mundo_com_fogueiras([14650, 16650])}))
    liberar, chamadas = threading.Event(), []

    def montar():
        chamadas.append(1)
        liberar.wait(5)
        if (tmp_path / "quebrar").exists():
            raise OSError("sem o jogo")
        return INDICE

    httpd = serve.make_server(tmp_path, port=0, runner=serve.Runner(command=lambda p: [sys.executable, "-c", "0"], cwd=tmp_path),
                              save=save, mapa=serve.MapaVivo(tmp_path, save, carregar_area=lambda a: MAPAS[a]),
                              catalogo=serve.Catalogo(tmp_path, montar))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}", tmp_path, liberar, chamadas
    liberar.set()
    httpd.shutdown()


def test_catalog_is_built_in_background_and_lists_every_item(server_catalogo):
    base, home, liberar, chamadas = server_catalogo
    icones = home / "cache" / "ds2" / "icons"
    icones.mkdir(parents=True)
    (icones / "Magic_Stone.png").write_bytes(PNG)
    url = f"{base}/api/ds2/catalogo"
    status, _, body = get(url)
    assert status == 202 and json.loads(body) == {"estado": "montando"}
    get(url)
    liberar.set()
    assert esperar(url, 200) and chamadas == [1]
    itens = {i["nome"]: i for i in json.loads(get(url)[2])["itens"]}
    pedra = itens["Magic Stone"]
    assert pedra["cat"] == "material" and pedra["fontes"] == {"compra": 2, "chao": 3, "drop": 1}
    assert itens["Uchigatana"]["req"] == {"STR": 10, "DEX": 16} and itens["Uchigatana"]["fontes"] == {"troca": 1}
    assert "icone" not in pedra  # o índice de teste não tem a URL do ícone


def test_catalog_icon_is_the_cached_wiki_icon(tmp_path):
    icones = tmp_path / "cache" / "ds2" / "icons"
    icones.mkdir(parents=True)
    (icones / "Soul_Spear.png").write_bytes(PNG)
    item = {"id": 1, "nome": "Soul Spear", "cat": "feitico", "req": {}, "fontes": [],
            "icone": "https://static0.fextralifeimages.com/file/darksouls2/x/Soul_Spear.png"}
    assert serve.resumo_catalogo(tmp_path, item)["icone"] == "icons/Soul_Spear.png"
    assert "icone" not in serve.resumo_catalogo(tmp_path, {**item, "icone": "https://x.example/Outro.png"})


def test_catalog_error_is_reported(server_catalogo):
    base, home, liberar, _ = server_catalogo
    (home / "quebrar").write_text("1", encoding="utf-8")
    liberar.set()
    url = f"{base}/api/ds2/catalogo"
    get(url)
    assert esperar(url, 500)
    with pytest.raises(urllib.error.HTTPError) as err:
        get(url)
    assert "sem o jogo" in json.loads(err.value.read())["erro"]


def test_sources_of_an_item_come_from_the_save_and_the_game(server_catalogo):
    from test_ds2fontes import ITEM, ARMA
    base, _, liberar, _ = server_catalogo
    liberar.set()
    assert esperar(f"{base}/api/ds2/catalogo", 200)
    r = json.loads(get(f"{base}/api/ds2/personagem-teste/fontes?item={ITEM}")[2])
    assert r["item"]["id"] == f"quero-{ITEM}" and r["item"]["item"]["nome"] == "Magic Stone"
    primeira = r["item"]["fontes"][0]
    assert primeira["acesso"] == "agora" and "mais_cedo" in primeira["destaques"] and primeira["mapa"]["area"]
    assert [p["tipo"] for p in r["passos"]] in (["compra"], ["explorar"])
    arma = json.loads(get(f"{base}/api/ds2/personagem-teste/fontes?item={ARMA}")[2])
    assert [p["tipo"] for p in arma["passos"]] == ["troca"] and arma["requisito"] is None  # STR 10 e DEX 18 do slot
    for url, codigo in ((f"{base}/api/ds2/personagem-teste/fontes?item=abc", 400), (f"{base}/api/ds2/personagem-teste/fontes", 400),
                        (f"{base}/api/ds2/personagem-teste/fontes?item=123", 404), (f"{base}/api/ds2/outro/fontes?item={ITEM}", 404)):
        with pytest.raises(urllib.error.HTTPError) as err:
            get(url)
        assert err.value.code == codigo, url


def test_sources_wait_for_the_catalog(server_catalogo):
    base, _, _, _ = server_catalogo
    status, _, body = get(f"{base}/api/ds2/personagem-teste/fontes?item=61140000")
    assert status == 202 and json.loads(body) == {"estado": "montando"}


def test_marked_items_are_kept_per_character(server_catalogo):
    base, home, _, _ = server_catalogo
    api = f"{base}/api/ds2/personagem-teste"
    state = post(f"{api}/quero/61140000", {"item_id": 61140000, "desde": "2026-10-11T10:00:00Z", "marcado": True})
    assert state["quero"]["61140000"] == {"item_id": 61140000, "desde": "2026-10-11T10:00:00Z", "marcado": True}
    post(f"{api}/quero/61140000", {"item_id": 61140000, "desde": "2026-10-11T10:00:00Z", "marcado": False})
    on_disk = json.loads((home / "estado" / "ds2" / "personagem-teste.json").read_text(encoding="utf-8"))
    assert on_disk["quero"]["61140000"]["marcado"] is False
    for doc, body in (("61140000", {"item_id": 1, "marcado": True}), ("61140000", {"item_id": 61140000, "marcado": True, "x": 1}),
                      ("magic-stone", {"item_id": 61140000, "marcado": True}), ("61140000", {"item_id": "61140000", "marcado": True}),
                      ("61140000", {"item_id": 61140000, "marcado": "sim"})):
        with pytest.raises(urllib.error.HTTPError) as err:
            post(f"{api}/quero/{doc}", body)
        assert err.value.code == 400, body


def test_marked_items_have_a_limit(server_catalogo, monkeypatch):
    base, _, _, _ = server_catalogo
    monkeypatch.setattr(serve, "MAX_QUERO", 2)
    api = f"{base}/api/ds2/personagem-teste"
    for i in (1, 2):
        post(f"{api}/quero/{i}", {"item_id": i, "marcado": True})
    with pytest.raises(urllib.error.HTTPError) as err:
        post(f"{api}/quero/3", {"item_id": 3, "marcado": True})
    assert err.value.code == 409
    post(f"{api}/quero/1", {"item_id": 1, "marcado": False})  # desmarcar sempre pode
    post(f"{api}/quero/3", {"item_id": 3, "marcado": True})


def test_page_icon_falls_back_to_the_icon_cache(server_catalogo):
    base, home, _, _ = server_catalogo
    icones = home / "cache" / "ds2" / "icons"
    icones.mkdir(parents=True)
    (icones / "Magic_Stone.png").write_bytes(PNG)
    status, ctype, body = get(f"{base}/p/ds2/personagem-teste/icons/Magic_Stone.png")
    assert status == 200 and body == PNG and ctype == "image/png"
    with pytest.raises(urllib.error.HTTPError) as err:
        get(f"{base}/p/ds2/personagem-teste/icons/Outro.png")
    assert err.value.code == 404


def test_page_without_ai_does_not_take_the_main_page(server):
    base, home = server
    sem_ia = home / "paginas" / "ds2" / "personagem-dois"
    sem_ia.mkdir(parents=True)
    (sem_ia / "index.html").write_text("<p>ok</p>", encoding="utf-8")
    (sem_ia / "plano.json").write_text(json.dumps({"sem_ia": True}), encoding="utf-8")  # mais nova que a da IA
    assert serve.latest_page_url(home, 8642).endswith("/p/ds2/personagem-um/")
    opener = urllib.request.build_opener(NoRedirect)
    with pytest.raises(urllib.error.HTTPError) as err:
        opener.open(urllib.request.Request(f"{base}/"), timeout=5)
    assert err.value.headers["Location"] == "/p/ds2/personagem-um/"


@pytest.fixture
def server_combate(tmp_path):
    slot = make_slot(name="Personagem (teste)")
    save = tmp_path / "DS2SOFS0000.co2"
    save.write_bytes(build_bnd4({"USER_DATA001": bytes(slot), "USER_DATA011": bytes(0x30000)}))
    page = tmp_path / "paginas" / "ds2" / "personagem-teste"
    page.mkdir(parents=True)
    (page / "plano.json").write_text(json.dumps({"equipamento": {"slots": []}}), encoding="utf-8")
    chamadas = []

    def calcular(path, slot_n, indice, plano, metas=None):
        chamadas.append((slot_n, indice is not None, plano))
        (tmp_path / "metas_vistas.json").write_text(json.dumps(metas), encoding="utf-8")
        if (tmp_path / "quebrar").exists():
            raise OSError("save sendo gravado")
        return {"equipamento": {"slots": [{"slot": "R1", "agora": {"nome": "Uchigatana", "nivel": 5, "tipo": "arma"}, "plano": None,
                                           "muda": False}], "sintonia": {}}, "feiticos": {"lista": []}, "dano": [],
                "compras": [{"loja": {"tipo": "npc", "nome": "Steady Hand McDuff"}, "item": {"tipo": "item", "nome": "Uchigatana"}, "qtd": 1}]}

    def simular_arma(path, slot_n, item_id, nivel, infusao):
        if infusao == 7:
            import ds2save
            raise ds2save.SaveError("a arma não aceita a infusão Raw")
        return {"item": {"id": item_id}, "nivel": nivel, "infusao": infusao, "slot": slot_n}

    httpd = serve.make_server(tmp_path, port=0, runner=serve.Runner(command=lambda p: [sys.executable, "-c", "0"], cwd=tmp_path),
                              save=save, mapa=serve.MapaVivo(tmp_path, save, calcular_combate=calcular, simular_arma=simular_arma),
                              catalogo=serve.Catalogo(tmp_path, lambda: {"itens": {}, "areas": {}}))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}", tmp_path, chamadas
    httpd.shutdown()


def test_combat_comes_from_the_save_and_is_kept_until_it_changes(server_combate):
    base, home, chamadas = server_combate
    assert esperar(f"{base}/api/ds2/catalogo", 200)  # com o índice pronto (sem ele, recalcula quando ficar pronto)
    r = json.loads(get(f"{base}/api/ds2/personagem-teste/combate")[2])
    assert r["equipamento"]["slots"][0]["agora"]["nome"] == "Uchigatana" and r["compras"][0]["qtd"] == 1
    get(f"{base}/api/ds2/personagem-teste/combate")
    assert len(chamadas) == 1 and chamadas[0] == (1, True, {"equipamento": {"slots": []}})
    with pytest.raises(urllib.error.HTTPError) as err:
        get(f"{base}/api/ds2/outro/combate")
    assert err.value.code == 404


def test_simulate_a_weapon_by_code(server_combate):
    base, _, _ = server_combate
    api = f"{base}/api/ds2/personagem-teste"
    r = json.loads(get(f"{api}/simular?item=3330000&nivel=8&infusao=1")[2])
    assert r == {"item": {"id": 3330000}, "nivel": 8, "infusao": 1, "slot": 1}
    for q in ("item=abc&nivel=8&infusao=1", "item=3330000&nivel=11&infusao=1", "item=3330000&nivel=8&infusao=10",
              "nivel=8&infusao=1", "item=3330000&nivel=-1&infusao=0"):
        with pytest.raises(urllib.error.HTTPError) as err:
            get(f"{api}/simular?{q}")
        assert err.value.code == 400, q
    with pytest.raises(urllib.error.HTTPError) as err:
        get(f"{api}/simular?item=3330000&nivel=8&infusao=7")
    assert err.value.code == 400 and "não aceita" in json.loads(err.value.read())["erro"]
    with pytest.raises(urllib.error.HTTPError) as err:
        get(f"{base}/api/ds2/outro/simular?item=3330000&nivel=8&infusao=1")
    assert err.value.code == 404


def test_goals_per_weapon_are_kept_and_validated(server_combate):
    base, home, _ = server_combate
    api = f"{base}/api/ds2/personagem-teste"
    meta = {"item_id": 3330000, "nivel": 8, "infusao": 1, "ativa": True, "desde": "2026-10-12T10:00:00Z"}
    assert post(f"{api}/metas/3330000", meta)["metas"]["3330000"] == meta
    for doc, body in (("3330000", {**meta, "nivel": 11}), ("3330000", {**meta, "infusao": 10}), ("3330000", {**meta, "x": 1}),
                      ("1700000", meta), ("3330000", {**meta, "ativa": "sim"}), ("3330000", {**meta, "nivel": True})):
        with pytest.raises(urllib.error.HTTPError) as err:
            post(f"{api}/metas/{doc}", body)
        assert err.value.code == 400, body


def test_goals_have_a_limit(server_combate, monkeypatch):
    base, _, _ = server_combate
    monkeypatch.setattr(serve, "MAX_METAS", 1)
    api = f"{base}/api/ds2/personagem-teste"
    post(f"{api}/metas/1", {"item_id": 1, "nivel": 0, "infusao": 0, "ativa": True})
    with pytest.raises(urllib.error.HTTPError) as err:
        post(f"{api}/metas/2", {"item_id": 2, "nivel": 0, "infusao": 0, "ativa": True})
    assert err.value.code == 409
    post(f"{api}/metas/1", {"item_id": 1, "nivel": 0, "infusao": 0, "ativa": False})  # tirar sempre pode
    post(f"{api}/metas/2", {"item_id": 2, "nivel": 0, "infusao": 0, "ativa": True})


def test_combat_gets_the_goals_and_is_redone_when_they_change(server_combate):
    base, home, chamadas = server_combate
    assert esperar(f"{base}/api/ds2/catalogo", 200)
    api = f"{base}/api/ds2/personagem-teste"
    get(f"{api}/combate")
    assert json.loads((home / "metas_vistas.json").read_text(encoding="utf-8")) == {}
    post(f"{api}/metas/3330000", {"item_id": 3330000, "nivel": 8, "infusao": 1, "ativa": True})
    get(f"{api}/combate")
    assert len(chamadas) == 2
    assert json.loads((home / "metas_vistas.json").read_text(encoding="utf-8"))["3330000"]["nivel"] == 8


def test_combat_error_is_503(server_combate):
    base, home, _ = server_combate
    (home / "quebrar").write_text("1", encoding="utf-8")
    with pytest.raises(urllib.error.HTTPError) as err:
        get(f"{base}/api/ds2/personagem-teste/combate")
    assert err.value.code == 503


class LeitorFalso:
    def __init__(self, quebrar=False):
        self.n, self.quebrar = 0, quebrar

    def ler(self):
        if self.quebrar:
            raise RuntimeError("leitura quebrada")
        self.n += 1
        return {"ativo": True, "nome": "Personagem Um", "pos": [1.0, 2.0, float(self.n)], "yaw_camera": 0.5, "ts": self.n}


@pytest.fixture
def server_vivo(tmp_path):
    leitor = LeitorFalso()
    httpd = serve.make_server(tmp_path, port=0, runner=serve.Runner(command=lambda p: [sys.executable, "-c", "0"], cwd=tmp_path),
                              vivo=serve.FluxoVivo(leitor, intervalo=0.05))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}", leitor, httpd
    httpd.shutdown()


def test_live_state_once(server_vivo):
    base, leitor, _ = server_vivo
    r = json.loads(get(f"{base}/api/ds2/vivo")[2])
    assert r["ativo"] and r["nome"] == "Personagem Um" and r["pos"][:2] == [1.0, 2.0]


def test_live_stream_sends_events_and_survives_the_client_leaving(server_vivo):
    import time
    base, leitor, _ = server_vivo
    resp = urllib.request.urlopen(f"{base}/api/ds2/vivo/stream", timeout=5)
    assert resp.headers.get("Content-Type").startswith("text/event-stream")
    eventos, inicio = [], time.time()
    while len(eventos) < 3 and time.time() - inicio < 3:
        linha = resp.readline().decode("utf-8").strip()
        if linha.startswith("data: "):
            eventos.append(json.loads(linha[6:]))
    resp.close()
    assert len(eventos) == 3 and eventos[0]["pos"][2] < eventos[2]["pos"][2]  # valores novos a cada leitura
    time.sleep(0.3)
    lidas = leitor.n
    time.sleep(0.3)
    assert leitor.n == lidas  # sem cliente, a thread para de ler o jogo
    assert json.loads(get(f"{base}/api/ds2/vivo")[2])["ativo"]  # e o servidor segue respondendo


def test_reader_failure_is_inactive_not_an_error(tmp_path):
    fluxo = serve.FluxoVivo(LeitorFalso(quebrar=True))
    assert fluxo.atual() == {"ativo": False, "motivo": "erro na leitura (RuntimeError)"}


def test_minimap_page_gets_the_page_csp(server):
    base, home = server
    page = home / "paginas" / "ds2" / "personagem-um"
    (page / "overlay.html").write_text("<title>Minimapa</title><p>m</p>", encoding="utf-8")
    with urllib.request.urlopen(f"{base}/p/ds2/personagem-um/overlay.html", timeout=5) as resp:
        body = resp.read()
        assert resp.headers.get("Content-Security-Policy") == serve.CSP_PAGINA
        assert body.startswith(b"<!doctype html>") and b"<title>Minimapa</title>" in body


def test_overlay_page_follows_the_character_loaded_in_the_game(server):
    base, home = server
    save = home / "DS2SOFS0000.co2"
    (home / "paginas" / "ds2" / "personagem-teste").mkdir(parents=True)

    class Vivo:
        def __init__(self, nome):
            self.nome = nome

        def atual(self):
            return {"ativo": bool(self.nome), "nome": self.nome}

    assert serve.slug_do_jogador(home, Vivo("Personagem (teste)"), save) == "personagem-teste"
    assert serve.slug_do_jogador(home, Vivo("Personagem Um"), save) == "personagem-um"
    assert serve.slug_do_jogador(home, Vivo(None), save) in ("personagem-um", "personagem-teste")  # sem jogo: a mais recente


def test_same_name_in_the_game_opens_the_main_page_of_those_characters(tmp_path):
    save = tmp_path / "DS2SOFS0000.co2"
    save.write_bytes(build_bnd4({"USER_DATA001": bytes(make_slot(name="Stacy", level=12)),
                                 "USER_DATA002": bytes(make_slot(name="Stacy", level=39)),
                                 "USER_DATA011": bytes(0x30000), "USER_DATA012": bytes(0x30000)}))
    for slug, plano in (("stacy-1", {"sem_ia": True}), ("stacy", {"objetivo": "hex"})):
        page = tmp_path / "paginas" / "ds2" / slug
        page.mkdir(parents=True)
        (page / "plano.json").write_text(json.dumps(plano), encoding="utf-8")

    class Vivo:
        def atual(self):
            return {"ativo": True, "nome": "Stacy"}

    assert serve.slug_do_jogador(tmp_path, Vivo(), save) == "stacy"  # a do plano da IA, não a primeira do save


def test_overlay_key_route_calls_the_overlay_action(server, monkeypatch):
    import overlay

    base, _ = server
    chamadas = []
    monkeypatch.setitem(overlay.ACOES, "grande", lambda: chamadas.append("grande"))
    assert post(f"{base}/api/overlay/grande", {}) == {"ok": True} and chamadas == ["grande"]
    monkeypatch.delitem(overlay.ACOES, "mini", raising=False)
    assert post(f"{base}/api/overlay/mini", {}) == {"ok": False}
    with pytest.raises(urllib.error.HTTPError) as err:  # sem o cabeçalho próprio: recusado como todo POST
        urllib.request.urlopen(urllib.request.Request(f"{base}/api/overlay/grande", data=b"{}", method="POST"), timeout=5)
    assert err.value.code == 403 and chamadas == ["grande"]
