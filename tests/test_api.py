from unittest.mock import MagicMock, patch
from api import services


def _fake_client():
    client = MagicMock()
    client.get_activities.return_value = [{
        "activityType": {"typeKey": "running"},
        "duration": 2520, "averageHR": 150,
        "startTimeLocal": "2026-06-10 07:00:00", "activityName": "Corrida",
    }]
    client.get_heart_rate_stats.return_value = [{"restingHeartRate": 52}] * 14
    client.get_sleep.return_value = [{"dailySleepDTO": {"sleepTimeSeconds": 25200}}] * 14
    client.get_body_battery.return_value = [[{"charged": 65, "drained": 0}]] * 14
    return client


def test_build_today_payload():
    client = _fake_client()
    with patch("api.services.HealthMonitor") as MockMon:
        MockMon.return_value.check.return_value = {
            "status": "verde", "motivo": "ok", "recomendacao": "treine"
        }
        payload = services.build_today(client)
    assert payload["status"] == "verde"
    assert "metrics" in payload
    assert payload["metrics"]["resting_hr_avg_7d"] == 52.0


def test_build_data_payload_has_trends():
    client = _fake_client()
    payload = services.build_data(client)
    assert "fc_series" in payload
    assert "fc_trend" in payload
    # 14 pontos → weekly_trend computa label (não vazio)
    assert payload["fc_trend"]["label"] != ""
    assert payload["battery_trend"]["label"] != ""
    assert "atividades" in payload
    assert isinstance(payload["atividades"], list)


def test_build_plan_payload():
    client = _fake_client()
    with patch("api.services.TrainingPlanner") as MockPlanner:
        MockPlanner.return_value.generate_weekly_plan.return_value = {
            "corrida": [{"dia": "Seg", "descricao": "x", "duracao": 40, "intensidade": "leve"}],
            "musculacao": [],
        }
        payload = services.build_plan(client)
    assert "corrida" in payload
    assert "musculacao" in payload


from fastapi.testclient import TestClient


def test_today_route():
    with patch("api.main.GarminClient") as MockClient, \
         patch("api.main.services.build_today", return_value={"status": "verde", "metrics": {}}):
        from api.main import app
        resp = TestClient(app).get("/api/today")
    assert resp.status_code == 200
    assert resp.json()["status"] == "verde"


def test_plan_route():
    with patch("api.main.GarminClient"), \
         patch("api.main.services.build_plan", return_value={"corrida": [], "musculacao": []}):
        from api.main import app
        resp = TestClient(app).post("/api/plan")
    assert resp.status_code == 200
    assert "corrida" in resp.json()


def test_today_route_garmin_error_returns_503():
    with patch("api.main.GarminClient"), \
         patch("api.main.services.build_today", side_effect=RuntimeError("auth failed")):
        from api.main import app
        resp = TestClient(app).get("/api/today")
    assert resp.status_code == 503
    assert "erro" in resp.json()


from unittest.mock import MagicMock as _MM


def _hist_with_snapshots():
    db = _MM()
    db.get_snapshots.return_value = [
        {"date": f"2026-06-{i+1:02d}", "resting_hr": 50 + i, "sleep_hours": 7,
         "stress_avg": 30, "body_battery_high": 90, "intensity_minutes": 30,
         "race_pred_5k": 1800} for i in range(14)
    ]
    db.get_activities.return_value = [
        {"activity_id": 1, "date": "2026-06-10", "name": "Corrida", "type": "running",
         "is_strength": 0, "pace_min_km": 5.0, "avg_hr": 150, "duration_min": 25,
         "distance_m": 5000, "splits_json": None}
    ]
    db.get_activity.return_value = {
        "activity_id": 1, "date": "2026-06-10", "name": "Corrida", "type": "running",
        "is_strength": 0, "pace_min_km": 5.0, "avg_hr": 150, "duration_min": 25,
        "distance_m": 5000, "splits_json": None,
    }
    return db


def test_build_trends():
    db = _hist_with_snapshots()
    with patch("api.services.InsightEngine") as MockEng:
        MockEng.return_value.trend_insights.return_value = ["obs1", "obs2"]
        payload = services.build_trends(db, period=14)
    assert "metrics" in payload
    assert "insights" in payload
    assert payload["insights"] == ["obs1", "obs2"]
    assert "resting_hr" in payload["metrics"]


def test_build_activities_list():
    db = _hist_with_snapshots()
    payload = services.build_activities(db, period=30)
    assert isinstance(payload, list)
    assert payload[0]["name"] == "Corrida"


def test_build_activity_detail_fetches_splits_if_missing():
    db = _hist_with_snapshots()
    client = MagicMock()
    client.get_activity_splits.return_value = {"lapDTOs": [
        {"distance": 1000, "duration": 300, "averageSpeed": 3.33, "averageHR": 150, "averageRunCadence": 160}
    ]}
    with patch("api.services.InsightEngine") as MockEng:
        MockEng.return_value.activity_insight.return_value = "bom pace"
        payload = services.build_activity_detail(db, client, 1)
    assert payload["splits"][0]["distance_m"] == 1000
    assert payload["insight"] == "bom pace"
    client.get_activity_splits.assert_called_once_with(1)


def test_param_deltas_computes_direction():
    snaps = [
        {"date": "2026-06-10", "body_battery_high": 30, "stress_avg": 45, "calories_total": 3700},
        {"date": "2026-06-11", "body_battery_high": 39, "stress_avg": 41, "calories_total": 3400},
    ]
    out = services._param_deltas(snaps)
    bat = next(p for p in out if p["label"] == "Body Battery")
    assert bat["valor"] == 39
    assert bat["delta"] == 9
    assert bat["direcao"] == "subiu"
    stress = next(p for p in out if p["label"] == "Stress médio")
    assert stress["direcao"] == "desceu"
    assert stress["bom"] is True  # stress caindo é bom


def test_param_deltas_single_day_no_delta():
    snaps = [{"date": "2026-06-11", "body_battery_high": 39, "stress_avg": 41, "calories_total": 3400}]
    out = services._param_deltas(snaps)
    assert out[0]["delta"] is None
    assert out[0]["direcao"] == "estável"


def test_param_deltas_includes_new_metrics():
    snaps = [
        {"date": "2026-06-10", "steps": 8000, "sleep_hours": 7.0, "intensity_minutes": 30},
        {"date": "2026-06-11", "steps": 10000, "sleep_hours": 6.5, "intensity_minutes": 45},
    ]
    out = services._param_deltas(snaps)
    passos = next(p for p in out if p["label"] == "Passos")
    assert passos["valor"] == 10000
    assert passos["valor_fmt"] == "10000"
    assert passos["delta_fmt"] == "+2000"
    sono = next(p for p in out if p["label"] == "Sono")
    assert sono["valor_fmt"] == "6.5 h"


def test_param_deltas_formats_race_prediction_as_time():
    # 5k em 1500s = 25:00, dia anterior 1530s = 25:30 → melhorou 30s
    snaps = [
        {"date": "2026-06-10", "race_pred_5k": 1530},
        {"date": "2026-06-11", "race_pred_5k": 1500},
    ]
    out = services._param_deltas(snaps)
    prova = next(p for p in out if p["label"] == "Prova 5k")
    assert prova["valor_fmt"] == "25:00"
    assert prova["delta_fmt"] == "-0:30"
    assert prova["bom"] is True  # tempo caindo é bom


def test_build_today_overrides_resting_hr_from_snapshot():
    client = _fake_client()
    db = _hist_with_snapshots()
    # snapshot mais recente tem resting_hr = 50 + 13 = 63
    db.get_snapshots.return_value = [{"date": "2026-06-12", "resting_hr": 48}]
    with patch("api.services.HealthMonitor") as MockMon, \
         patch("api.services.InsightEngine") as MockEng:
        MockMon.return_value.check.return_value = {
            "status": "verde", "motivo": "ok", "recomendacao": "x"}
        MockEng.return_value.daily_insight.return_value = "ins"
        payload = services.build_today(client, db)
    assert payload["metrics"]["resting_hr_today"] == 48


def test_build_plan_saves_to_db():
    client = _fake_client()
    db = _MM()
    db.get_plan.return_value = None
    with patch("api.services.TrainingPlanner") as MockPlanner:
        MockPlanner.return_value.generate_weekly_plan.return_value = {"corrida": [], "musculacao": []}
        services.build_plan(client, db)
    db.upsert_plan.assert_called_once()


def test_build_plan_status_no_saved_plan():
    db = _MM()
    db.get_plan.return_value = None
    import datetime
    out = services.build_plan_status(db, today=datetime.date(2026, 6, 11))
    assert out["plan"] is None
    assert out["week_start"] == "2026-06-08"


def test_build_plan_status_matches_activities():
    import datetime
    db = _MM()
    db.get_plan.return_value = {
        "plan": {"corrida": [{"dia": "Segunda", "descricao": "x", "duracao": 40, "intensidade": "leve"}],
                 "musculacao": []},
        "created_at": "2026-06-08",
    }
    db.get_activities.return_value = [{"date": "2026-06-08", "type": "running", "is_strength": 0}]
    out = services.build_plan_status(db, today=datetime.date(2026, 6, 10))
    assert out["match"]["corrida"][0]["status"] == "feito"


def test_plan_status_route():
    with patch("api.main.get_db"), \
         patch("api.main.services.build_plan_status", return_value={"plan": None, "match": None, "week_start": "2026-06-08"}):
        from api.main import app
        resp = TestClient(app).get("/api/plan")
    assert resp.status_code == 200
    assert resp.json()["plan"] is None


def test_trends_route():
    with patch("api.main.GarminClient"), patch("api.main.get_db"), \
         patch("api.main.services.build_trends", return_value={"metrics": {}, "insights": []}):
        from api.main import app
        resp = TestClient(app).get("/api/trends?period=30")
    assert resp.status_code == 200
    assert "insights" in resp.json()


def test_activities_route():
    with patch("api.main.GarminClient"), patch("api.main.get_db"), \
         patch("api.main.services.build_activities", return_value=[{"name": "Corrida"}]):
        from api.main import app
        resp = TestClient(app).get("/api/activities?period=30")
    assert resp.status_code == 200
    assert resp.json()[0]["name"] == "Corrida"


def test_activity_detail_route():
    with patch("api.main.GarminClient"), patch("api.main.get_db"), \
         patch("api.main.services.build_activity_detail",
               return_value={"activity": {}, "splits": [], "insight": "ok"}):
        from api.main import app
        resp = TestClient(app).get("/api/activity/1")
    assert resp.status_code == 200
    assert resp.json()["insight"] == "ok"


def test_build_today_passes_db_to_engine_and_force():
    client = _fake_client()
    db = _hist_with_snapshots()
    with patch("api.services.HealthMonitor") as MockMon, \
         patch("api.services.InsightEngine") as MockEng:
        MockMon.return_value.check.return_value = {
            "status": "verde", "motivo": "ok", "recomendacao": "x"}
        MockEng.return_value.daily_insight.return_value = "ins"
        services.build_today(client, db, force=True)
    MockEng.assert_called_once_with(db=db)
    assert MockEng.return_value.daily_insight.call_args[1]["force"] is True


def test_build_trends_passes_force():
    db = _hist_with_snapshots()
    with patch("api.services.InsightEngine") as MockEng:
        MockEng.return_value.trend_insights.return_value = ["a"]
        services.build_trends(db, period=14, force=True)
    assert MockEng.return_value.trend_insights.call_args[1]["force"] is True
    assert MockEng.return_value.trend_insights.call_args[1]["period"] == 14


def test_sync_route():
    with patch("api.main.GarminClient"), patch("api.main.get_db"), \
         patch("api.main.Ingestor") as MockIng:
        MockIng.return_value.sync_today.return_value = None
        from api.main import app
        resp = TestClient(app).post("/api/sync")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


def test_sync_garmin_route_clears_cache():
    with patch("api.main.GarminClient") as MockClient, patch("api.main.get_db"):
        MockClient.return_value.clear_cache.return_value = None
        from api.main import app
        resp = TestClient(app).post("/api/sync/garmin")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


def test_sync_insights_route_hoje():
    with patch("api.main.GarminClient"), patch("api.main.get_db"), \
         patch("api.main.services.build_today", return_value={"status": "verde"}) as mock_bt:
        from api.main import app
        resp = TestClient(app).post("/api/sync/insights", json={"page": "hoje"})
    assert resp.status_code == 200
    assert mock_bt.call_args[1]["force"] is True


import datetime as _dt2


def test_build_metrics_groups_and_status():
    db = _MM()
    db.get_metrics.return_value = [
        {"date": "2026-06-13", "metric_key": "resting_hr", "value": 52,
         "measured_at": "2026-06-13T00:00", "source": "garmin"},
        {"date": "2026-06-13", "metric_key": "race_pred_5k", "value": 1758,
         "measured_at": "2026-06-13T00:00", "source": "estimado"},
    ]
    db.get_metric_series.return_value = [
        {"date": "2026-06-10", "metric_key": "weight_kg", "value": 80.0,
         "measured_at": "2026-06-10T07:00", "source": "garmin"}]
    payload = services.build_metrics(db, "2026-06-13", today=_dt2.date(2026, 6, 13))

    dominios = payload["dominios"]
    rec = {m["key"]: m for m in dominios["recuperacao"]}
    assert rec["resting_hr"]["status"] == "fresco"
    assert rec["hrv_overnight"]["status"] == "ausente"
    pront = {m["key"]: m for m in dominios["prontidao"]}
    assert pront["race_pred_5k"]["status"] == "estimado"
    corpo = {m["key"]: m for m in dominios["corpo"]}
    assert corpo["weight_kg"]["value"] == 80.0
    assert corpo["weight_kg"]["status"] == "fresco"
    assert corpo["weight_kg"]["measured_at"] == "2026-06-10T07:00"


def test_sync_insights_route_trends():
    with patch("api.main.get_db"), \
         patch("api.main.services.build_trends", return_value={"insights": []}) as mock_bt:
        from api.main import app
        resp = TestClient(app).post("/api/sync/insights", json={"page": "trends", "period": 14})
    assert resp.status_code == 200
    assert mock_bt.call_args[1]["force"] is True
    assert mock_bt.call_args[1]["period"] == 14
