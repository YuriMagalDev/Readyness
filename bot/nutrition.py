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


def resolve_unknowns(db_path, names, client, model):
    """Resolve nomes de alimentos via IA e cacheia em custom_foods (source='ia').

    Retorna a lista de termos resolvidos. Termo é gravado como o usuário digitou,
    pra bater exato no próximo /comi. Sem cliente/API: retorna [] (degrada).
    """
    from src.nutrition.food_resolver import resolve_food
    resolvidos = []
    for termo in dict.fromkeys(n for n in names if n):   # distintos, preserva ordem
        data = resolve_food(termo, client=client, model=model)
        if not data:
            continue
        store.add_custom_food(db_path, termo, data["base_unit"], data.get("porcao_g"),
                              data["kcal"], data["p"], data["c"], data["g"], source="ia")
        resolvidos.append(termo)
    return resolvidos


def parse_peso_arg(text):
    """'107,4' | '107.4' -> 107.4 ; inválido/fora de faixa humana -> None."""
    if not text:
        return None
    try:
        v = float(text.strip().replace(",", "."))
    except ValueError:
        return None
    if not (30.0 <= v <= 300.0):
        return None
    return v


def build_progress_report(weights, week_days, cfg, prev_bf, prev_weight):
    """Monta o texto do /progresso + a proposta de ajuste (pura, testável).

    weights: lista de kg (cronológica). week_days: list de dicts com p, kcal, training.
    """
    from src.nutrition.adaptive import (
        trend_kg, weekly_rate_pct, derive_bf,
        is_adherent_day, week_adherence_ok, propose_adjustment,
    )

    trend = trend_kg(weights)
    rate = weekly_rate_pct(weights)

    flags = []
    for d in week_days:
        target = day_target(cfg, training=d.get("training", False))
        flags.append(is_adherent_day({"p": d["p"], "kcal": d["kcal"]}, target))
    adher_ok = week_adherence_ok(flags)

    proposal = propose_adjustment(rate, adher_ok, cfg)

    latest = weights[-1] if weights else prev_weight
    bf = derive_bf(prev_weight, prev_bf, weights[-1]) if weights else prev_bf
    lbm = latest * (1 - bf / 100.0)

    lines = ["📊 *Progresso*"]
    if trend is not None:
        lines.append(f"Peso (tendência): {trend:.1f} kg")
    if rate is not None:
        lines.append(f"Ritmo: {rate:+.2f}%/sem")
    lines.append(f"BF estimado: {bf:.1f}% · LBM {lbm:.1f} kg")
    lines.append(f"Aderência: {sum(flags)}/{len(flags)} dias" if flags else "Aderência: sem registro")
    lines.append(f"→ {proposal['reason']}")
    return {"text": "\n".join(lines), "proposal": proposal}


def today_panel(db_path, profile, date):
    cfg = nutrition_config(profile)
    cfg["kcal_adjust"] = store.get_kcal_adjust(db_path)

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
