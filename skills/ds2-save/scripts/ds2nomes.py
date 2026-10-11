#!/usr/bin/env python3
"""Nomes de inimigos e objetos do DS2 SotFS pela linha/modelo do próprio jogo.

O jogo não guarda nome de inimigo comum nem de objeto de mapa. A comunidade de modding deu nome às linhas e aos
modelos (games/ds2/nomes_smithbox.json, do Smithbox, MIT). Este módulo liga o que o jogo diz ao nome:

- inimigo: a linha do EnemyParam (o `tipo` do gerador) tem nome, ex. 318030 = "The Pursuer - Lost Bastille";
  sem nome na linha, o modelo dá o nome base: a linha // 100 é o modelo cXXXX (102000 -> c1020 Hollow Soldier,
  318030 -> c3180 The Pursuer; conferido em 624 linhas com nome nas duas tabelas).
- objeto: o modelo do MSB (oXX_XXXX) tem nome ("o00_0300" = "Wooden Door"); a categoria (porta, alavanca, baú...)
  sai do nome do modelo ou, sem nome, do tipo da instância (MapObjectInstanceTypeParam, cujas linhas o jogo nomeia
  em japonês: 120 = 木製宝箱 "baú de madeira", 210 = 片扉 "porta simples", 170 = レバー "alavanca").
- porta com chave: o nome do modelo às vezes diz a chave ("Large Stone Door (Forgotten Key)"); a chave só vale se
  existir com esse nome entre os itens do jogo.
"""
import json
import re
from functools import lru_cache
from pathlib import Path

ARQUIVO = Path(__file__).resolve().parents[3] / "games" / "ds2" / "nomes_smithbox.json"

# categoria do objeto pelo nome do modelo (a ordem importa: "Fog Gate" é névoa, "Lever Door" é porta)
CATEGORIAS = (
    ("nevoa", re.compile(r"\bfog (gate|wall)\b", re.I)),
    ("pharros", re.compile(r"\bpharros", re.I)),
    ("elevador", re.compile(r"\belevator\b|\blift\b", re.I)),
    ("porta", re.compile(r"\bdoors?\b|\bgate\b|\bbars\b|\bportcullis\b", re.I)),
    ("alavanca", re.compile(r"\blever\b|\bswitch\b|\bvalve\b", re.I)),
    ("ponte", re.compile(r"\bbridge\b", re.I)),
    ("escada", re.compile(r"\bladder\b", re.I)),
    ("bau", re.compile(r"\bchest\b", re.I)),
    ("cadaver", re.compile(r"\bcorpse\b", re.I)),
)
IGNORAR = re.compile(r"^(dummy|after destroying)\b|fireball", re.I)  # peças auxiliares de evento
# tipo da instância (MapObjectInstanceTypeParam) -> categoria, para objeto sem nome de modelo
TIPO_INSTANCIA = {110: "nevoa", 120: "bau", 121: "bau", 122: "bau", 123: "bau", 130: "cadaver", 131: "cadaver",
                  150: "escada", 195: "escada", 170: "alavanca", 180: "alavanca", 190: "alavanca",
                  200: "porta", 210: "porta", 211: "porta", 220: "porta", 225: "porta", 230: "porta", 231: "porta",
                  235: "porta", 240: "porta", 365: "porta", 380: "porta", 381: "porta", 490: "porta",
                  320: "ponte", 540: "ponte"}
CHAVE_NO_NOME = (re.compile(r"\(([^()]*\bKey\b[^()]*)\)"), re.compile(r"\b(House Key|King's Ring)\b(?= Door)"))


@lru_cache(maxsize=4)
def _tabelas(caminho: str = str(ARQUIVO)) -> dict:
    return json.loads(Path(caminho).read_text(encoding="utf-8"))


def partes_nome(texto: str) -> dict:
    """"Rupturing Hollow (Red Core) - Lost Bastille" -> base, variante e local (o " - " fora dos parênteses)."""
    nivel, corte = 0, None
    for i, c in enumerate(texto):
        nivel += (c == "(") - (c == ")")
        if nivel == 0 and texto.startswith(" - ", i):
            corte = i
            break
    nome, local = (texto[:corte], texto[corte + 3:]) if corte is not None else (texto, "")
    m = re.match(r"^(.*?)\s*\((.*)\)\s*$", nome)
    base, variante = (m.group(1), m.group(2)) if m else (nome, "")
    return {"base": base.strip(), "variante": variante.strip(), "local": local.strip()}


def nome_inimigo(tipo, tabelas: dict | None = None) -> dict | None:
    """{nome, base, fonte, prova} do tipo de inimigo (linha do EnemyParam); None sem nome nas tabelas."""
    t = tabelas or _tabelas()
    try:
        linha = int(tipo)
    except (TypeError, ValueError):
        return None
    texto = t["inimigos"].get(str(linha))
    if texto:
        p = partes_nome(texto)
        nome = f"{p['base']} ({p['variante']})" if p["variante"] and not p["variante"].startswith("Boss") else p["base"]
        return {"nome": nome, "base": p["base"], "fonte": "jogo",
                "prova": f"linha {linha} do EnemyParam do jogo: “{texto}” (nome da comunidade, Smithbox/Paramdex)"}
    modelo = f"c{linha // 100:04d}"
    texto = t["personagens"].get(modelo)
    if texto:
        return {"nome": texto, "base": texto, "fonte": "modelo",
                "prova": f"modelo {modelo} do jogo (linha {linha} do EnemyParam // 100): “{texto}” (Smithbox)"}
    return None


def categoria(nome_modelo: str | None, tipo_instancia: int | None = None) -> str | None:
    if nome_modelo:
        if IGNORAR.search(nome_modelo):
            return None
        for cat, rx in CATEGORIAS:
            if rx.search(nome_modelo):
                return cat
    return TIPO_INSTANCIA.get(tipo_instancia)


def chave_do_nome(nome_modelo: str | None, itens: dict[int, str]) -> tuple[int, str] | None:
    """(id, nome) da chave que o nome do modelo cita, se ela existir entre os itens do jogo ("Den Key" acha
    "Tseldora Den Key")."""
    if not nome_modelo:
        return None
    for rx in CHAVE_NO_NOME:
        m = rx.search(nome_modelo)
        if not m:
            continue
        alvo = m.group(1).strip().casefold()
        exatos = [(i, n) for i, n in itens.items() if n.casefold() == alvo]
        fim = [(i, n) for i, n in itens.items() if n.casefold().endswith(" " + alvo)]
        achados = exatos or fim
        if len(achados) == 1 or (achados and len({n for _, n in achados}) == 1):
            return min(achados)
    return None


def objeto(modelo: str, tipo_instancia: int | None, itens: dict[int, str], tabelas: dict | None = None) -> dict | None:
    """{cat, nome, chave} de um objeto do MSB; None se não é de nenhuma categoria do mapa."""
    t = tabelas or _tabelas()
    nome = t["objetos"].get((modelo or "").lower())
    cat = categoria(nome, tipo_instancia)
    if not cat:
        return None
    chave = chave_do_nome(nome, itens) if cat == "porta" else None
    return {"cat": cat, "nome": nome or "", "chave": list(chave) if chave else None}


# fora do cenário 3D: ajudantes invisíveis (efeito, colisão) e a lápide de NPC, que o jogo só mostra quando o NPC morre
FORA_DA_CENA = re.compile(r"^dummy\b|\bdummy for\b|^tombstone$", re.I)


def fora_da_cena(modelo: str, tabelas: dict | None = None) -> str | None:
    """Motivo para o objeto não entrar no cenário (None = entra)."""
    nome = (tabelas or _tabelas())["objetos"].get((modelo or "").lower(), "")
    return "objeto que o jogo só mostra em evento ou nunca desenha" if nome and FORA_DA_CENA.search(nome) else None
