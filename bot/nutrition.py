import datetime

from src.nutrition.config import nutrition_config
from src.nutrition.targets import day_target, energy_availability, resolve_exercise_kcal, day_balance
from src.nutrition.food_db import FoodDB, load_aliases, PORTIONS
import src.nutrition.store as store

_ALIASES_PATH = "src/nutrition/data/aliases.csv"


def load_food_db(db_path, taco_path="src/nutrition/data/taco.csv",
                 aliases_path=_ALIASES_PATH):
    # SÓ os aliases curados (termo comum -> nome TACO exato). Os ALIASES globais
    # apontam pros nomes do fixture (não existem na TACO real) — não entram em prod.
    aliases = load_aliases(aliases_path)
    return FoodDB(taco_path, custom=store.get_custom_foods(db_path),
                  aliases=aliases, portions=PORTIONS)


def today_panel(db_path, profile, date):
    cfg = nutrition_config(profile)

    # ── TODAY ──────────────────────────────────────────────────────────────────
    plan = store.get_day_plan(db_path, date) or {}
    training = bool(plan.get("vai_treinar") or plan.get("vai_correr"))
    totals = store.day_totals(db_path, date)

    ex_today = resolve_exercise_kcal(
        cfg,
        vai_treinar=bool(plan.get("vai_treinar")),
        vai_correr=bool(plan.get("vai_correr")),
        garmin_active_kcal=store.garmin_active_kcal(db_path, date),
    )
    target = day_target(cfg, training=training, exercise_kcal=ex_today)
    ea = energy_availability(cfg, totals["kcal"], ex_today)

    today = {
        "totals": totals,
        "target": target,
        "ea": ea,
        "training": training,
        "exercise_kcal": ex_today,
    }

    # ── YESTERDAY ──────────────────────────────────────────────────────────────
    yday = (datetime.date.fromisoformat(date) - datetime.timedelta(days=1)).isoformat()
    eaten_y = store.day_totals(db_path, yday)
    burn_y = store.garmin_total_kcal(db_path, yday)
    active_y = store.garmin_active_kcal(db_path, yday)
    balance_y = day_balance(eaten_y["kcal"], burn_y)
    ea_y = energy_availability(cfg, eaten_y["kcal"], active_y or 0)

    yesterday = {
        "eaten": eaten_y,
        "burn": burn_y,
        "active": active_y,
        "balance": balance_y,
        "ea": ea_y,
        "protein_target": cfg["protein_g"],
    }

    return {"today": today, "yesterday": yesterday}
