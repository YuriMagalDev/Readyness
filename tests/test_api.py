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
    client.get_body_battery.return_value = [[{"charged": 65, "drained": 0}]] * 7
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
