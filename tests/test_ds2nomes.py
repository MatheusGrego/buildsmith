import ds2nomes

TABELAS = {
    "inimigos": {"318030": "The Pursuer - Lost Bastille", "125015": "Rupturing Hollow (Yellow Core) - Lost Bastille",
                 "133001": "Bonewheel Skeleton (Boss - Skeleton Lords)"},
    "personagens": {"c1020": "Hollow Soldier"},
    "objetos": {"o00_0300": "Wooden Door", "o04_0470": "Large Stone Door (Forgotten Key)", "o00_0600": "Vertical Lever",
                "o00_0500": "Fog Gate (Small)", "o10_1030": "Lever Door", "o00_9115": "Drawbridge Lever",
                "o14_0371": "Wooden Door (Den Key) - Brightstone Cove Tseldora", "o00_0100": "Bonfire",
                "o14_1020": "Dummy for sand door damage - Brightstone Cove Tseldora", "o16_1600": "Cage Elevator - Lost Bastille",
                "o00_1810": "Pharros Contraption - Shrine of Amana", "o00_0200": "Wooden Treasure Chest"},
}
ITENS = {50820000: "Forgotten Key", 50930000: "Tseldora Den Key", 50860000: "House Key", 1: "Dagger"}


def test_row_name_splits_base_variant_and_place():
    assert ds2nomes.partes_nome("Rupturing Hollow (Red Core) - Lost Bastille") == {
        "base": "Rupturing Hollow", "variante": "Red Core", "local": "Lost Bastille"}
    assert ds2nomes.partes_nome("Bonewheel Skeleton (Boss - Skeleton Lords)") == {  # o " - " dentro do parêntese fica
        "base": "Bonewheel Skeleton", "variante": "Boss - Skeleton Lords", "local": ""}
    assert ds2nomes.partes_nome("Darksucker") == {"base": "Darksucker", "variante": "", "local": ""}


def test_enemy_name_from_the_row_then_the_model():
    assert ds2nomes.nome_inimigo(318030, TABELAS)["nome"] == "The Pursuer"  # o Pursuer perto do McDuff
    r = ds2nomes.nome_inimigo("125015", TABELAS)
    assert r["nome"] == "Rupturing Hollow (Yellow Core)" and r["base"] == "Rupturing Hollow" and r["fonte"] == "jogo"
    assert "125015" in r["prova"] and "EnemyParam" in r["prova"]
    assert ds2nomes.nome_inimigo(133001, TABELAS)["nome"] == "Bonewheel Skeleton"  # "(Boss - ...)" não é variante
    m = ds2nomes.nome_inimigo(102099, TABELAS)  # linha sem nome: o modelo c1020 dá o nome
    assert m["nome"] == "Hollow Soldier" and m["fonte"] == "modelo" and "c1020" in m["prova"]
    assert ds2nomes.nome_inimigo(999999, TABELAS) is None and ds2nomes.nome_inimigo(None, TABELAS) is None


def test_vendored_table_names_the_lost_bastille_pursuer():
    assert ds2nomes.nome_inimigo(318030)["nome"] == "The Pursuer"
    assert ds2nomes.nome_inimigo(102000)["base"] == "Hollow Soldier"


def test_object_category_by_model_name_in_order():
    cat = lambda m, t=None: (ds2nomes.objeto(m, t, ITENS, TABELAS) or {}).get("cat")  # noqa: E731
    assert cat("o00_0300") == "porta" and cat("o10_1030") == "porta"  # "Lever Door" é porta
    assert cat("o00_0600") == "alavanca" and cat("o00_9115") == "alavanca"  # "Drawbridge Lever" é alavanca
    assert cat("o00_0500") == "nevoa" and cat("o16_1600") == "elevador" and cat("o00_1810") == "pharros"
    assert cat("o00_0200") == "bau"
    assert cat("o00_0100") is None and cat("o14_1020") is None  # fogueira e peça auxiliar ficam de fora
    assert cat("o99_9999", 121) == "bau" and cat("o99_9999", 210) == "porta" and cat("o99_9999", 1001) is None


def test_door_key_from_model_name_only_if_the_item_exists():
    assert ds2nomes.objeto("o04_0470", None, ITENS, TABELAS)["chave"] == [50820000, "Forgotten Key"]
    assert ds2nomes.objeto("o14_0371", None, ITENS, TABELAS)["chave"] == [50930000, "Tseldora Den Key"]
    assert ds2nomes.objeto("o00_0300", None, ITENS, TABELAS)["chave"] is None
    assert ds2nomes.objeto("o04_0470", None, {1: "Dagger"}, TABELAS)["chave"] is None
    assert ds2nomes.chave_do_nome("A-san House Key Door", ITENS) == (50860000, "House Key")


def test_lapide_de_npc_e_ajudante_ficam_fora_do_cenario():
    t = {"objetos": {"o00_9050": "Tombstone", "o34_9003": "Dummy for SFX - Grave of Saints",
                     "o24_9000": "Tombstone - Undead Crypt", "o00_0200": "Wooden Treasure Chest"}}
    assert ds2nomes.fora_da_cena("o00_9050", t) and ds2nomes.fora_da_cena("o34_9003", t)
    assert ds2nomes.fora_da_cena("o24_9000", t) is None  # a lápide do cemitério é cenário
    assert ds2nomes.fora_da_cena("o00_0200", t) is None and ds2nomes.fora_da_cena("o99_9999", t) is None
