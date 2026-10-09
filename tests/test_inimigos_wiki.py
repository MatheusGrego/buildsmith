import inimigos_wiki

LISTA = """<div id="tabber-All_Enemies_by_Name"><a href="/Royal_Swordsman" title="Royal Swordsman">Royal Swordsman</a>
<a href="/Gaoler" title="Gaoler">Gaoler</a><a href="/Hollow_Varangian" title="Hollow Varangian">x</a></div>
<div id="tabber-Enemies_by_Location"><a href="/Majula" title="Majula">Majula</a></div>"""

ROYAL = """<div id="mw-content-text"><h3 id="Drops">Drops</h3><ul><li><a href="/Royal_Swordsman_Set" title="Royal Swordsman Set">x</a></li>
<li><a href="/Royal_Greatsword" title="Royal Greatsword">x</a></li><li>NG: 180 Souls,NG+ 360 Souls, NG+7: 1,440 Souls.</li></ul></div>
<div class="printfooter"><a href="/Alluring_Skull" title="Alluring Skull">rodapé</a></div>"""

AREA = """<h3 class="special" id="Enemies">Enemies</h3><ul><li><a href="/Royal_Swordsman" title="Royal Swordsman">x</a></li>
<li><a href="/Undead_Jailer" title="Undead Jailer">x</a></li></ul><h3 id="Drops">Drops</h3><ul><li><a href="/Lifegem" title="Lifegem">x</a></li></ul>"""


def paginas():
    return {
        "Royal Swordsman": {"url": "https://w/Royal_Swordsman", **inimigos_wiki.dados_pagina(ROYAL)},
        "Gaoler": {"url": "https://w/Gaoler", "almas": [1100], "links": ["Great Machete", "Twilight Herb", "Lingering Flame"]},
        "Desert Sorceress": {"url": "https://w/DS", "almas": [300], "links": ["Desert Sorceress Hood"]},
        "Hollow Varangian": {"url": "https://w/HV", "almas": [200], "links": ["Varangian Set", "Royal Greatsword"]},
    }


def test_enemy_list_comes_from_the_by_name_tab():
    assert inimigos_wiki.lista_inimigos(LISTA) == [("Royal Swordsman", inimigos_wiki.WIKI + "Royal_Swordsman"),
                                                   ("Gaoler", inimigos_wiki.WIKI + "Gaoler"),
                                                   ("Hollow Varangian", inimigos_wiki.WIKI + "Hollow_Varangian")]


def test_page_data_reads_souls_and_content_links_only():
    d = inimigos_wiki.dados_pagina(ROYAL)
    assert d["almas"] == [180]  # só NG: o EnemyParam guarda o valor base
    assert "Royal Greatsword" in d["links"] and "Alluring Skull" not in d["links"]  # rodapé fica de fora


def test_area_enemies_stop_at_the_list():
    assert inimigos_wiki.inimigos_da_area(AREA) == ["Royal Swordsman", "Undead Jailer"]
    assert inimigos_wiki.inimigos_da_area("<p>sem lista</p>") == []


def test_name_needs_drops_and_souls_or_area():
    royal = {"almas": 180, "drops": ["Royal Swordsman Helm", "Royal Greatsword", "Lifegem"]}
    r = inimigos_wiki.nomear(royal, paginas(), {"Royal Swordsman"})
    assert r["nome"] == "Royal Swordsman" and "almas: 180" in r["prova"] and "Royal Swordsman Helm" in r["prova"]
    gaoler = {"almas": 540, "drops": ["Great Machete", "Twilight Herb", "Lingering Flame"]}  # almas da wiki diferentes
    assert inimigos_wiki.nomear(gaoler, paginas(), set())["nome"] == "Gaoler"


def test_souls_alone_or_a_generic_lot_are_not_enough():
    assert inimigos_wiki.nomear({"almas": 300, "drops": []}, paginas(), set()) is None
    generico = {"almas": 0, "drops": ["Royal Greatsword", "Hollow Soldier Helm", "Heide Knight Chainmail", "Zweihander"]}
    pags = paginas()
    for n, item in (("A", "Hollow Soldier Helm"), ("B", "Heide Knight Chainmail"), ("C", "Zweihander")):
        pags[n] = {"url": n, "almas": [], "links": [item]}
    assert inimigos_wiki.nomear(generico, pags, {"Royal Swordsman"}) is None


def test_tie_has_no_name():
    tipo = {"almas": 0, "drops": ["Royal Greatsword"]}
    assert inimigos_wiki.nomear(tipo, paginas(), {"Royal Swordsman", "Hollow Varangian"}) is None


def test_variants_of_the_same_model_share_the_name():
    nomes = {"125010": {"nome": "Rupturing Hollow", "wiki": "w", "prova": "drops: Flame Butterfly"}}
    out = inimigos_wiki.por_familia(nomes, ["125010", "125011", "152002"])
    assert out["125011"]["nome"] == "Rupturing Hollow" and "125010" in out["125011"]["prova"]
    assert "152002" not in out


class Fetch:
    def __init__(self):
        self.chamadas = []

    def __call__(self, url):
        self.chamadas.append(url)
        paginas = {inimigos_wiki.LISTA: LISTA, inimigos_wiki.WIKI + "Royal_Swordsman": ROYAL,
                   inimigos_wiki.WIKI + "Lost_Bastille": AREA}
        if url not in paginas:
            raise OSError("404")
        return paginas[url].encode()


def test_cache_keeps_pages_for_the_next_build(tmp_path):
    fetch = Fetch()
    tipos = {"152002": {"almas": 180, "drops": ["Royal Swordsman Helm", "Royal Greatsword"]}, "1": {"almas": 5, "drops": []}}
    w = inimigos_wiki.InimigosWiki(tmp_path / "i.json", fetch)
    assert list(w.nomes(tipos, "The Lost Bastille")) == ["152002"]
    n = len(fetch.chamadas)
    de_novo = inimigos_wiki.InimigosWiki(tmp_path / "i.json", fetch)
    assert de_novo.nomes(tipos, "The Lost Bastille")["152002"]["nome"] == "Royal Swordsman"
    assert len(fetch.chamadas) == n


def test_wiki_down_gives_no_names(tmp_path):
    def fora(url):
        raise OSError("sem rede")
    assert inimigos_wiki.InimigosWiki(tmp_path / "i.json", fora).nomes({"1": {"almas": 1, "drops": []}}, "X") == {}
