#!/usr/bin/env python3
"""Confere se o plano.json (versão 2) tem tudo que a página precisa antes de publicar."""
import json
import sys

STATS = ["VGR", "END", "VIT", "ATN", "STR", "DEX", "INT", "FTH", "ADP"]
# Ordem dos grupos na aba Passos.
GRUPOS = ["equipar", "explorar", "chefe", "troca", "compra", "upgrade", "farm", "nivel"]
TIPOS_PASSO = set(GRUPOS)
TIPOS_FONTE = {"compra", "troca", "drop", "bau", "farm", "recompensa"}
ACESSOS = ["agora", "em_breve", "tarde"]
DESTAQUES = {"mais_cedo", "mais_rentavel"}
TIPOS_NO = {"item", "chefe", "inimigo", "npc", "local", "bau", "almas", "atributo"}
SINAIS = {"+", "-", ""}
ESTADOS_CHEFE = {"derrotado", "vivo"}
ESTADOS_EVENTO = {"feito", "pendente"}
TOP = {"versao": int, "gerado_em": str, "jogo": str, "objetivo": str, "personagem": dict, "alvo_stats": dict,
       "mudancas": list, "passos": list, "fases": list, "itens": list, "comparacao": list, "fontes": list}


def _node(where: str, node, problems: list) -> None:
    if not isinstance(node, dict):
        problems.append(f"{where} deveria ser um nó")
        return
    if node.get("tipo") not in TIPOS_NO:
        problems.append(f"{where}.tipo deveria ser um de {sorted(TIPOS_NO)}")
    if not node.get("nome"):
        problems.append(f"{where} sem 'nome'")
    if len(node.get("sub") or "") > 30:
        problems.append(f"{where}.sub passa de 30 caracteres")


def _flow(where: str, flow, problems: list) -> None:
    if not isinstance(flow, list):
        problems.append(f"{where} deveria ser lista de nós")
        return
    for i, node in enumerate(flow):
        _node(f"{where}[{i}]", node, problems)


def _rows(where: str, rows, problems: list) -> None:
    if not isinstance(rows, list):
        problems.append(f"{where} deveria ser lista de linhas")
        return
    for i, row in enumerate(rows):
        if not row.get("dado"):
            problems.append(f"{where}[{i}] sem 'dado'")
        if row.get("sinal", "") not in SINAIS:
            problems.append(f"{where}[{i}].sinal deveria ser '+', '-' ou ''")


def validate(plano: dict) -> list[str]:
    problems = []
    for key, kind in TOP.items():
        if key not in plano:
            problems.append(f"falta '{key}'")
        elif not isinstance(plano[key], kind):
            problems.append(f"'{key}' deveria ser {kind.__name__}")
    if problems:
        return problems
    if plano["versao"] != 2:
        problems.append("versao deveria ser 2")
    person = plano["personagem"]
    for key in ("name", "level", "souls", "soul_memory", "stats", "equipado"):
        if key not in person:
            problems.append(f"falta 'personagem.{key}'")
    _flow("personagem.equipado", person.get("equipado", []), problems)
    for where, stats in (("personagem.stats", person.get("stats", {})), ("alvo_stats", plano["alvo_stats"])):
        for stat in STATS:
            if not isinstance(stats.get(stat), int):
                problems.append(f"'{where}.{stat}' deveria ser número inteiro")
    _rows("mudancas", plano["mudancas"], problems)
    for i, step in enumerate(plano["passos"]):
        if not step.get("titulo"):
            problems.append(f"passos[{i}] sem 'titulo'")
        elif len(step["titulo"]) > 40:
            problems.append(f"passos[{i}].titulo passa de 40 caracteres")
        if step.get("tipo") not in TIPOS_PASSO:
            problems.append(f"passos[{i}].tipo deveria ser um de {sorted(TIPOS_PASSO)}")
        _flow(f"passos[{i}].fluxo", step.get("fluxo"), problems)
        _rows(f"passos[{i}].dados", step.get("dados", []), problems)
    for i, phase in enumerate(plano["fases"]):
        for key in ("de", "ate", "almas"):
            if not isinstance(phase.get(key), int):
                problems.append(f"fases[{i}].{key} deveria ser número inteiro")
        if phase.get("atributo") not in STATS:
            problems.append(f"fases[{i}].atributo deveria ser um de {STATS}")
    for i, item in enumerate(plano["itens"]):
        _node(f"itens[{i}].item", item.get("item"), problems)
        _sources(f"itens[{i}]", item.get("fontes"), problems)
        _rows(f"itens[{i}].dados", item.get("dados", []), problems)
    for i, build in enumerate(plano["comparacao"]):
        if not build.get("build"):
            problems.append(f"comparacao[{i}] sem 'build'")
        _rows(f"comparacao[{i}].dados", build.get("dados", []), problems)
        _flow(f"comparacao[{i}].ajuste", build.get("ajuste", []), problems)
    if "progresso" in plano:
        _progress(plano["progresso"], problems)
    if "dano" in plano:
        _damage(plano["dano"], problems)
    if not problems:
        _closure(plano, problems)
    return problems


def _sources(where: str, sources, problems: list) -> None:
    if not isinstance(sources, list) or not sources:
        problems.append(f"{where}.fontes deveria ser lista com pelo menos uma fonte")
        return
    earliest = 0
    for j, src in enumerate(sources):
        at = f"{where}.fontes[{j}]"
        if src.get("tipo") not in TIPOS_FONTE:
            problems.append(f"{at}.tipo deveria ser um de {sorted(TIPOS_FONTE)}")
        if src.get("acesso") not in ACESSOS:
            problems.append(f"{at}.acesso deveria ser um de {ACESSOS}")
        _flow(f"{at}.fluxo", src.get("fluxo"), problems)
        if not src.get("fluxo"):
            problems.append(f"{at}.fluxo vazio")
        marks = src.get("destaques", [])
        if not set(marks) <= DESTAQUES:
            problems.append(f"{at}.destaques deveria usar só {sorted(DESTAQUES)}")
        earliest += "mais_cedo" in marks
    if earliest != 1:
        problems.append(f"{where} precisa de exatamente uma fonte com destaque 'mais_cedo' (tem {earliest})")
    if sum("mais_rentavel" in s.get("destaques", []) for s in sources) > 1:
        problems.append(f"{where} tem mais de uma fonte 'mais_rentavel'")
    ranks = [ACESSOS.index(s["acesso"]) for s in sources if s.get("acesso") in ACESSOS]
    if ranks != sorted(ranks):
        problems.append(f"{where}.fontes fora de ordem: agora → em_breve → tarde")


def _cited_items(plano: dict):
    for step in plano["passos"]:
        yield from step.get("fluxo", [])
    for row in plano.get("dano", []):
        yield row["arma"]
        yield from row.get("por_causa", [])
    for build in plano["comparacao"]:
        yield from build.get("ajuste", [])


def _closure(plano: dict, problems: list) -> None:
    """Todo item citado precisa de 'Onde pegar', salvo os que o jogador já tem."""
    known = {item["item"]["nome"] for item in plano["itens"]}
    missing = sorted({n["nome"] for n in _cited_items(plano)
                      if n.get("tipo") == "item" and not n.get("tem") and n["nome"] not in known})
    for name in missing:
        problems.append(f"'{name}' é citado no plano mas não tem fonte em 'itens' (ou marque \"tem\": true)")


def _progress(prog, problems: list) -> None:
    if not isinstance(prog, dict):
        problems.append("'progresso' deveria ser dict")
        return
    for i, boss in enumerate(prog.get("chefes", [])):
        _node(f"progresso.chefes[{i}].no", boss.get("no"), problems)
        if boss.get("estado") not in ESTADOS_CHEFE:
            problems.append(f"progresso.chefes[{i}].estado deveria ser um de {sorted(ESTADOS_CHEFE)}")
    for i, buy in enumerate(prog.get("compras", [])):
        _node(f"progresso.compras[{i}].loja", buy.get("loja"), problems)
        _node(f"progresso.compras[{i}].item", buy.get("item"), problems)
        if not isinstance(buy.get("qtd"), int):
            problems.append(f"progresso.compras[{i}].qtd deveria ser número inteiro")
    for i, event in enumerate(prog.get("eventos", [])):
        if not event.get("nome"):
            problems.append(f"progresso.eventos[{i}] sem 'nome'")
        if event.get("estado") not in ESTADOS_EVENTO:
            problems.append(f"progresso.eventos[{i}].estado deveria ser um de {sorted(ESTADOS_EVENTO)}")


def _damage(rows, problems: list) -> None:
    if not isinstance(rows, list):
        problems.append("'dano' deveria ser lista")
        return
    for i, row in enumerate(rows):
        _node(f"dano[{i}].arma", row.get("arma"), problems)
        for key in ("agora", "depois"):
            value = row.get(key)
            if not (isinstance(value, int) or value == "—"):
                problems.append(f"dano[{i}].{key} deveria ser número inteiro ou '—'")
        _flow(f"dano[{i}].por_causa", row.get("por_causa", []), problems)


def main(argv=None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    argv = argv if argv is not None else sys.argv[1:]
    with open(argv[0], encoding="utf-8") as fh:
        problems = validate(json.load(fh))
    for problem in problems:
        print(problem)
    print("ok" if not problems else f"{len(problems)} problema(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
