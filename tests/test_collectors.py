from src.collectors.recuperacao import normalize_recuperacao
from src.collectors.atividade import normalize_atividade
from src.collectors.prontidao import normalize_prontidao

DAY = "2026-06-13"


def _summary():
    return {"restingHeartRate": 52, "averageStressLevel": 30, "maxStressLevel": 75,
            "averageSpo2": 96, "bodyBatteryHighestValue": 90, "bodyBatteryLowestValue": 20,
            "avgWakingRespirationValue": 14}


def _sleep():
    return {"dailySleepDTO": {"sleepTimeSeconds": 25200, "deepSleepSeconds": 5400,
            "lightSleepSeconds": 14400, "remSleepSeconds": 5400}}


def test_recuperacao_extracts_core_metrics():
    rows = normalize_recuperacao(DAY, summary=_summary(), sleep=_sleep(),
                                 hrv=None)
    by_key = {r["metric_key"]: r for r in rows}
    assert by_key["resting_hr"]["value"] == 52
    assert by_key["resting_hr"]["source"] == "garmin"
    assert by_key["resting_hr"]["measured_at"] == "2026-06-13T00:00"
    assert by_key["sleep_hours"]["value"] == 7.0
    assert by_key["sleep_deep_h"]["value"] == 1.5
    assert by_key["stress_avg"]["value"] == 30
    assert by_key["spo2_avg"]["value"] == 96
    assert by_key["body_battery_high"]["value"] == 90


def test_recuperacao_skips_missing_fields():
    rows = normalize_recuperacao(DAY, summary={}, sleep={}, hrv=None)
    assert rows == []


def test_recuperacao_hrv_when_present():
    rows = normalize_recuperacao(DAY, summary={}, sleep={},
                                 hrv={"hrvSummary": {"lastNightAvg": 42}})
    by_key = {r["metric_key"]: r for r in rows}
    assert by_key["hrv_overnight"]["value"] == 42


def test_atividade_extracts_daily_metrics():
    summary = {"totalSteps": 8000, "floorsAscended": 5,
               "moderateIntensityMinutes": 20, "vigorousIntensityMinutes": 5,
               "totalKilocalories": 2200}
    rows = normalize_atividade(DAY, summary)
    by_key = {r["metric_key"]: r for r in rows}
    assert by_key["steps"]["value"] == 8000
    assert by_key["floors"]["value"] == 5
    assert by_key["intensity_minutes"]["value"] == 25  # moderate + vigorous
    assert by_key["calories_total"]["value"] == 2200
    assert by_key["steps"]["measured_at"] == "2026-06-13T00:00"


def test_atividade_intensity_none_when_both_absent():
    rows = normalize_atividade(DAY, {"totalSteps": 100})
    keys = {r["metric_key"] for r in rows}
    assert "intensity_minutes" not in keys
    assert "steps" in keys


def test_prontidao_extracts_metrics():
    rows = normalize_prontidao(
        DAY,
        readiness={"score": 72},
        max_metrics=[{"generic": {"vo2MaxValue": 48.0}}],
        endurance={"overallScore": 5600},
        race={"time5K": 1758, "time10K": 3700,
              "timeHalfMarathon": 8200, "timeMarathon": 17000},
    )
    by_key = {r["metric_key"]: r for r in rows}
    assert by_key["training_readiness"]["value"] == 72
    assert by_key["vo2max"]["value"] == 48.0
    assert by_key["endurance_score"]["value"] == 5600
    assert by_key["race_pred_5k"]["value"] == 1758
    assert by_key["race_pred_5k"]["source"] == "estimado"
    assert by_key["vo2max"]["source"] == "garmin"


def test_prontidao_skips_missing():
    rows = normalize_prontidao(DAY, readiness=None, max_metrics=None,
                               endurance=None, race=None)
    assert rows == []


from src.collectors.corpo import normalize_corpo


def test_corpo_extracts_weight_with_real_measured_at():
    body = {"dateWeightList": [{
        "weight": 80500, "bodyFat": 18.5, "muscleMass": 60000,
        "date": "2026-06-13", "timestampGMT": 1781000000000,
    }]}
    rows = normalize_corpo(DAY, body)
    by_key = {r["metric_key"]: r for r in rows}
    assert by_key["weight_kg"]["value"] == 80.5      # gramas → kg
    assert by_key["body_fat_pct"]["value"] == 18.5
    assert by_key["lean_mass_kg"]["value"] == 60.0
    assert by_key["weight_kg"]["measured_at"].startswith("2026-06-13")


def test_corpo_empty_when_no_weigh_in():
    assert normalize_corpo(DAY, {"dateWeightList": []}) == []
    assert normalize_corpo(DAY, None) == []
