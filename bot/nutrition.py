from src.nutrition.config import nutrition_config
from src.nutrition.targets import day_target, energy_availability
from src.nutrition.food_db import FoodDB
import src.nutrition.store as store


def load_food_db(db_path, taco_path="src/nutrition/data/taco.csv"):
    return FoodDB(taco_path, custom=store.get_custom_foods(db_path))


def today_panel(db_path, profile, date, exercise_kcal=0.0):
    cfg = nutrition_config(profile)
    plan = store.get_day_plan(db_path, date) or {}
    training = bool(plan.get("vai_treinar") or plan.get("vai_correr"))
    totals = store.day_totals(db_path, date)
    target = day_target(cfg, training=training, exercise_kcal=exercise_kcal)
    ea = energy_availability(cfg, totals["kcal"], exercise_kcal)
    return {"totals": totals, "target": target, "ea": ea, "training": training}
