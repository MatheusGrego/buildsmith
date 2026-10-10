import escala_wiki

UCHI = """<div id="mw-content-text"><table><tr><th>Name</th><th>Attack Values</th></tr>
<tr><td>Regular</td><td>115</td><td>-</td><td>-</td><td>-</td><td>-</td><td>150 20</td><td>E</td><td>B</td><td>-</td><td>-</td><td>-</td><td>-</td><td>-</td><td>45.0</td></tr>
<tr><td>Regular +5</td><td>172</td><td>-</td><td>-</td><td>-</td><td>-</td><td>^</td><td>E</td><td>B</td><td>-</td><td>-</td><td>-</td><td>-</td><td>-</td><td>45.0</td></tr>
<tr><td>Regular +10</td><td>230</td><td>-</td><td>-</td><td>-</td><td>-</td><td>^</td><td>E</td><td>A</td><td>-</td><td>-</td><td>-</td><td>-</td><td>-</td><td>45.0</td></tr>
<tr><td>Fire +10</td><td>161</td><td>-</td><td>161</td><td>-</td><td>-</td><td>^</td><td>E</td><td>B</td><td>-</td><td>B</td><td>-</td><td>-</td><td>-</td><td>42.9</td></tr>
</table></div>"""

FLAME = """<div id="mw-content-text"><table>
<tr><td>Pyromancy Flame</td><td>0</td><td>0</td><td>125</td><td>0</td><td>0</td><td>100 5</td><td>-</td><td>-</td><td>-</td><td>A</td><td>-</td><td>-</td><td>-</td><td>-</td></tr>
<tr><td>Pyromancy Flame +5</td><td>0</td><td>0</td><td>187</td><td>0</td><td>0</td><td>100 5</td><td>-</td><td>-</td><td>-</td><td>S</td><td>-</td><td>-</td><td>-</td><td>-</td></tr>
</table></div>"""

STAFF = """<div id="mw-content-text"><table>
<tr><td>Lizard Staff</td><td></td><td>110</td><td>-</td><td>-</td><td>40</td><td>100/10</td><td></td><td></td><td>A</td><td>-</td><td>-</td><td>C</td><td>-</td><td>-</td></tr>
<tr><td>Dark +10</td><td>-</td><td>186</td><td>-</td><td>-</td><td>230</td><td>^</td><td>-</td><td>-</td><td>S</td><td>-</td><td>-</td><td>B</td><td>-</td><td>-</td></tr>
</table></div>"""


def test_letters_by_level_skip_infusions():
    assert escala_wiki.letras_da_pagina(UCHI, "Uchigatana") == {"0": {"STR": "E", "DEX": "B"}, "5": {"STR": "E", "DEX": "B"},
                                                                 "10": {"STR": "E", "DEX": "A"}}
    assert escala_wiki.letras_da_pagina(FLAME, "Pyromancy Flame") == {"0": {"fogo": "A"}, "5": {"fogo": "S"}}
    assert escala_wiki.letras_da_pagina(STAFF, "Lizard Staff") == {"0": {"magico": "A", "sombrio": "C"}}  # infusão Dark fica de fora


class Fetch:
    def __init__(self):
        self.chamadas = []

    def __call__(self, url):
        self.chamadas.append(url)
        paginas = {"Pyromancy_Flame": FLAME, "Uchigatana": UCHI}
        nome = url.rsplit("/", 1)[-1]
        if nome not in paginas:
            raise OSError("404")
        return paginas[nome].encode()


def test_level_without_row_uses_the_closest_below_and_cache(tmp_path):
    fetch = Fetch()
    e = escala_wiki.EscalaWiki(tmp_path / "escala.json", fetch)
    r = e.letras("Pyromancy Flame", 2)
    assert r["letras"] == {"fogo": "A"} and r["nivel"] == 0 and r["fonte"].endswith("/Pyromancy_Flame")
    assert e.letras("Pyromancy Flame", 7)["letras"] == {"fogo": "S"}
    assert e.letras("Item Sem Tabela", 0) is None
    n = len(fetch.chamadas)
    de_novo = escala_wiki.EscalaWiki(tmp_path / "escala.json", fetch)
    assert de_novo.letras("Uchigatana", 5)["letras"] == {"STR": "E", "DEX": "B"} and len(fetch.chamadas) == n + 1
    assert de_novo.letras("Item Sem Tabela", 0) is None and len(fetch.chamadas) == n + 1  # falta também fica no cache
