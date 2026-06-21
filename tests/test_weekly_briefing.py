import datetime as dt
from src.history_db import HistoryDB
from src.weekly_briefing import build_weekly_briefing


def test_briefing_agrega_semana(tmp_path):
    db = HistoryDB(str(tmp_path / "b.db"))
    for i, km in enumerate([5, 8]):       # 2 corridas na semana
        d = (dt.date(2026, 6, 20) - dt.timedelta(days=i)).isoformat()
        db.upsert_activity({"activity_id": 10 + i, "date": d, "name": "run",
                            "type": "running", "is_strength": 0,
                            "distance_m": km * 1000, "duration_min": 30,
                            "pace_min_km": 6.0, "avg_hr": 150, "max_hr": 175,
                            "calories": 300, "cadence": 160, "stride_length": 1.0})
        db.upsert_metric(d, "sleep_hours", 7.0, d + "T08:00:00", "garmin")
    db.upsert_metric("2026-06-20", "acwr", 1.8, "2026-06-20T10:00:00", "computed")
    out = build_weekly_briefing(db, dt.date(2026, 6, 20))
    assert out["km_7d"] == 13.0 and out["sessoes"] == 2
    assert out["acwr"] == 1.8
    assert out["sono_medio"] == 7.0
    assert out["recomendacao"].startswith("Semana de deload")   # zona risco


def test_briefing_sem_dados_degrada(tmp_path):
    db = HistoryDB(str(tmp_path / "b2.db"))
    out = build_weekly_briefing(db, dt.date(2026, 6, 20))
    assert out["km_7d"] == 0.0 and out["sessoes"] == 0
    assert out["acwr"] is None and out["sono_medio"] is None
    assert out["recomendacao"] == "Mantenha a carga atual."     # zona None
