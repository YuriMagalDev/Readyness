import datetime as _dt
from src.metric_catalog import CATALOG, DOMAIN_ORDER
from src.metric_status import compute_status


def read_metrics(db, date: str, today: _dt.date = None) -> dict:
    today = today or _dt.date.today()
    rows_today = {r["metric_key"]: r for r in db.get_metrics(date)}

    dominios = {d: [] for d in DOMAIN_ORDER}
    for spec in CATALOG:
        row = rows_today.get(spec.key)
        if row is None and spec.cadencia in ("corpo", "fitness"):
            row = _latest_on_or_before(db, spec.key, date)

        if row is None:
            value, measured_at, source = None, None, spec.source_default
        else:
            value, measured_at, source = row["value"], row["measured_at"], row["source"]

        status = compute_status(spec.cadencia, source, measured_at, today)
        dominios[spec.dominio].append({
            "key": spec.key, "label": spec.label, "value": value,
            "unidade": spec.unidade, "measured_at": measured_at,
            "status": status, "source": source,
        })
    return {"date": date, "dominios": dominios}


def _latest_on_or_before(db, metric_key: str, date: str):
    start = (_dt.date.fromisoformat(date) - _dt.timedelta(days=60)).isoformat()
    series = db.get_metric_series(metric_key, start, date)
    return series[-1] if series else None


SLEEP_TARGET_HOURS = 7.0
RUN_TYPES = {"running", "trail_running", "treadmill_running"}


def context_from_metrics(db, date: str, today: _dt.date = None) -> dict:
    today = today or _dt.date.today()
    week_start = (_dt.date.fromisoformat(date) - _dt.timedelta(days=6)).isoformat()

    hr_series = db.get_metric_series("resting_hr", week_start, date)
    hr_vals = [r["value"] for r in hr_series if r["value"] is not None]
    hr_avg = round(sum(hr_vals) / len(hr_vals), 1) if hr_vals else 0.0
    hr_today = hr_vals[-1] if hr_vals else hr_avg

    sleep_series = db.get_metric_series("sleep_hours", week_start, date)
    debt = sum(max(SLEEP_TARGET_HOURS - r["value"], 0)
               for r in sleep_series if r["value"] is not None)

    bat_series = db.get_metric_series("body_battery_high", week_start, date)
    bat_vals = [r["value"] for r in bat_series if r["value"] is not None]
    battery = bat_vals[-1] if bat_vals else 100

    acts = db.get_activities(week_start, date)
    runs = sum(1 for a in acts if not a.get("is_strength") and a.get("type") in RUN_TYPES)

    day_metrics = {r["metric_key"]: r["value"] for r in db.get_metrics(date)}

    return {
        "resting_hr_today": hr_today,
        "resting_hr_avg_7d": hr_avg,
        "sleep_debt_hours": round(debt, 1),
        "morning_battery_avg": battery,
        "run_sessions_7d": runs,
        "acwr": day_metrics.get("acwr"),
        "soreness": day_metrics.get("soreness"),
        "energia": day_metrics.get("energia"),
        "resting_hr_baseline": day_metrics.get("resting_hr_baseline"),
    }
