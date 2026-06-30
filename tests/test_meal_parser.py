from src.nutrition.food_db import FoodDB
from src.nutrition.meal_parser import parse_meal

DB = FoodDB("tests/fixtures/taco_min.csv")


def test_parse_gramas_e_rotulo():
    out = parse_meal("almoço: 100g arroz, 200g peito de frango", DB)
    assert out["meal"] == "almoço"
    arroz, frango = out["items"]
    assert arroz["grams"] == 100 and round(arroz["kcal"]) == 128
    assert frango["grams"] == 200 and round(frango["kcal"]) == 318
    assert all(i["recognized"] for i in out["items"])


def test_parse_unidade():
    out = parse_meal("2 ovos", DB)
    item = out["items"][0]
    assert item["grams"] == 100            # 2 * 50g
    assert round(item["kcal"]) == 143      # 143/100 * 100


def test_parse_item_desconhecido():
    out = parse_meal("100g patinho", DB)
    item = out["items"][0]
    assert item["recognized"] is False
    assert item["raw"] == "100g patinho"


def test_parse_sem_rotulo_e_lixo():
    out = parse_meal("blah blah", DB)
    assert out["meal"] is None
    assert out["items"][0]["recognized"] is False


CUSTOM = {"whey soldier": {"name": "whey soldier", "base_unit": "porcao",
                           "porcao_g": 30, "macros": {"kcal": 120, "p": 24, "c": 3, "g": 1.5}}}


def test_parse_scoop_custom():
    db = FoodDB("tests/fixtures/taco_min.csv", custom=CUSTOM)
    out = parse_meal("2 scoops whey soldier", db)
    item = out["items"][0]
    assert item["recognized"] is True
    assert item["kcal"] == 240          # 2 * 120
    assert item["p"] == 48


def test_unrecognized_carrega_nome_limpo():
    db = FoodDB("tests/fixtures/taco_min.csv")
    out = parse_meal("100g patinho", db)
    it = out["items"][0]
    assert it["recognized"] is False
    assert it["name"] == "patinho"


def test_parse_custom_em_gramas():
    db = FoodDB("tests/fixtures/taco_min.csv", custom=CUSTOM)
    out = parse_meal("60g whey soldier", db)   # 60g = 2 porções de 30g
    item = out["items"][0]
    assert round(item["kcal"]) == 240
