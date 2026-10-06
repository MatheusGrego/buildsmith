#!/usr/bin/env python3
"""Confere se o plano.json tem tudo que a página precisa antes de publicar."""
import json
import sys

STATS = ["VGR", "END", "VIT", "ATN", "STR", "DEX", "INT", "FTH", "ADP"]
TIPOS = {"nivel", "item", "chefe", "compra", "equipar"}
TOP = {"gerado_em": str, "jogo": str, "objetivo": str, "personagem": dict, "alvo_stats": dict,
       "mudancas": list, "passos": list, "fases": list, "itens": list, "comparacao": list, "fontes": list}


def validate(plano: dict) -> list[str]:
    problems = []
    for key, kind in TOP.items():
        if key not in plano:
            problems.append(f"falta '{key}'")
        elif not isinstance(plano[key], kind):
            problems.append(f"'{key}' deveria ser {kind.__name__}")
    if problems:
        return problems
    person = plano["personagem"]
    for key in ("name", "level", "souls", "soul_memory", "stats", "equipado"):
        if key not in person:
            problems.append(f"falta 'personagem.{key}'")
    for where, stats in (("personagem.stats", person.get("stats", {})), ("alvo_stats", plano["alvo_stats"])):
        for stat in STATS:
            if not isinstance(stats.get(stat), int):
                problems.append(f"'{where}.{stat}' deveria ser número inteiro")
    for i, step in enumerate(plano["passos"]):
        if not step.get("titulo"):
            problems.append(f"passos[{i}] sem 'titulo'")
        if step.get("tipo") not in TIPOS:
            problems.append(f"passos[{i}].tipo deveria ser um de {sorted(TIPOS)}")
    for i, phase in enumerate(plano["fases"]):
        for key in ("de", "ate", "almas"):
            if not isinstance(phase.get(key), int):
                problems.append(f"fases[{i}].{key} deveria ser número inteiro")
    for i, item in enumerate(plano["itens"]):
        for key in ("nome", "onde"):
            if not item.get(key):
                problems.append(f"itens[{i}] sem '{key}'")
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
