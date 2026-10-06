# buildsmith

Conjunto de skills do Claude Code para planejar builds de jogos a partir do save do jogador.

Primeiro jogo suportado: Dark Souls II: Scholar of the First Sin.

## Instalar

```bash
pip install pycryptodome
claude plugin marketplace add C:/Users/Matheus/Dev/Projects/buildsmith
claude plugin install buildsmith@buildsmith
```

## Usar

No Claude Code: `/buildsmith:build ds2` ou `/buildsmith:build ds2 quero focar piromancia`.

Seus dados (perfil, histórico, cache da wiki, link da página) ficam em `~/.buildsmith/`, fora do repositório.

## Testes

```bash
pip install pytest pycryptodome
python -m pytest -q
```

Listas de IDs do DS2: [DS2S-META](https://github.com/Nordgaren/DS2S-META) (MIT).
