import datetime
from unittest.mock import MagicMock
from src.ingestor import Ingestor


def _summary(rhr=52):
    return {"restingHeartRate": rhr, "totalSteps": 8000, "moderateIntensityMinutes": 20,
            "vigorousIntensityMinutes": 5, "averageStressLevel": 30, "averageSpo2": 96,
            "bodyBatteryHighestValue": 90, "bodyBatteryLowestValue": 20,
            "totalKilocalories": 2200, "activeKilocalories": 500,
            "measurableAsleepDuration": 25200}


def _client():
    c = MagicMock()
    c.get_daily_summary.return_value = _summary()
    c.get_race_predictions.return_value = {"time5K": 1758, "time10K": 3700,
                                           "timeHalfMarathon": 8200, "timeMarathon": 17000}
    c.get_activities_by_date.return_value = [{
        "activityId": 1, "activityName": "Corrida", "startTimeLocal": "2026-06-10 07:00:00",
        "activityType": {"typeKey": "running"}, "distance": 5000, "duration": 1500,
        "averageSpeed": 3.333, "averageHR": 150,
    }]
    c.get_sleep.return_value = [{"dailySleepDTO": {"sleepTimeSeconds": 25200, "deepSleepSeconds": 5400, "lightSleepSeconds": 14400, "remSleepSeconds": 5400}}]
    c.get_hrv.return_value = None
    c.get_training_readiness.return_value = None
    c.get_max_metrics.return_value = None
    c.get_endurance_score.return_value = None
    c.get_body_composition.return_value = None
    return c


def test_backfill_writes_snapshots(tmp_path):
    from src.history_db import HistoryDB
    db = HistoryDB(db_path=str(tmp_path / "h.db"))
    client = _client()
    ing = Ingestor(client, db, sleep_seconds=0)
    ing.backfill(days=3, today=datetime.date(2026, 6, 10))
    rows = db.get_snapshots("2026-06-01", "2026-06-30")
    assert len(rows) == 3
    assert all(r["resting_hr"] == 52 for r in rows)


def test_backfill_throttles_between_days(tmp_path):
    from src.history_db import HistoryDB
    db = HistoryDB(db_path=str(tmp_path / "h.db"))
    sleeper = MagicMock()
    ing = Ingestor(_client(), db, sleep_seconds=0.01, sleeper=sleeper)
    ing.backfill(days=3, today=datetime.date(2026, 6, 10))
    assert sleeper.call_count >= 3  # pausa por dia


def test_backfill_resumes_from_latest(tmp_path):
    from src.history_db import HistoryDB
    db = HistoryDB(db_path=str(tmp_path / "h.db"))
    db.upsert_snapshot({"date": "2026-06-09", "resting_hr": 99})
    client = _client()
    ing = Ingestor(client, db, sleep_seconds=0)
    ing.backfill(days=5, today=datetime.date(2026, 6, 10))
    rows = {r["date"]: r for r in db.get_snapshots("2026-06-01", "2026-06-30")}
    assert rows["2026-06-09"]["resting_hr"] == 99
    assert "2026-06-10" in rows


def test_backfill_retries_on_rate_limit(tmp_path):
    from src.history_db import HistoryDB
    db = HistoryDB(db_path=str(tmp_path / "h.db"))
    client = _client()
    calls = {"n": 0}

    def flaky(day):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("Garmin rate limit hit — try again later")
        return _summary()

    client.get_daily_summary.side_effect = flaky
    sleeper = MagicMock()
    ing = Ingestor(client, db, sleep_seconds=0, sleeper=sleeper)
    ing.backfill(days=1, today=datetime.date(2026, 6, 10))
    rows = db.get_snapshots("2026-06-01", "2026-06-30")
    assert len(rows) == 1  # recuperou após retry


def test_sync_today_writes_one(tmp_path):
    from src.history_db import HistoryDB
    db = HistoryDB(db_path=str(tmp_path / "h.db"))
    ing = Ingestor(_client(), db, sleep_seconds=0)
    ing.sync_today(today=datetime.date(2026, 6, 10))
    rows = db.get_snapshots("2026-06-01", "2026-06-30")
    assert len(rows) == 1
    acts = db.get_activities("2026-06-01", "2026-06-30")
    assert len(acts) == 1


def _client_full():
    c = _client()  # reusa o mock base do arquivo
    c.get_training_readiness.return_value = {"score": 70}
    c.get_max_metrics.return_value = [{"generic": {"vo2MaxValue": 48.0}}]
    c.get_endurance_score.return_value = {"overallScore": 5600}
    c.get_hrv.return_value = None
    c.get_body_composition.return_value = {"dateWeightList": [
        {"weight": 80000, "bodyFat": 18.0, "muscleMass": 60000, "date": "2026-06-10"}]}
    return c


def test_sync_today_writes_metric_value_and_snapshot(tmp_path):
    from src.history_db import HistoryDB
    db = HistoryDB(db_path=str(tmp_path / "h.db"))
    ing = Ingestor(_client_full(), db, sleep_seconds=0)
    ing.sync_today(today=datetime.date(2026, 6, 10))

    snaps = db.get_snapshots("2026-06-01", "2026-06-30")
    assert len(snaps) == 1  # dual-write: snapshot legado preenchido

    metrics = {m["metric_key"]: m for m in db.get_metrics("2026-06-10")}
    assert metrics["resting_hr"]["value"] == 52
    assert metrics["steps"]["value"] == 8000
    assert metrics["vo2max"]["value"] == 48.0
    assert metrics["race_pred_5k"]["source"] == "estimado"
    assert metrics["weight_kg"]["value"] == 80.0
