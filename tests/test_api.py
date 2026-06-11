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


def test_sync_route():
    with patch("api.main.GarminClient"), patch("api.main.get_db"), \
         patch("api.main.Ingestor") as MockIng:
        MockIng.return_value.sync_today.return_value = None
        from api.main import app
        resp = TestClient(app).post("/api/sync")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
