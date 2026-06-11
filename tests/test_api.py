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
