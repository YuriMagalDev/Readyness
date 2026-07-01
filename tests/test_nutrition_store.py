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


def test_save_recognized_sem_macros_nao_quebra(tmp_path):
    p = _db(tmp_path)
    store.save_meal_items(p, "2026-06-30", "almoço",
                          [{"recognized": True, "food": "x", "grams": 10}])
    t = store.day_totals(p, "2026-06-30")
    assert t["kcal"] == 0 and t["n_meals"] == 1


def test_weights_roundtrip(tmp_path):
    p = _db(tmp_path)
    store.add_weight(p, "2026-06-22", 108.0)
    store.add_weight(p, "2026-06-29", 107.4)
    ws = store.get_weights(p)
    assert [w["kg"] for w in ws] == [108.0, 107.4]
    assert store.latest_weight(p) == 107.4


def test_weight_upsert_mesma_data(tmp_path):
    p = _db(tmp_path)
    store.add_weight(p, "2026-06-29", 107.4)
    store.add_weight(p, "2026-06-29", 107.1)   # corrige o mesmo dia
    assert store.latest_weight(p) == 107.1
    assert len(store.get_weights(p)) == 1


def test_kcal_adjust_default_zero(tmp_path):
    p = _db(tmp_path)
    assert store.get_kcal_adjust(p) == 0


def test_kcal_adjust_roundtrip(tmp_path):
    p = _db(tmp_path)
    store.set_kcal_adjust(p, -100)
    assert store.get_kcal_adjust(p) == -100


def test_week_totals(tmp_path):
    p = _db(tmp_path)
    store.save_meal_items(p, "2026-06-29", "almoço",
                          [{"recognized": True, "food": "x", "grams": 10,
                            "kcal": 500, "p": 40, "c": 10, "g": 5}])
    tots = store.week_totals(p, ["2026-06-29", "2026-06-30"])
    assert round(tots[0]["kcal"]) == 500 and tots[1]["kcal"] == 0


def _insert_snapshot(db_path, date, calories_total=None, calories_active=None):
    import sqlite3
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute(
        "INSERT OR REPLACE INTO daily_snapshot (date, calories_total, calories_active) "
        "VALUES (?,?,?)",
        (date, calories_total, calories_active),
    )
    conn.commit()
    conn.close()


def test_garmin_kcal_reads(tmp_path):
    p = _db(tmp_path)
    _insert_snapshot(p, "2026-06-29", calories_total=2800.0, calories_active=450.0)
    assert store.garmin_total_kcal(p, "2026-06-29") == 2800.0
    assert store.garmin_active_kcal(p, "2026-06-29") == 450.0


def test_garmin_kcal_missing_date(tmp_path):
    p = _db(tmp_path)
    assert store.garmin_total_kcal(p, "2026-06-01") is None
    assert store.garmin_active_kcal(p, "2026-06-01") is None


def test_list_e_delete_meal_item(tmp_path):
    p = _db(tmp_path)
    store.save_meal_items(p, "2026-06-30", "almoço", [
        {"recognized": True, "food": "arroz", "grams": 100, "kcal": 128, "p": 2, "c": 28, "g": 0},
        {"recognized": True, "food": "frango", "grams": 200, "kcal": 318, "p": 62, "c": 0, "g": 7},
    ])
    itens = store.list_meal_items(p, "2026-06-30")
    assert len(itens) == 2 and "id" in itens[0]
    assert store.delete_meal_item(p, itens[0]["id"]) is True
    assert len(store.list_meal_items(p, "2026-06-30")) == 1
    assert store.delete_meal_item(p, 99999) is False
