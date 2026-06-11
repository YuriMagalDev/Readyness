from src.analytics import Analytics


def _snaps():
    # 14 dias: FC subindo de 50 a 56
    rows = []
    for i in range(14):
        rows.append({
            "date": f"2026-06-{i+1:02d}",
            "resting_hr": 50 + i * 0.5,
            "sleep_hours": 7.0,
            "stress_avg": 30,
            "body_battery_high": 90,
            "intensity_minutes": 30,
            "race_pred_5k": 1800 - i,  # melhorando
        })
    return rows


def test_series_extracts_metric():
    a = Analytics()
    s = a.series(_snaps(), "resting_hr")
    assert len(s) == 14
    assert s[0]["valor"] == 50
    assert s[0]["data"] == "2026-06-01"


def test_series_skips_none():
    a = Analytics()
    rows = [{"date": "2026-06-01", "resting_hr": None}, {"date": "2026-06-02", "resting_hr": 52}]
    s = a.series(rows, "resting_hr")
    assert len(s) == 2
    assert s[0]["valor"] is None


def test_trend_rising():
    a = Analytics()
    t = a.trend(_snaps(), "resting_hr")
    assert t["direction"] == "subindo"
    assert t["slope"] > 0


def test_trend_falling_race_pred():
    a = Analytics()
    t = a.trend(_snaps(), "race_pred_5k")
    assert t["direction"] == "descendo"  # tempo caindo = melhora


def test_trend_stable():
    a = Analytics()
    rows = [{"date": f"2026-06-{i+1:02d}", "stress_avg": 30} for i in range(14)]
    t = a.trend(rows, "stress_avg")
    assert t["direction"] == "estável"


def test_trend_insufficient_data():
    a = Analytics()
    t = a.trend([{"date": "2026-06-01", "resting_hr": 50}], "resting_hr")
    assert t["direction"] == "estável"
    assert t["slope"] == 0.0


def test_summary_bundles_metrics():
    a = Analytics()
    out = a.summary(_snaps())
    assert "resting_hr" in out
    assert out["resting_hr"]["trend"]["direction"] == "subindo"
    assert len(out["resting_hr"]["series"]) == 14
