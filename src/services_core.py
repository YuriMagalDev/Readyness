"""Lógica de domínio independente da camada FastAPI (usada pelo bot)."""
import datetime as _dt
import json as _json

from src.analytics import Analytics
from src.insight_engine import InsightEngine
from src.extractors import splits_from_garmin

_CHECKIN_KEYS = {"hidratacao", "energia", "soreness", "alimentacao"}


def save_checkin(db, payload: dict, today: _dt.date = None) -> dict:
    today = today or _dt.date.today()
    now = _dt.datetime.now().isoformat(timespec="minutes")
    day = today.isoformat()
    for key, val in payload.items():
        if key not in _CHECKIN_KEYS:
            continue
        if not isinstance(val, int) or not (1 <= val <= 5):
            raise ValueError(f"{key} deve ser inteiro 1-5")
        db.upsert_metric(day, key, val, now, "manual")
    return {"ok": True}


def _period_range(period: int):
    end = _dt.date.today()
    start = end - _dt.timedelta(days=period - 1)
    return start.isoformat(), end.isoformat()


def build_run_detail(db, client, activity_id: int) -> dict:
    """Detalhe de uma corrida: splits (cache ou Garmin) + insight da IA. Fonte única."""
    act = db.get_activity(activity_id)
    if act is None:
        raise ValueError(f"Atividade {activity_id} não encontrada")
    if act.get("splits_json"):
        splits = _json.loads(act["splits_json"])
    else:
        splits = splits_from_garmin(client.get_activity_splits(activity_id))
        act["splits_json"] = _json.dumps(splits)
        db.upsert_activity(act)
    insight = InsightEngine(db=db).activity_insight(act, splits)
    return {"activity": act, "splits": splits, "insight": insight}


def build_trends(db, period: int = 30, force: bool = False) -> dict:
    start, end = _period_range(period)
    snaps = db.get_snapshots(start, end)
    metrics = Analytics().summary(snaps)
    insights = InsightEngine(db=db).trend_insights(metrics, period=period, force=force)
    return {"period": period, "metrics": metrics, "insights": insights}
