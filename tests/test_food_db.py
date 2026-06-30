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
