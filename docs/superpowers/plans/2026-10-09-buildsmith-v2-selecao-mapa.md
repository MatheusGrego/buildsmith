# Forja v2: layout novo, seleção de personagem e mapa do jogo — plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** trocar a página pelo layout do protótipo `design_novo/ui_kits/forja-v2`, escolher entre os personagens do save com retrato automático, e desenhar em isométrico, com dados do próprio jogo, onde fica cada passo e item, com a rota pelo chão.

**Architecture:** duas entregas que funcionam sozinhas. (A) Python (`ds2save`, `serve.py`) ganha a lista de personagens, o retrato e a correção da armadura; o template vira fontes separadas (`index.html` + `pagina.css` + `pagina.js`) que o `prepare_page` junta num só arquivo (o CSP da página só aceita script inline). (B) `ds2arquivos.py` abre os arquivos cifrados do jogo; `ds2mapa.py` extrai chão (navmesh), fogueiras, itens e inimigos de uma área para o cache e calcula rotas; o plano aponta `ponto` nos nós; o `prepare_page` copia as áreas usadas e as rotas; `mapa.js` desenha.

**Tech Stack:** Python 3.12 só com biblioteca padrão + `pycryptodome` (já usado); página em HTML/CSS/JS puro, sem build; pytest; node só para checar sintaxe e o teste de `limpaPedido`.

**Spec:** aprovado no chat em 2026-10-09 (sem arquivo, a pedido do usuário). Pontos aprovados: layout do `forja-v2`; seleção lista os personagens do save (Carregar / Gerar plano, sem "Novo personagem"); retrato = equipamento do save + botão "Usar último print" (Steam, app 335300); mapa só da área do alvo, passos da wiki postos no ponto exato do jogo e ligados pela rota do chão com o aviso "rota pelo chão; portas e alavancas não aparecem"; sem jogo instalado a página mostra os passos sem mapa e diz o motivo.

## Global Constraints

- Nada do jogo vai para o repositório: mapas e textos extraídos ficam em `~/.buildsmith/cache/ds2/`.
- Regra de credibilidade (skills `build`/`build-page`): posição vem do jogo; ordem dos passos vem da wiki; sem fonte, sem marcador.
- Texto em pt-BR, termos do jogo em inglês; dados, não frases; nada de verde nem check; feito = fogueira acesa.
- A página só carrega ícone local (`icons/...`), só abre link http(s), só fala com o próprio servidor (CSP atual de `serve.py`).
- POST novo no servidor exige `X-Buildsmith: 1` e Host/Origin locais (o `_trusted` atual).
- Retrato: só PNG ou JPEG (pelos bytes iniciais), até 2 MB.
- Toda execução sem janela passa pelo guarda (`app/guard.py`): subcomando novo de script precisa entrar na lista dele.
- Antes de cada commit: `git pull --rebase` (outra sessão também empurra na `master`); push direto na `master`, sem PR.

## Review Focus

1. Save com 1 personagem só, ou personagem sem página: a seleção mostra "Gerar plano" e não quebra a página atual. Teste na Task 2.
2. Item com mais de um ponto no jogo (ex.: Fragrant Branch of Yore ×2 na Lost Bastille): `onde` devolve todos, e a skill escolhe um por fonte. Teste na Task 9.
3. Ponto sem caminho pelo chão (componente separada do navmesh): `rota` devolve `null` e a página mostra os marcadores sem linha. Teste na Task 10.
4. Jogo não instalado ou arquivo trocado por atualização: `prepare_page` não falha, só avisa, e a página diz "Mapa indisponível". Teste na Task 11.
5. Upload de arquivo que não é imagem, imagem grande demais ou POST sem cabeçalho próprio: 400/413/403 e nada gravado. Teste na Task 2.

---

# Entrega A — layout v2 e seleção de personagem

## File Structure (A)

- Modify `skills/ds2-save/scripts/ds2save.py`: armadura com ID de item (+10.000.000); `slot_by_name` aceita nome ou slug; nova `personagens(path, names)`.
- Modify `app/serve.py`: `GET /api/<jogo>/personagens`; retrato (`GET`/`POST .../retrato`, `POST .../retrato-print`, `POST .../retrato-limpar`); `/` redireciona para a última página.
- Create `app/retrato.py`: valida imagem, grava/lê retrato, acha o último print da Steam. Uma responsabilidade, testável sem servidor.
- Create `skills/build-page/template/pagina.css`, `skills/build-page/template/pagina.js`; `index.html` vira só o esqueleto com `<!--CSS-->` e `<!--JS-->`.
- Modify `skills/build-page/scripts/prepare_page.py`: `montar_index(template_dir) -> str` junta as fontes.
- Tests: `tests/test_ds2save.py`, `tests/test_retrato.py` (novo), `tests/test_serve.py`, `tests/test_prepare_page.py`, `tests/test_injection.py` (caminho do `limpaPedido`).

### Task 1: armadura, slug e lista de personagens no `ds2save`

**Files:** Modify `skills/ds2-save/scripts/ds2save.py`; Test `tests/test_ds2save.py`

**Interfaces:**
- Produces: `ARMOR_ITEM_OFFSET = 10_000_000`; `slot_by_name(path, name: str) -> int` (aceita "Melatonina (teste)" ou "melatonina-teste"); `personagens(path, names=None) -> list[dict]` com `{"slot", "nome", "slug", "nivel", "soul_memory", "equipado": {"cabeca","peito","maos","pernas","R1","L1"} -> {"id","name"}}`.

- [ ] **Step 1: testes que falham**

```python
def test_armor_uses_item_ids(tmp_path, names):
    slot = make_slot(name="A")
    struct.pack_into("<4I", slot, ds2save.OFF_ARMOR, 12460100, 12460101, 12460102, 12460103)
    path = tmp_path / "a.sl2"
    path.write_bytes(build_bnd4({"USER_DATA001": bytes(slot), "USER_DATA011": bytes(0x30000)}))
    armor = ds2save.snapshot(path, names={22460100: ("Armor", "Tseldora Cap")}, regulation=False)["equipped"]["armor"]
    assert armor["cabeca"] == {"id": 22460100, "name": "Tseldora Cap"}

def test_slot_by_slug_and_character_list(tmp_path, names):
    path = tmp_path / "multi.sl2"
    path.write_bytes(build_bnd4({"USER_DATA001": bytes(make_slot(name="Melatonina Vorcaro")),
                                 "USER_DATA002": bytes(make_slot(name="Melatonina (teste)", level=10)),
                                 "USER_DATA011": bytes(0x30000), "USER_DATA012": bytes(0x30000)}))
    assert ds2save.slot_by_name(path, "melatonina-teste") == 2
    lista = ds2save.personagens(path, names=names)
    assert [(p["slot"], p["slug"], p["nivel"]) for p in lista] == [(1, "melatonina-vorcaro", 65), (2, "melatonina-teste", 10)]
    assert set(lista[0]["equipado"]) == {"cabeca", "peito", "maos", "pernas", "R1", "L1"}
```

- [ ] **Step 2:** `python -m pytest tests/test_ds2save.py -q` → os dois falham (armadura "desconhecido", `personagens` não existe).
- [ ] **Step 3: implementação**

```python
ARMOR_ITEM_OFFSET = 10_000_000  # o slot guarda o ID da ArmorParam; o item (e o nome) é esse + 10.000.000

def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", _plain(text)).strip("-")

def slot_by_name(path, name: str) -> int:
    found = list_slots(path)
    for item in found:
        if _slug(item["name"]) == _slug(name):
            return item["slot"]
    options = ", ".join(f'{item["slot"]}: {item["name"]}' for item in found) or "nenhum"
    raise SaveError(f"personagem {name!r} não está no save (personagens: {options})")

def personagens(path, names=None) -> list[dict]:
    names = names if names is not None else load_item_names()
    out = []
    for number, slot in _occupied(_read_entries(path)):
        info = parse_slot(slot, names)
        eq = info["equipped"]
        equipado = {k: eq["armor"].get(k) for k in ("cabeca", "peito", "maos", "pernas")}
        equipado.update({k: eq["hands"].get(k) for k in ("R1", "L1")})
        out.append({"slot": number, "nome": info["name"], "slug": _slug(info["name"]), "nivel": info["level"],
                    "soul_memory": info["soul_memory"], "equipado": equipado})
    return out
```

Em `parse_slot`, a linha da armadura passa a ser `"armor": {k: named(i + ARMOR_ITEM_OFFSET) for k, i in zip(ARMOR_SLOTS, _ids(slot, OFF_ARMOR, 4)) if i not in EMPTY}`. `_plain` já existe; `_slug` reaproveita.

- [ ] **Step 4:** `python -m pytest -q` → tudo passa; no save real, `python skills/ds2-save/scripts/ds2save.py snapshot --personagem melatonina-teste` mostra slot 2 e armadura "Tseldora Cap".
- [ ] **Step 5:** commit `fix: armadura com ID de item, personagem pelo slug e lista de personagens do save`.

### Task 2: retrato e lista de personagens no servidor

**Files:** Create `app/retrato.py`; Modify `app/serve.py`; Tests `tests/test_retrato.py`, `tests/test_serve.py`

**Interfaces:**
- Consumes: `ds2save.personagens`, `ds2save.find_save` (import via `sys.path` para `skills/ds2-save/scripts`).
- Produces (`app/retrato.py`): `tipo_imagem(data: bytes) -> str | None` ("png"/"jpg"); `gravar(home, jogo, slug, data) -> Path` (levanta `ValueError` se não for imagem ou passar de `MAX_RETRATO = 2 * 1024 * 1024`); `achar(home, jogo, slug) -> Path | None`; `limpar(home, jogo, slug) -> None`; `ultimo_print(steam_dirs=None, app=335300) -> Path | None`.
- Produces (HTTP): `GET /api/<jogo>/personagens` → `{"personagens": [{..., "pagina": bool, "url": str|None, "retrato": "/api/<jogo>/<slug>/retrato"|None, "equipado_icones": [{"nome","icone"}]}], "print": bool}`; `GET /api/<jogo>/<slug>/retrato`; `POST /api/<jogo>/<slug>/retrato` (corpo = bytes da imagem); `POST .../retrato-print`; `POST .../retrato-limpar`; `GET /` → 302 para a página mais recente (sem página: a lista atual).

- [ ] **Step 1: testes que falham** (`tests/test_retrato.py`)

```python
PNG = b"\x89PNG\r\n\x1a\n" + b"\0" * 20
JPG = b"\xff\xd8\xff\xe0" + b"\0" * 20

def test_only_png_or_jpeg_up_to_2mb(tmp_path):
    assert retrato.tipo_imagem(PNG) == "png" and retrato.tipo_imagem(JPG) == "jpg"
    for ruim in (b"<svg onload=x>", b"GIF89a", b""):
        with pytest.raises(ValueError):
            retrato.gravar(tmp_path, "ds2", "a", ruim)
    with pytest.raises(ValueError):
        retrato.gravar(tmp_path, "ds2", "a", PNG + b"\0" * retrato.MAX_RETRATO)

def test_save_replaces_other_extension_and_clear(tmp_path):
    retrato.gravar(tmp_path, "ds2", "a", PNG)
    retrato.gravar(tmp_path, "ds2", "a", JPG)
    assert retrato.achar(tmp_path, "ds2", "a").suffix == ".jpg"
    retrato.limpar(tmp_path, "ds2", "a")
    assert retrato.achar(tmp_path, "ds2", "a") is None

def test_latest_steam_print(tmp_path):
    shots = tmp_path / "userdata" / "1" / "760" / "remote" / "335300" / "screenshots"
    shots.mkdir(parents=True)
    old, new = shots / "a.jpg", shots / "b.jpg"
    old.write_bytes(JPG); new.write_bytes(JPG)
    os.utime(old, (1, 1))
    other = tmp_path / "userdata" / "1" / "760" / "remote" / "999" / "screenshots"
    other.mkdir(parents=True); (other / "z.jpg").write_bytes(JPG)
    assert retrato.ultimo_print([tmp_path]) == new
```

Em `tests/test_serve.py` (a fixture `server` ganha `BUILDSMITH_STEAM` apontando para uma pasta temporária e um save sintético em `BUILDSMITH_SAVE`):

```python
def test_portrait_upload_rules(server):
    base, home = server
    url = f"{base}/api/ds2/melatonina-vorcaro/retrato"
    with pytest.raises(urllib.error.HTTPError) as err:
        post_raw(url, b"<svg/>", "image/png")
    assert err.value.code == 400
    with pytest.raises(urllib.error.HTTPError) as err:
        post_raw(url, PNG, "image/png", headers={"X-Buildsmith": ""})
    assert err.value.code == 403
    post_raw(url, PNG, "image/png")
    status, ctype, body = get(url)
    assert ctype == "image/png" and body == PNG

def test_characters_from_save(server):
    base, _ = server
    lista = json.loads(get(f"{base}/api/ds2/personagens")[2])["personagens"]
    assert [(p["slug"], p["pagina"]) for p in lista] == [("melatonina-vorcaro", True), ("melatonina-teste", False)]
```

- [ ] **Step 2:** rodar → falham.
- [ ] **Step 3: implementação**: `app/retrato.py` com as funções acima (pastas `~/.buildsmith/retratos/<jogo>/<slug>.<png|jpg>`, gravação atômica com `os.replace`; `ultimo_print` procura `<raiz>/userdata/*/760/remote/<app>/screenshots/*.jpg` nas raízes `BUILDSMITH_STEAM` ou `C:/Program Files (x86)/Steam` e `C:/Program Files/Steam`). Em `serve.py`: rota de corpo binário própria (`_raw_body(limit=MAX_RETRATO)`), as rotas acima, `find_save` respeitando `BUILDSMITH_SAVE` para os testes, e `_index` → 302 quando `pages(home)` não estiver vazio. `equipado_icones` vem do `plano.json` da página do personagem (nós de `personagem.equipado` com `icone` local, prefixados por `/p/<jogo>/<slug>/`).
- [ ] **Step 4:** `python -m pytest -q` → passa.
- [ ] **Step 5:** commit `feat: lista de personagens do save e retrato (upload, último print da Steam) no servidor local`.

### Task 3: template em fontes separadas, montado num arquivo só

**Files:** Modify `skills/build-page/template/index.html`; Create `skills/build-page/template/pagina.css`, `skills/build-page/template/pagina.js`; Modify `skills/build-page/scripts/prepare_page.py`; Tests `tests/test_prepare_page.py`, `tests/test_injection.py`

**Interfaces:** Produces `prepare_page.montar_index(template_dir: Path) -> str` (troca `<!--CSS-->` por `<style>…</style>` e `<!--JS-->` por `<script>…</script>`; levanta `ValueError` se faltar marcador ou se o CSS/JS tiver `</style>`/`</script>`).

- [ ] **Step 1: testes que falham**

```python
def test_index_is_assembled_from_template_parts(tmp_path):
    html = prepare_page.montar_index(prepare_page.SKILL_DIR / "template")
    assert html.startswith("<title>") and "<!--CSS-->" not in html and "<!--JS-->" not in html
    assert "function limpaPedido" in html or "const limpaPedido" in html
    assert html.count("<script>") == 1 and html.count("<style>") == 1
```

Em `tests/test_injection.py`, o teste do `limpaPedido` passa a ler `skills/build-page/template/pagina.js`.

- [ ] **Step 2:** rodar → falha (`montar_index` não existe).
- [ ] **Step 3:** mover o `<style>` para `pagina.css` e o `<script>` para `pagina.js` sem mudar comportamento; `index.html` fica com `<title>`, fontes do Google, `<!--CSS-->`, o `<main>`, a faixa e `<!--JS-->`; `prepare()` grava `montar_index(...)` em vez de copiar.
- [ ] **Step 4:** `python -m pytest -q` e `node --check` no `pagina.js` → passam.
- [ ] **Step 5:** commit `refactor: template da página em index/pagina.css/pagina.js, montado pelo prepare_page`.

### Task 4: layout v2 (cabeçalho, menu lateral, lista + detalhe)

**Files:** Modify `skills/build-page/template/{index.html,pagina.css,pagina.js}`

**Interfaces:** Consumes o mesmo `plano.json` e a mesma API local; Produces as funções de seção `secaoAgora(p)`, `secaoPassos(p)`, `secaoOnde(p)`, `secaoDano(p)`… chamadas por `render(p)`, e `mestreDetalhe({itens, sel, linha, detalhe})` (HTML de lista + detalhe com `data-md-sel`). O detalhe de Onde pegar e de Passos tem `<div class="mapa-slot" data-mapa="...">` vazio (Entrega B preenche).

Porte de `design_novo/ui_kits/forja-v2/{AppV2.jsx,v2.css}` para JS puro, reaproveitando `node`, `flow`, `rows`, `grid`, `requisito`, `fogueira`, `applyState`, Forja e `localDb` atuais:
- Cabeçalho `.topo`: retrato 56×72 (Task 5 preenche), meta (jogo · atualizado), `h1`, botão "Trocar personagem", Nível/Almas/Soul memory, legenda, ações da Forja.
- `.corpo` = `nav.menu` (grupos Plano: Agora, Passos, Fases · Coletar: Onde pegar, Fila · Combate: Dano, Feitiços, Atributos · Registro: Ficha, Progresso, Builds, Fontes; contadores) + `main.conteudo` (uma seção por vez, `aria-current="page"` no item ativo, lembra a seção em `localStorage` e no `#hash`).
- Passos e Onde pegar em lista + detalhe (`.md`, `.md-lista`, `.md-det`); fontes clicáveis `.fonte-v`.
- Dano em barras (`.dano-l`, `.dano-bar .now/.ganho`).
- Celular (< 760px): menu vira faixa horizontal, lista + detalhe empilha.
- CSS do `v2.css` com tokens do design system (`--dim:#8a8885` do v2).

- [ ] **Step 1:** portar; `node --check pagina.js`.
- [ ] **Step 2:** `python -m pytest -q` (os testes da página e da injeção continuam passando).
- [ ] **Step 3:** conferir no navegador com um servidor de teste (cópia de `~/.buildsmith/paginas/ds2/melatonina-vorcaro` em pasta temporária, `serve.make_server` em outra porta): todas as seções abrem, fogueira grava, Pesquisar enfileira, Forja aparece, desktop e 375 px.
- [ ] **Step 4:** commit `feat: página no layout v2 (menu lateral, lista + detalhe, dano em barras)`.

### Task 5: seleção de personagem e retrato na página

**Files:** Modify `skills/build-page/template/{pagina.css,pagina.js}`

**Interfaces:** Consumes as rotas da Task 2 e o `rodar` da Forja (`POST /api/<jogo>/<slug>/rodar {"modo": "plano"}`).

- Retrato do cabeçalho: foto (`/api/<jogo>/<slug>/retrato`) se houver; senão mosaico 2×2 com os ícones do equipamento (`personagem.equipado` com `sub` começando por cabeça/peito/R1/L1; sem ícone, a inicial).
- Diálogo "Selecionar personagem" (`role="dialog"`, Esc fecha, foco volta ao botão): um card por personagem de `/api/<jogo>/personagens` com retrato, nome, Nível, Soul memory; "Em uso", **Carregar** (vai para `url`) ou **Gerar plano** (roda a skill para aquele slug; a Forja mostra "Rodando para …" e, no fim, um link "Abrir página").
- No card do personagem atual: soltar uma imagem envia `POST .../retrato`; **Usar último print** (só se `print: true`) e **Usar equipamento** (`retrato-limpar`).
- Fora do servidor local (Artifact): o botão "Trocar personagem" some.

- [ ] **Step 1:** implementar; `node --check`.
- [ ] **Step 2:** navegador: lista os 2 personagens do save real (Vorcaro com página, (teste) com "Gerar plano"); upload de PNG troca o retrato; "Usar equipamento" volta ao mosaico; 375 px.
- [ ] **Step 3:** commit `feat: seleção de personagem com retrato automático (equipamento ou último print)`.

### Task 6: skills, versão e publicação da Entrega A

**Files:** Modify `skills/build/SKILL.md` (equipado inclui armadura com `sub` "cabeça"/"peito"/"mãos"/"pernas"; `--personagem` aceita o slug), `skills/build-page/SKILL.md` (fontes do template), `docs/design-system.md` (cabeçalho com retrato, menu lateral, lista + detalhe, diálogo), `.claude-plugin/plugin.json` → `0.8.0`, `README.md`.

- [ ] **Step 1:** `python -m pytest -q` → passa.
- [ ] **Step 2:** página real: `python skills/build-page/scripts/prepare_page.py ~/.buildsmith/paginas/ds2/melatonina-vorcaro/plano.json ~/.buildsmith/paginas/ds2/melatonina-vorcaro --jogo ds2`; reiniciar o servidor (`POST /api/desligar` + `pythonw app/serve.py`).
- [ ] **Step 3:** `git pull --rebase`, commit `docs: skills e design system do layout v2; 0.8.0`, `git push origin master`, `claude plugin marketplace update buildsmith && claude plugin update buildsmith@buildsmith`.

---

# Entrega B — mapa com dados do jogo

## File Structure (B)

- Create `skills/ds2-save/scripts/ds2arquivos.py`: índice BHD5 (RSA com a chave pública que vem no jogo), hash de nome, leitura no BDT (AES-ECB por trechos), DCX.
- Create `skills/ds2-save/scripts/ds2mapa.py`: leitores (MSB, params por mapa, NVG2, FMG), extração da área para o cache, `onde`, `rota`, CLI.
- Modify `skills/build-page/scripts/validate_plano.py`: `ponto` nos nós.
- Modify `skills/build-page/scripts/prepare_page.py`: rotas e cópia de `mapas/<area>.json`.
- Create `skills/build-page/template/mapa.js` (montado como o `pagina.js`).
- Modify `app/guard.py`: `ds2mapa.py` com `areas`, `extrair`, `onde`, `rota`.
- Tests: `tests/test_ds2arquivos.py`, `tests/test_ds2mapa.py`, `tests/test_validate_plano.py`, `tests/test_prepare_page.py`, `tests/test_guard.py`.

Formatos (lidos no teste de 2026-10-09 contra a Lost Bastille):
- `<Nome>KeyCode.pem` + `<Nome>Ebl.bhd`: blocos de 256 bytes; `m = c^e mod n`, saída = 255 bytes (sem o primeiro). BHD5: `"BHD5"`, `@0x10` buckets (i32) e offset (i32), `@0x18` tamanho do sal + sal ASCII; bucket = (qtd i32, offset i32); arquivo = 0x20 bytes `<Iiqqq>` (hash, tamanho, offset no BDT, sha, aes); AES em `aes`: chave 16 bytes, qtd i32, pares `<qq>` (início, fim) a decifrar com AES-128-ECB.
- Hash do nome: minúsculas, `/` na frente, `h = h*37 + ord(c)` em 32 bits. Nomes por padrão: `/map/<m>/<m>.msb`, `/map/<m>/<m>.ngp`, `/param/<tabela>_<m>.param`, `/menu/text/english/{bonfirename,mapname}.fmg`.
- Param por mapa: contagem u16 `@0x0A`, linhas de 24 bytes `<QQQ>` a partir de `0x40` (id, offset, nome); fim da última = u32 `@0x00`.
- MSB: listas a partir de `0x10` (`<ii>` versão e qtd+1, `<q>` nome, `qtd` offsets `<q>`, último = próxima lista); `PARTS_PARAM_ST`: nome `<q>` relativo `@+0`, tipo/índice/modelo `<HHH>` `@+8`, posição `<3f>` `@+0x10`; objeto: referência u32 `@+0xA0` (linha de `MapObjectInstanceParam` ou lote de `ItemLotParam2_Other`). Tipo 4 = navmesh; a posição dela é a origem das coordenadas relativas (params e NVG2).
- `MapObjectInstanceParam`: primeiro i32 da linha = ID da fogueira (bate com `bonfirename.fmg`).
- `ItemLotParam2_Other` (regulation): quantidades `@0x04` (10 bytes), IDs `@0x2C` (10 × i32, vazio ≤ 10), chances `@0x54` (10 × f32).
- NVG2: `"NVG2"`, malhas = u32 `@0x08`; `@0x20` vêm `malhas + 4` offsets `<q>`, os 4 primeiros são seções de ligação e o resto, as malhas; malha: vértices u32 `@+0x28`, faces u16 `@+0x2C`, offsets `<qqq>` `@+0x40` (vértices `<3f>`, atributos, faces de 12 bytes com 3 índices `<HHH>` no começo).
- FMG: grupos i32 `@0x0C`, textos i32 `@0x10`, tabela de offsets i32 `@0x14`; grupo (12 bytes a partir de `0x1C`) = (índice, primeiro id, último id); texto UTF-16 terminado em zero. Nome do mapa `mXX_YY_..` = id `XX*1_000_000 + YY*10_000`.

### Task 7: `ds2arquivos.py`

**Interfaces:** Produces `ds2_hash(path: str) -> int`; `Arquivo(game_dir: Path, nome: str)` (ex.: `"GameData"`) com `.ler(caminho: str) -> bytes` (decifra AES, abre DCX) e `.tem(caminho) -> bool`; `assinatura(game_dir) -> str` (tamanho+mtime dos `.bhd`, para invalidar cache); `ArquivoError`.

- [ ] **Step 1: testes que falham** (`tests/test_ds2arquivos.py`): montam um jogo falso numa pasta temporária — chave RSA 2048 de teste (`RSA.generate(2048)`), `.pem` com a pública, `.bhd` cifrado com a privada (`pow(m, d, n)` por bloco de 255 bytes, preenchido), um BDT com dois arquivos: um em claro com DCX (zlib) e um com um trecho AES. Verificam `ds2_hash("/map/m10_16_00_00/m10_16_00_00.msb")` contra o valor calculado à mão no teste, `ler()` dos dois arquivos e `ArquivoError` para nome que não existe.
- [ ] **Step 2:** rodar → falham.
- [ ] **Step 3:** implementar com o formato acima (`ds2regulation.decompress_dcx` para o DCX).
- [ ] **Step 4:** passar + teste com jogo instalado (pula sem jogo): `Arquivo(GAME, "GameData").ler("/map/m10_16_00_00/m10_16_00_00.msb")[:4] == b"MSB "`.
- [ ] **Step 5:** commit `feat: leitura dos arquivos do DS2 SotFS (índice cifrado com a chave do jogo, AES, DCX)`.

### Task 8: leitores do `ds2mapa.py`

**Interfaces:** Produces `partes_msb(data) -> list[dict(nome, tipo, pos, ref)]`; `linhas_param(data) -> list[tuple[int, bytes]]`; `malhas_nvg2(data, origem) -> list[dict(v: list[tuple3], f: list[tuple3])]`; `textos_fmg(data) -> dict[int, str]`; `nome_mapa_id(area: str) -> int`.

- [ ] **Step 1: testes que falham**: cada leitor recebe bytes montados no teste (MSB com 1 lista de 2 partes, uma navmesh tipo 4 e um objeto com ref; param com 2 linhas; NVG2 com 1 malha de 2 triângulos; FMG com 2 grupos) e confere os valores; `nome_mapa_id("m10_16_00_00") == 10160000`.
- [ ] **Step 2:** falham. **Step 3:** implementar. **Step 4:** passam.
- [ ] **Step 5:** commit `feat: leitores de mapa, params, navmesh e textos do DS2`.

### Task 9: extração da área, `areas` e `onde`

**Interfaces:**
- Produces `extrair_area(game_dir, area, cache_dir, names=None) -> dict` → grava `cache_dir/mapas/<area>.json`: `{"area", "nome", "assinatura", "origem", "malhas": [{"v": [x,y,z,…], "f": [a,b,c,…]}], "fogueiras": [{"id","nome","pos"}], "itens": [{"lote","pos","itens": [{"id","nome","qtd"}]}], "inimigos": [{"id","pos"}]}` (coordenadas absolutas, 1 casa decimal). Reaproveita o cache se a assinatura bater.
- `areas(game_dir) -> list[{"area","nome"}]` (mapas com `.msb` e `.ngp` no índice, nome do `mapname.fmg`).
- `onde(game_dir, cache_dir, item: str) -> list[{"area","nome_area","lote","pos","itens"}]` (extrai as áreas que faltam no cache).
- CLI: `ds2mapa.py areas`, `extrair --area`, `onde --item`.

- [ ] **Step 1: teste com jogo instalado** (pula sem jogo): Lost Bastille tem 7 fogueiras com nome do jogo, Straid's Cell a < 1 m de (−128.1, 27.7, 604.2), um ponto com "Petrified Dragon Bone" e "Firebomb" ×3 a < 15 m dela, e `onde(item="Fragrant Branch of Yore")` devolve ≥ 2 pontos na `m10_16_00_00`; `areas()` contém `{"area": "m10_16_00_00", "nome": "The Lost Bastille"}`.
- [ ] **Step 2:** falha. **Step 3:** implementar (`ds2regulation.load_params()["ItemLotParam2_Other"]` para os lotes, `ds2save.load_item_names()` para os nomes). **Step 4:** passa; tempo de `extrair` < 10 s por área.
- [ ] **Step 5:** commit `feat: extração de área do DS2 (chão, fogueiras, itens, inimigos) com cache e busca de item`.

### Task 10: rota pelo chão

**Interfaces:** Produces `rota(area_json: dict, de: tuple3, ate: tuple3) -> dict | None` → `{"pontos": [[x,y,z],…], "metros": float}` ou `None` sem caminho; `ponto_de(area_json, tipo, ref) -> tuple3` (`fogueira` = ID, `item` = lote, `inimigo` = id); CLI `rota --area A --de tipo:ref --ate tipo:ref`.

- [ ] **Step 1: testes que falham**: malha sintética de 4 triângulos em fila (rota passa pelos centróides, metros ≈ distância), e duas ilhas separadas → `None`; `ponto_de` com ref que não existe → `KeyError`.
- [ ] **Step 2:** falham. **Step 3:** grafo de triângulos por aresta compartilhada (coordenadas arredondadas a 0,1 m, inclusive entre malhas), Dijkstra entre o triângulo mais perto de cada ponta, caminho = ponta + centróides + ponta, metros somados. **Step 4:** passam; no jogo, Servants' Quarters → Straid's Cell dá rota (≈ 254 m).
- [ ] **Step 5:** commit `feat: rota pelo navmesh do jogo entre dois pontos`.

### Task 11: `ponto` no plano e mapas na pasta da página

**Interfaces:**
- Consumes `ds2mapa.extrair_area`, `ds2mapa.rota`, `ds2mapa.ponto_de`.
- Plano: nó pode ter `"ponto": {"area": "mXX_YY_ZZ_WW", "tipo": "fogueira"|"item"|"inimigo", "ref": int}`.
- `validate_plano`: formato de `ponto` (regex da área, tipo, `ref` inteiro positivo).
- `prepare_page.prepare(..., game_dir=None)`: para cada fonte de item e cada passo com nós de `ponto` na mesma área, grava `mapa: {"area", "rota": [[x,y,z]…] | null, "metros"}` no plano publicado e copia `mapas/<area>.json` (só as malhas perto da rota/pontos, margem 40 m) para a pasta; ponto inexistente → erro `ponto <tipo>:<ref> não existe em <area>`; sem jogo → aviso `mapa indisponível: <motivo>` e plano sem `mapa`.

- [ ] **Step 1: testes que falham**: plano com `ponto` mal formado → `validate` acusa; `prepare` com uma área falsa no cache (JSON pronto, assinatura igual) grava `mapa` com rota e copia `mapas/<area>.json`; `prepare` sem jogo → `avisos` contém "mapa indisponível" e não falha; ponto inexistente → `ValueError`.
- [ ] **Step 2:** falham. **Step 3:** implementar. **Step 4:** passam.
- [ ] **Step 5:** commit `feat: plano aponta pontos do jogo e a página recebe área e rota`.

### Task 12: `mapa.js` na página

**Interfaces:** Consumes `plano.*.mapa` e `mapas/<area>.json`. Produces `desenharMapa(slot: HTMLElement, area: object, mapa: object, passos: array)`.

- Isométrico (x−z, (x+z)/2 − y): chão em tons pela altura (só triângulos no recorte), contorno 1 px `--line`; fogueira de partida com o ícone da fogueira; passos numerados (círculo borda `--pos`, os mesmos números da lista); item = losango `--pos`; rota tracejada `--ember` com seta; recorte = caixa dos pontos + rota + 25 m; legenda curta "rota pelo chão; portas e alavancas não aparecem"; linha de áreas no topo quando os nós cobrem mais de uma área (nome do mapa).
- Sem `mapa` ou JSON que não carregou: "Mapa indisponível." (vazio no padrão do design system).
- `prefers-reduced-motion`: sem animação na rota.

- [ ] **Step 1:** implementar e montar no `index.html` (`<!--JS-->` passa a juntar `pagina.js` + `mapa.js`); `node --check`.
- [ ] **Step 2:** navegador: plano de teste com fonte "Servants' Quarters → Straid of Olaphis → Fragrant Branch of Yore" (pontos reais) mostra área recortada, rota e números iguais aos da lista; 375 px.
- [ ] **Step 3:** commit `feat: mapa isométrico da área em Onde pegar e Passos`.

### Task 13: skills, guarda, docs e publicação da Entrega B

**Files:** `app/guard.py` (+ `skills/ds2-save/scripts/ds2mapa.py`: `areas`, `extrair`, `onde`, `rota`) e `tests/test_guard.py`; `skills/build/SKILL.md` (para cada nó de item/fogueira/NPC do plano: `ds2mapa.py onde --item` ou o ID da fogueira → `ponto`; a ordem dos passos vem da wiki; sem ponto confirmado, sem `ponto`); `skills/ds2-save/SKILL.md` (comandos novos); `skills/build-page/SKILL.md` (mapa); `docs/design-system.md` (componente Mapa); `.claude-plugin/plugin.json` → `0.9.0`; apagar `design_novo/_spike_mapa*.html`.

- [ ] **Step 1:** teste do guarda: `ds2mapa.py rota --area m10_16_00_00 --de fogueira:16675 --ate item:10165010` permitido; `ds2mapa.py apagar` negado.
- [ ] **Step 2:** `python -m pytest -q` → passa.
- [ ] **Step 3:** página real com `ponto` no passo "Libertar o Straid" (Servants' Quarters → Straid of Olaphis) para conferir no navegador.
- [ ] **Step 4:** `git pull --rebase`, commit `docs: mapa nas skills, guarda e design system; 0.9.0`, push na `master`, atualizar o plugin.
