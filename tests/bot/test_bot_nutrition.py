# tests/bot/test_bot_nutrition.py
import src.nutrition.store as store
from src.history_db import HistoryDB
from bot.nutrition import load_food_db, today_panel

PROFILE = {"peso_kg": 108, "percentual_gordura": 30}


def _db(tmp_path):
    p = str(tmp_path / "h.db")
    HistoryDB(p)
    return p


def test_load_food_db_inclui_custom(tmp_path):
    p = _db(tmp_path)
    store.add_custom_food(p, "whey soldier", "porcao", 30, 120, 24, 3, 1.5)
    db = load_food_db(p, taco_path="tests/fixtures/taco_min.csv")
    assert db.match("whey soldier")["per_portion"]["p"] == 24
    assert db.match("arroz cozido") is not None


def test_today_panel_descanso(tmp_path):
    p = _db(tmp_path)
    store.set_day_plan(p, "2026-06-30", vai_treinar=0, vai_correr=0)
    store.save_meal_items(p, "2026-06-30", "almoço",
                          [{"recognized": True, "food": "x", "grams": 100,
                            "kcal": 500, "p": 40, "c": 50, "g": 10}])
    panel = today_panel(p, PROFILE, "2026-06-30")
    assert panel["training"] is False
    assert round(panel["target"]["kcal"]) == 2104
    assert panel["totals"]["kcal"] == 500
    assert panel["ea"]["faixa"] in ("verde", "amarelo", "vermelho")
