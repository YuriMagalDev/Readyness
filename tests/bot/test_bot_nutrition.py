# tests/bot/test_bot_nutrition.py
import sqlite3
import src.nutrition.store as store
from src.history_db import HistoryDB
from bot.nutrition import load_food_db, today_panel

PROFILE = {"peso_kg": 108, "percentual_gordura": 30}


def _db(tmp_path):
    p = str(tmp_path / "h.db")
    HistoryDB(p)
    return p


def _insert_snapshot(db_path, date, calories_total=None, calories_active=None):
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT OR REPLACE INTO daily_snapshot (date, calories_total, calories_active) "
        "VALUES (?,?,?)",
        (date, calories_total, calories_active),
    )
    conn.commit()
    conn.close()


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
    t = panel["today"]
    assert t["training"] is False
    assert round(t["target"]["kcal"]) == 2104
    assert t["totals"]["kcal"] == 500
    assert t["ea"]["faixa"] in ("verde", "amarelo", "vermelho")


def test_today_panel_training_sem_garmin_maior_que_descanso(tmp_path):
    """Dia de treino sem snapshot Garmin deve ter alvo kcal > descanso (ciclo via estimativa)."""
    p = _db(tmp_path)

    store.set_day_plan(p, "2026-06-30", vai_treinar=1, vai_correr=0)
    panel_treino = today_panel(p, PROFILE, "2026-06-30")

    store.set_day_plan(p, "2026-06-29", vai_treinar=0, vai_correr=0)
    panel_descanso = today_panel(p, PROFILE, "2026-06-29")

    assert panel_treino["today"]["target"]["kcal"] > panel_descanso["today"]["target"]["kcal"]


def test_today_panel_yesterday_balance(tmp_path):
    """yesterday block reads previous-day snapshot correctly."""
    p = _db(tmp_path)
    _insert_snapshot(p, "2026-06-29", calories_total=2900.0, calories_active=500.0)
    store.save_meal_items(p, "2026-06-29", "almoço",
                          [{"recognized": True, "food": "y", "grams": 200,
                            "kcal": 2200, "p": 150, "c": 200, "g": 50}])

    panel = today_panel(p, PROFILE, "2026-06-30")
    yd = panel["yesterday"]
    assert yd["burn"] == 2900.0
    assert yd["eaten"]["kcal"] == 2200
    assert yd["balance"]["saldo"] == 2200 - 2900.0
    assert yd["protein_target"] == 165


def test_today_panel_yesterday_no_snapshot(tmp_path):
    """yesterday balance.saldo is None when no Garmin snapshot for that day."""
    p = _db(tmp_path)
    panel = today_panel(p, PROFILE, "2026-06-30")
    yd = panel["yesterday"]
    assert yd["burn"] is None
    assert yd["balance"]["saldo"] is None
