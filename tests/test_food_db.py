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
