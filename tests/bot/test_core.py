from bot.core import collect_metrics

def test_collect_metrics_extrai_4_chaves():
    ctx = {"resting_hr_today": 55, "resting_hr_avg_7d": 60.9,
           "morning_battery_avg": 38, "sleep_debt_hours": 2.4, "run_sessions_7d": 3,
           "extra": "ignorado"}
    m = collect_metrics(ctx)
    assert set(m) == {"resting_hr_today", "resting_hr_avg_7d",
                      "morning_battery_avg", "sleep_debt_hours", "run_sessions_7d"}
    assert m["resting_hr_today"] == 55
