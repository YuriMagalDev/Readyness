from unittest.mock import patch
from src.health_monitor import HealthMonitor

BASE_CONTEXT = {
    "resting_hr_avg_7d": 52.0,
    "morning_battery_avg": 60.0,
    "sleep_debt_hours": 0.0,
    "recent_activities": [],
    "strength_sessions_7d": 2,
    "run_sessions_7d": 3,
}

MOCK_RESPONSE = '{"status": "verde", "motivo": "Tudo normal", "recomendacao": "Pode treinar"}'

def make_context(**overrides):
    return {**BASE_CONTEXT, **overrides}

def test_green_status():
    monitor = HealthMonitor()
    result = monitor._evaluate_rules(make_context())
    assert result["status"] == "verde"

def test_red_status_high_hr():
    monitor = HealthMonitor()
    result = monitor._evaluate_rules(
        make_context(resting_hr_today=58, resting_hr_avg_7d=52)
    )
    assert result["status"] == "vermelho"

def test_yellow_status_low_battery():
    monitor = HealthMonitor()
    result = monitor._evaluate_rules(make_context(morning_battery_avg=20))
    assert result["status"] == "amarelo"

def test_yellow_status_sleep_debt():
    monitor = HealthMonitor()
    result = monitor._evaluate_rules(make_context(sleep_debt_hours=2.5))
    assert result["status"] == "amarelo"

@patch("src.health_monitor.ask_coach", return_value=MOCK_RESPONSE)
def test_check_calls_haiku(mock_ask):
    monitor = HealthMonitor()
    result = monitor.check(make_context())
    mock_ask.assert_called_once()
    call_kwargs = mock_ask.call_args
    assert call_kwargs[1].get("depth") == "quick" or call_kwargs[0][2] == "quick"
    assert result["status"] in ("verde", "amarelo", "vermelho")


def test_verdict_is_deterministic_no_llm():
    from src.health_monitor import HealthMonitor
    ctx = {"resting_hr_today": 60, "resting_hr_avg_7d": 50,
           "morning_battery_avg": 80, "sleep_debt_hours": 0}
    out = HealthMonitor().verdict(ctx)
    assert out["status"] == "vermelho"
    assert "FC repouso" in out["motivo"]


def test_verdict_green_when_normal():
    from src.health_monitor import HealthMonitor
    ctx = {"resting_hr_today": 50, "resting_hr_avg_7d": 50,
           "morning_battery_avg": 80, "sleep_debt_hours": 0}
    assert HealthMonitor().verdict(ctx)["status"] == "verde"
