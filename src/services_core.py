"""Lógica de domínio independente da camada FastAPI (usada pelo bot)."""
import datetime as _dt

from src.analytics import Analytics
from src.insight_engine import InsightEngine

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


def build_trends(db, period: int = 30, force: bool = False) -> dict:
    start, end = _period_range(period)
    snaps = db.get_snapshots(start, end)
    metrics = Analytics().summary(snaps)
    insights = InsightEngine(db=db).trend_insights(metrics, period=period, force=force)
    return {"period": period, "metrics": metrics, "insights": insights}
