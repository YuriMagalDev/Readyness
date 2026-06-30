from src.nutrition.food_db import FoodDB, normalize

FIX = "tests/fixtures/taco_min.csv"


def test_normalize():
    assert normalize("  Peito de Frango  ") == "peito de frango"
    assert normalize("Açúcar") == "acucar"


def test_lookup_exato():
    db = FoodDB(FIX)
    item = db.lookup("arroz cozido")
    assert item["per100"]["kcal"] == 128
    assert item["per100"]["p"] == 2.5


def test_lookup_normaliza():
    db = FoodDB(FIX)
    assert db.lookup("ARROZ COZIDO")["per100"]["kcal"] == 128


def test_lookup_inexistente():
    db = FoodDB(FIX)
    assert db.lookup("dragon fruit") is None


def test_match_alias():
    db = FoodDB(FIX)
    m = db.match("frango")
    assert m["name"] == "peito de frango grelhado"


def test_match_fuzzy_acima_do_limiar():
    db = FoodDB(FIX)
    m = db.match("arroz cozido")          # exato
    assert m["score"] == 100
    m2 = db.match("arrloz cozido")        # typo
    assert m2 is not None and m2["name"] == "arroz cozido"


def test_match_abaixo_do_limiar():
    db = FoodDB(FIX)
    assert db.match("xyzqwk", threshold=85) is None


def test_porcao_unitaria():
    db = FoodDB(FIX)
    assert db.portion_grams("ovo") == 50
    assert db.portion_grams("banana") == 100
    assert db.portion_grams("arroz cozido") is None


def test_custom_food_prioridade_e_porcao():
    custom = {
        "whey soldier": {
            "name": "whey soldier", "base_unit": "porcao", "porcao_g": 30,
            "macros": {"kcal": 120, "p": 24, "c": 3, "g": 1.5},
        }
    }
    db = FoodDB(FIX, custom=custom)
    m = db.match("whey soldier")
    assert m["per_portion"]["p"] == 24
    assert m["portion_g"] == 30
    assert db.portion_grams("whey soldier") == 30


def test_custom_100g_vira_per100():
    custom = {
        "tapioca": {"name": "tapioca", "base_unit": "100g", "porcao_g": None,
                    "macros": {"kcal": 240, "p": 0.5, "c": 60, "g": 0.1}}
    }
    db = FoodDB(FIX, custom=custom)
    assert db.match("tapioca")["per100"]["kcal"] == 240
