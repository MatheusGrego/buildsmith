# buildsmith — design

Data: 2026-10-06
Status: aprovado em conversa, aguardando revisão do documento

## Objetivo

Plugin do Claude Code (conjunto de skills) que lê o save do jogador, entende a build atual e gera um plano de evolução numa página fixa. Arquitetura genérica por jogo; primeira e única implementação: **Dark Souls II: Scholar of the First Sin (PC)**.

O plano responde:
- quantas almas custa cada próxima etapa de nível;
- onde pegar cada item que falta (pedras, anéis, catalisadores, magias, piromancias, armaduras);
- como a build se compara com builds de outros players, sugerindo **ajustes** sem migrar a build inteira.

## Decisões

| Tema | Decisão |
|---|---|
| Forma | Plugin do Claude Code com skills; código só onde raciocínio não resolve (ler save binário) |
| Linguagem do código | Python 3 (script dentro da skill), dependência única: `pycryptodome` |
| Fonte de dados | Híbrida: IDs e custos de nível locais; locais de item e builds via wiki com cache |
| Saída | Uma página (Artifact) com link fixo, republicada a cada `/build` |
| Objetivo da build | Perfil salvo por personagem, editável conversando |
| Qual save | O mais recente entre `.co2` (Seamless Co-op) e `.sl2`, sempre lido a partir de cópia |
| Qual personagem | Único slot ocupado; se houver mais de um, pergunta 1 vez e grava no perfil |
| Dados do jogador | Fora do repositório, em `~/.buildsmith/` |

## Estrutura do repositório

```
buildsmith/
  .claude-plugin/plugin.json
  skills/
    build/SKILL.md            # orquestrador: /build <jogo> [pedido]
    ds2-save/
      SKILL.md                # como chamar o leitor e interpretar o JSON
      scripts/ds2save.py      # leitor do save + custos de nível
    wiki-cache/SKILL.md       # busca na wiki com cache de 30 dias
    build-page/
      SKILL.md                # como gerar plano.json e publicar
      template/index.html     # visual fixo; lê plano.json
  games/ds2/
    level_costs.json          # custo para alcançar cada nível
    ids/*.txt                 # listas de IDs (DS2S-META, MIT) + LICENSE-DS2S-META
  tests/
    test_ds2save.py
    fixtures/                 # save sintético gerado pelos testes, nunca um save real
  docs/superpowers/specs/
```

Dados do jogador (fora do repo):

```
~/.buildsmith/
  config.json                 # caminho do save, slot escolhido, URL da página
  profiles/ds2/<personagem>.yaml
  history/ds2/<personagem>/<timestamp>.json
  cache/ds2/<assunto>.md      # cópia resumida da wiki, com data e URL de origem
```

Adicionar outro jogo = nova skill `skills/<jogo>-save/` + pasta `games/<jogo>/`. As skills `build`, `wiki-cache` e `build-page` não mudam.

## Leitor do save DS2 (`ds2save.py`)

### Formato (descoberto e validado em 2026-10-06 contra o save real)

- Arquivo: `%APPDATA%\DarkSoulsII\<steamid64-hex>\DS2SOFS0000.sl2` (ou `.co2` com Seamless Co-op).
- Contêiner **BND4**: contagem de entradas em `0x0C`, tamanho do cabeçalho de entrada (`0x20`) em `0x20`; cabeçalhos começam em `0x40`.
  - Cabeçalho de entrada: tamanho (`int64` em `+0x08`), offset dos dados (`int32` em `+0x10`), offset do nome UTF-16 (`int32` em `+0x14`).
- Cada entrada: 16 bytes de checksum MD5, 16 bytes de IV, dados em **AES-128-CBC** com chave `599F9B699640A55236EE2D70835EC744`.
- 23 entradas: `USER_DATA000` (resumo dos slots), `USER_DATA001..010` (personagens), demais não usadas aqui.

### Layout do slot de personagem (offsets relativos ao dado decifrado)

| Offset | Tipo | Conteúdo |
|---|---|---|
| `0x24` | 9× `uint16` | VGR, END, VIT, ATN, STR, DEX, INT, FTH, ADP |
| `0x3C` | `uint32` | nível |
| `0x40` | `uint32` | almas em mãos |
| `0x44` | `uint32` | soul memory |
| `0x190` | `uint32[]` | IDs equipados (armas/catalisadores) |
| `0x1D0` | 4× `uint32` | anéis equipados |
| `0x208` | `uint32[]` | magias sintonizadas |
| `0x1E30…` | registros de 16 bytes | inventário: `id`, `0`, quantidade **ou** durabilidade (`float`), extra (byte 0 = nível de upgrade) |
| `~0x10E80…` | registros de 16 bytes | itens-chave: `0`, `id`, `0`, quantidade |

O nome do personagem aparece em UTF-16 logo após o bloco de atributos em `USER_DATA000`.
Esses offsets foram achados empiricamente; os testes com o save real (ver Testes) são a garantia contra regressão.

### Listas de IDs

Vêm do repositório `Nordgaren/DS2S-META` (`Resources/Equipment/**.txt`, formato `ID Nome`), licença MIT. Ficam vendorizadas em `games/ds2/ids/` junto com `LICENSE-DS2S-META`.

### Interface de linha de comando

```
python ds2save.py slots                      # lista personagens: slot, nome, nível
python ds2save.py snapshot [--save P] [--slot N]   # JSON da ficha completa em stdout
python ds2save.py levels --from 65 --to 90   # custo de cada nível + total
```

`snapshot` devolve:

```json
{
  "game": "ds2",
  "save_file": "...", "save_mtime": "...",
  "slot": 1, "name": "Melatonin", "level": 65,
  "souls": 0, "soul_memory": 221118,
  "stats": {"VGR": 9, "END": 6, "VIT": 5, "ATN": 30, "STR": 10, "DEX": 18, "INT": 26, "FTH": 6, "ADP": 8},
  "equipped": {"hands": {"L1": {...}, "R1": {...}}, "armor": {...}, "rings": [...], "spells": [...]},
  "inventory": [{"id": 1234, "name": "Uchigatana", "category": "MeleeWeapons", "upgrade": 5, "quantity": 1}],
  "unknown_ids": [100000000]
}
```

## Fluxo do `/build ds2 [pedido]`

1. `build` chama `ds2-save` → `snapshot` em JSON.
2. Carrega `profiles/ds2/<nome>.yaml`; se não existir, faz 3 perguntas (arquétipo, itens travados, foco secundário) e grava.
3. Compara com o último arquivo em `history/`; gera a lista "o que mudou" e grava o snapshot novo.
4. Monta o plano:
   - custos de alma sempre via `ds2save.py levels`, nunca calculados de cabeça;
   - para cada item que falta, consulta `wiki-cache` (onde pegar, requisitos);
   - consulta `wiki-cache` sobre builds de players do mesmo arquétipo e propõe ajustes compatíveis com o perfil.
5. `build-page` grava `plano.json` e republica a página no mesmo link (URL guardada em `config.json`).

### Perfil (`profiles/ds2/<nome>.yaml`)

```yaml
personagem: Melatonin
slot: 1
arquetipo: mago INT + espada DEX
secundario: piromancia (INT+FTH, soft cap 60)
travados: [Uchigatana]
nao_migrar: true
notas: []
```

### Página

> Substituído pela v2: `2026-10-06-buildsmith-pagina-v2-design.md` (estilo wiki, fluxos de nós, tabelas de dados, ícones).

`template/index.html` fixo + `plano.json` publicado como arquivo de apoio. Seções: ficha, "o que mudou", fluxograma de passos, custos por fase, onde pegar cada item, comparação com builds de players, fontes com data.

## Erros

| Situação | Comportamento |
|---|---|
| Save não encontrado | Pergunta o caminho uma vez e grava em `config.json` |
| BND4/AES inválido ou layout inesperado | Para com erro claro; nunca inventa atributo |
| ID desconhecido | `unknown_ids` + "item desconhecido #ID"; o resto segue |
| Wiki indisponível | Usa cache e marca "dados de DD/MM, podem estar desatualizados" |
| Save sendo gravado durante a leitura | Relê 1 vez; se falhar, pede para ir ao menu do jogo |
| Cache | Validade de 30 dias |

## Testes (`pytest`)

1. **Save sintético**: o teste monta um slot com valores conhecidos, empacota em BND4, cifra com a chave real e verifica que `snapshot` devolve exatamente esses valores.
2. **Save real (opcional)**: roda só se o save existir; confere invariantes (há personagem, nome não vazio, atributos entre 1 e 99, Uchigatana no inventário). Pulado em outras máquinas.
3. **Custos de nível**: 65→66 = 6.657; soma 66–76 = 82.736.
4. **Nomes**: `31010000` → Soul Arrow; ID inexistente → "desconhecido #ID" sem exceção.
5. **Skills (manual)**: `/build ds2` mostra ficha e custos iguais ao jogo, e o link da página não muda entre execuções.

## Fora do escopo (por enquanto)

- Outros jogos (a arquitetura permite, mas nenhum adaptador além do DS2).
- Editar o save.
- Ler a memória do jogo em execução.
- Builds de PvP / soul memory tiers.
