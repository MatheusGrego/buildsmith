#!/usr/bin/env python3
"""Confere se o plano.json (versão 2) tem tudo que a página precisa antes de publicar."""
import json
import sys

STATS = ["VGR", "END", "VIT", "ATN", "STR", "DEX", "INT", "FTH", "ADP"]
TIPOS_PASSO = {"nivel", "item", "chefe", "compra", "equipar"}
TIPOS_NO = {"item", "chefe", "inimigo", "npc", "local", "bau", "almas", "atributo"}
SINAIS = {"+", "-", ""}
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
        _flow(f"itens[{i}].onde", item.get("onde"), problems)
        _rows(f"itens[{i}].dados", item.get("dados", []), problems)
    for i, build in enumerate(plano["comparacao"]):
        if not build.get("build"):
            problems.append(f"comparacao[{i}] sem 'build'")
        _rows(f"comparacao[{i}].dados", build.get("dados", []), problems)
        _flow(f"comparacao[{i}].ajuste", build.get("ajuste", []), problems)
    return problems


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
