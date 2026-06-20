import datetime
from unittest.mock import MagicMock
from src.metric_reader import read_metrics


def test_read_metrics_groups_and_status():
    db = MagicMock()
    db.get_metrics.return_value = [
        {"date": "2026-06-13", "metric_key": "resting_hr", "value": 52,
         "measured_at": "2026-06-13T00:00", "source": "garmin"},
        {"date": "2026-06-13", "metric_key": "race_pred_5k", "value": 1758,
         "measured_at": "2026-06-13T00:00", "source": "estimado"},
    ]
    db.get_metric_series.return_value = [
        {"date": "2026-06-10", "metric_key": "weight_kg", "value": 80.0,
         "measured_at": "2026-06-10T07:00", "source": "garmin"}]
    payload = read_metrics(db, "2026-06-13", today=datetime.date(2026, 6, 13))

    dominios = payload["dominios"]
    rec = {m["key"]: m for m in dominios["recuperacao"]}
    assert rec["resting_hr"]["status"] == "fresco"
    assert rec["hrv_overnight"]["status"] == "ausente"
    pront = {m["key"]: m for m in dominios["prontidao"]}
    assert pront["race_pred_5k"]["status"] == "estimado"
    corpo = {m["key"]: m for m in dominios["corpo"]}
    assert corpo["weight_kg"]["value"] == 80.0
    assert corpo["weight_kg"]["status"] == "fresco"


from src.metric_reader import context_from_metrics


def test_context_from_metrics_computes_hr_avg_and_debt():
    db = MagicMock()

    def series(metric_key, start, end):
        if metric_key == "resting_hr":
            return [{"value": 50, "measured_at": f"2026-06-{6+i:02d}T00:00", "date": f"2026-06-{6+i:02d}"}
                    for i in range(7)]
        if metric_key == "sleep_hours":
            return [{"value": 6.0, "measured_at": f"2026-06-{6+i:02d}T00:00", "date": f"2026-06-{6+i:02d}"}
                    for i in range(7)]
        if metric_key == "body_battery_high":
            return [{"value": 80, "measured_at": "2026-06-13T00:00", "date": "2026-06-13"}]
        return []

    db.get_metric_series.side_effect = series
    db.get_activities.return_value = [
        {"date": "2026-06-12", "type": "running", "is_strength": 0},
        {"date": "2026-06-11", "type": "strength_training", "is_strength": 1},
    ]
    ctx = context_from_metrics(db, "2026-06-13", today=datetime.date(2026, 6, 13))
    assert ctx["resting_hr_today"] == 50
    assert ctx["resting_hr_avg_7d"] == 50.0
    assert ctx["sleep_debt_hours"] == 7.0
    assert ctx["morning_battery_avg"] == 80
    assert ctx["run_sessions_7d"] == 1


def test_context_inclui_sinais_novos(tmp_path):
    import datetime
    from src.history_db import HistoryDB
    from src.metric_reader import context_from_metrics
    db = HistoryDB(str(tmp_path / "c.db"))
    db.upsert_metric("2026-06-20", "acwr", 1.4, "2026-06-20T10:00:00", "computed")
    db.upsert_metric("2026-06-20", "soreness", 3, "2026-06-20T07:00:00", "manual")
    db.upsert_metric("2026-06-20", "resting_hr_baseline", 51.0, "2026-06-20T08:00:00", "computed")
    ctx = context_from_metrics(db, "2026-06-20", today=datetime.date(2026, 6, 20))
    assert ctx["acwr"] == 1.4
    assert ctx["soreness"] == 3
    assert ctx["resting_hr_baseline"] == 51.0
    assert ctx["energia"] is None        # ausente -> None
