from bot.core import collect_metrics, _last_night_sleep, sleep_view

def test_collect_metrics_extrai_4_chaves():
    ctx = {"resting_hr_today": 55, "resting_hr_avg_7d": 60.9,
           "morning_battery_avg": 38, "sleep_debt_hours": 2.4, "run_sessions_7d": 3,
           "extra": "ignorado"}
    m = collect_metrics(ctx)
    assert set(m) == {"resting_hr_today", "resting_hr_avg_7d",
                      "morning_battery_avg", "sleep_debt_hours", "run_sessions_7d"}
    assert m["resting_hr_today"] == 55


def test_last_night_sleep_extrai_horas():
    sleep = [{"dailySleepDTO": {"sleepTimeSeconds": 22680, "deepSleepSeconds": 2880,
                                "remSleepSeconds": 4320}}]
    s = _last_night_sleep(sleep)
    assert s["sleep_last_night_h"] == 6.3
    assert s["sleep_deep_h"] == 0.8
    assert s["sleep_rem_h"] == 1.2


def test_last_night_sleep_vazio():
    assert _last_night_sleep([]) == {}
    assert _last_night_sleep([{}]).get("sleep_last_night_h") is None


def test_sleep_view_monta_recorte():
    ctx = {"sleep_last_night_h": 6.3, "sleep_deep_h": 0.8, "sleep_debt_hours": 2.4}
    v = sleep_view(ctx)
    assert v["hours"] == 6.3 and v["debt_h"] == 2.4 and v["target"] == 7.0
