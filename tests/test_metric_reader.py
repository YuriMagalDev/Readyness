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
