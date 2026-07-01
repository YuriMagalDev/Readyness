import datetime as dt
import sqlite3
from contextlib import contextmanager

from src.nutrition.food_db import normalize


def _conn(db_path: str):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def _session(db_path):
    conn = _conn(db_path)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def add_custom_food(db_path, name, base_unit, porcao_g, kcal, p, c, g, source="manual"):
    with _session(db_path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO custom_foods "
            "(name, base_unit, porcao_g, kcal, p, c, g, created_at, source) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (normalize(name), base_unit, porcao_g, kcal, p, c, g,
             dt.datetime.now().isoformat(), source),
        )


def get_custom_foods(db_path) -> dict:
    with _session(db_path) as conn:
        rows = conn.execute("SELECT * FROM custom_foods").fetchall()
    out = {}
    for r in rows:
        out[r["name"]] = {
            "name": r["name"],
            "base_unit": r["base_unit"],
            "porcao_g": r["porcao_g"],
            "macros": {"kcal": r["kcal"], "p": r["p"], "c": r["c"], "g": r["g"]},
            "source": (r["source"] if "source" in r.keys() else None) or "manual",
        }
    return out


def save_meal_items(db_path, date, meal, items):
    now = dt.datetime.now().isoformat()
    rows = [
        (date, meal, it.get("food"), it.get("grams"),
         it.get("kcal", 0.0), it.get("p", 0.0), it.get("c", 0.0), it.get("g", 0.0), now)
        for it in items if it.get("recognized")
    ]
    if not rows:
        return
    with _session(db_path) as conn:
        conn.executemany(
            "INSERT INTO meal_log (date, meal, food, grams, kcal, p, c, g, logged_at) "
            "VALUES (?,?,?,?,?,?,?,?,?)", rows,
        )


def day_totals(db_path, date) -> dict:
    with _session(db_path) as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(kcal),0) k, COALESCE(SUM(p),0) p, "
            "COALESCE(SUM(c),0) c, COALESCE(SUM(g),0) g, "
            "COUNT(DISTINCT meal) nm, MAX(logged_at) last "
            "FROM meal_log WHERE date=?", (date,),
        ).fetchone()
    return {"kcal": row["k"], "p": row["p"], "c": row["c"], "g": row["g"],
            "n_meals": row["nm"], "last_at": row["last"]}


def garmin_active_kcal(db_path, date):
    """Return calories_active from daily_snapshot for *date*, or None if absent."""
    with _session(db_path) as conn:
        row = conn.execute(
            "SELECT calories_active FROM daily_snapshot WHERE date=?", (date,)
        ).fetchone()
    return row["calories_active"] if row and row["calories_active"] is not None else None


def garmin_total_kcal(db_path, date):
    """Return calories_total from daily_snapshot for *date*, or None if absent."""
    with _session(db_path) as conn:
        row = conn.execute(
            "SELECT calories_total FROM daily_snapshot WHERE date=?", (date,)
        ).fetchone()
    return row["calories_total"] if row and row["calories_total"] is not None else None


def list_meal_items(db_path, date) -> list:
    """Itens do dia com id (pra editar/apagar item específico)."""
    with _session(db_path) as conn:
        rows = conn.execute(
            "SELECT id, meal, food, grams, kcal FROM meal_log WHERE date=? ORDER BY id",
            (date,),
        ).fetchall()
    return [dict(r) for r in rows]


def delete_meal_item(db_path, item_id) -> bool:
    with _session(db_path) as conn:
        cur = conn.execute("DELETE FROM meal_log WHERE id=?", (item_id,))
    return cur.rowcount > 0


def delete_last_meal_item(db_path, date) -> bool:
    with _session(db_path) as conn:
        row = conn.execute(
            "SELECT id FROM meal_log WHERE date=? ORDER BY id DESC LIMIT 1", (date,),
        ).fetchone()
        if not row:
            return False
        conn.execute("DELETE FROM meal_log WHERE id=?", (row["id"],))
    return True


def set_day_plan(db_path, date, vai_treinar, vai_correr):
    with _session(db_path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO day_plan (date, vai_treinar, vai_correr, set_at) "
            "VALUES (?,?,?,?)",
            (date, vai_treinar, vai_correr, dt.datetime.now().isoformat()),
        )


def get_day_plan(db_path, date):
    with _session(db_path) as conn:
        row = conn.execute("SELECT * FROM day_plan WHERE date=?", (date,)).fetchone()
    return dict(row) if row else None
