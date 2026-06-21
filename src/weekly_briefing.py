import datetime as _dt
from src.training_load import RUN_TYPES, estimate_hr_max, acwr_zone
from src.ingestor import Ingestor

_REC = {
    "risco": "Semana de deload: reduza volume/intensidade.",
    "baixo": "Pode aumentar a carga com cuidado.",
    "otimo": "Mantenha a carga atual.",
}
_REC_DEFAULT = "Mantenha a carga atual."


def build_weekly_briefing(db, today: _dt.date = None) -> dict:
    today = today or _dt.date.today()
    end = today.isoformat()
    start7 = (today - _dt.timedelta(days=6)).isoformat()

    acts = db.get_activities(start7, end)
    runs = [a for a in acts if not a.get("is_strength") and a.get("type") in RUN_TYPES]
    km_7d = round(sum((a.get("distance_m") or 0) for a in runs) / 1000, 1)

    day_metrics = {r["metric_key"]: r["value"] for r in db.get_metrics(end)}
    acwr = day_metrics.get("acwr")

    sleep_rows = db.get_metric_series("sleep_hours", start7, end)
    sleep_vals = [r["value"] for r in sleep_rows if r["value"] is not None]
    sono_medio = round(sum(sleep_vals) / len(sleep_vals), 1) if sleep_vals else None

    start90 = (today - _dt.timedelta(days=89)).isoformat()
    acts90 = db.get_activities(start90, end)
    fc_max = estimate_hr_max(acts90, Ingestor._idade())

    zona = acwr_zone(acwr) if acwr is not None else None
    rec = _REC.get(zona, _REC_DEFAULT)

    return {
        "km_7d": km_7d,
        "sessoes": len(runs),
        "acwr": round(acwr, 2) if acwr is not None else None,
        "sono_medio": sono_medio,
        "fc_max": fc_max,
        "recomendacao": rec,
    }
