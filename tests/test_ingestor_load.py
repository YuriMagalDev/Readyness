import datetime as dt
from src.history_db import HistoryDB
from src.ingestor import Ingestor


def _seed_runs(db, end="2026-06-20", n=28, trimp_hr=150):
    """Seed n days of runs with alternating duration (30/45 min) so pstdev > 0
    and monotony() returns a value rather than None (uniform loads → desvio=0)."""
    end_d = dt.date.fromisoformat(end)
    for i in range(n):
        d = (end_d - dt.timedelta(days=i)).isoformat()
        duration = 30 if i % 2 == 0 else 45
        db.upsert_activity({
            "activity_id": 1000 + i, "date": d, "name": "run", "type": "running",
            "is_strength": 0, "distance_m": 5000, "duration_min": duration,
            "pace_min_km": 6.0, "avg_hr": trimp_hr, "max_hr": 175,
            "calories": 300, "cadence": 160, "stride_length": 1.0,
        })
        db.upsert_metric(d, "resting_hr", 50, d + "T08:00:00", "garmin")


def test_write_load_metrics_grava_computed(tmp_path):
    db = HistoryDB(str(tmp_path / "h.db"))
    _seed_runs(db)
    ing = Ingestor(client=None, db=db)
    ing._write_load_metrics("2026-06-20")
    metrics = {m["metric_key"]: m for m in db.get_metrics("2026-06-20")}
    assert "acwr" in metrics and metrics["acwr"]["source"] == "computed"
    assert "training_monotony" in metrics
    assert "resting_hr_baseline" in metrics
    assert metrics["resting_hr_baseline"]["value"] == 50.0


def test_write_load_metrics_sem_corridas_nao_grava(tmp_path):
    db = HistoryDB(str(tmp_path / "h2.db"))
    ing = Ingestor(client=None, db=db)
    ing._write_load_metrics("2026-06-20")
    keys = {m["metric_key"] for m in db.get_metrics("2026-06-20")}
    assert "acwr" not in keys          # sem crônico -> não grava
    assert "training_monotony" not in keys
