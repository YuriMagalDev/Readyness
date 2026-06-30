import src.nutrition.store as store
from src.history_db import HistoryDB


def _db(tmp_path):
    p = str(tmp_path / "h.db")
    HistoryDB(p)                       # cria tabelas
    return p


def test_custom_food_roundtrip(tmp_path):
    p = _db(tmp_path)
    store.add_custom_food(p, "whey soldier", "porcao", 30, 120, 24, 3, 1.5)
    foods = store.get_custom_foods(p)
    assert "whey soldier" in foods
    assert foods["whey soldier"]["base_unit"] == "porcao"


def test_save_e_totais(tmp_path):
    p = _db(tmp_path)
    items = [
        {"recognized": True, "food": "arroz", "grams": 100, "kcal": 128, "p": 2.5, "c": 28, "g": 0.2},
        {"recognized": False, "raw": "patinho"},
    ]
    store.save_meal_items(p, "2026-06-30", "almoço", items)
    t = store.day_totals(p, "2026-06-30")
    assert round(t["kcal"]) == 128 and t["n_meals"] == 1


def test_apaga_ultimo(tmp_path):
    p = _db(tmp_path)
    store.save_meal_items(p, "2026-06-30", "almoço",
                          [{"recognized": True, "food": "x", "grams": 10,
                            "kcal": 10, "p": 1, "c": 1, "g": 1}])
    assert store.delete_last_meal_item(p, "2026-06-30") is True
    assert store.day_totals(p, "2026-06-30")["kcal"] == 0


def test_day_plan(tmp_path):
    p = _db(tmp_path)
    store.set_day_plan(p, "2026-06-30", vai_treinar=1, vai_correr=0)
    assert store.get_day_plan(p, "2026-06-30")["vai_treinar"] == 1
