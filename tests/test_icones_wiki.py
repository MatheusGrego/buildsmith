import icones_wiki

PAGINA = """<html><body><img src="https://static0.fextralifeimages.com/file/darksouls2/logo.png">
<div id="infobox" class="infobox"><table class="wikitable"><tr><th><h2>Fragrant Branch of Yore</h2></th></tr>
<tr><td><a href="/File:Fragrant_branch_of_yore.png"><img alt="Fragrant Branch of Yore"
src="https://static0.fextralifeimages.com/file/darksouls2/a/a5/Fragrant_branch_of_yore.png" width="64"></a></td></tr>
</table></div></body></html>"""


class FakeFetch:
    def __init__(self, paginas):
        self.paginas = paginas
        self.chamadas = []

    def __call__(self, url):
        self.chamadas.append(url)
        if url not in self.paginas:
            raise OSError("404")
        return self.paginas[url].encode("utf-8")


def test_page_url_uses_underscores():
    assert icones_wiki.pagina_item("Fragrant Branch of Yore") == "https://darksouls2.wiki.fextralife.com/Fragrant_Branch_of_Yore"
    assert icones_wiki.pagina_item("Sorcerer's Staff") == "https://darksouls2.wiki.fextralife.com/Sorcerer's_Staff"


def test_icon_comes_from_the_infobox_only():
    assert icones_wiki.icone_da_pagina(PAGINA) == "https://static0.fextralifeimages.com/file/darksouls2/a/a5/Fragrant_branch_of_yore.png"
    assert icones_wiki.icone_da_pagina("<html><img src='https://static0.fextralifeimages.com/x.png'></html>") is None
    fora = PAGINA.replace("https://static0.fextralifeimages.com", "https://evil.example")
    assert icones_wiki.icone_da_pagina(fora) is None


def test_cache_avoids_second_request_and_remembers_misses(tmp_path):
    fetch = FakeFetch({icones_wiki.pagina_item("Fragrant Branch of Yore"): PAGINA})
    icones = icones_wiki.IconesWiki(tmp_path / "icones.json", fetch)
    assert icones.url("Fragrant Branch of Yore").endswith("Fragrant_branch_of_yore.png")
    assert icones.url("Item Inventado") is None
    de_novo = icones_wiki.IconesWiki(tmp_path / "icones.json", fetch)
    assert de_novo.url("Fragrant Branch of Yore").endswith("Fragrant_branch_of_yore.png")
    assert de_novo.url("Item Inventado") is None
    assert len(fetch.chamadas) == 2
