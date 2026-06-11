from src.extractors import snapshot_from_garmin, activity_from_garmin, splits_from_garmin

SUMMARY = {
    "restingHeartRate": 52, "totalSteps": 8000, "floorsAscended": 12,
    "totalKilocalories": 2200, "activeKilocalories": 600,
    "moderateIntensityMinutes": 30, "vigorousIntensityMinutes": 10,
    "averageStressLevel": 35, "maxStressLevel": 80,
    "avgWakingRespirationValue": 14.5, "averageSpo2": 96,
    "bodyBatteryHighestValue": 90, "bodyBatteryLowestValue": 20,
    "measurableAsleepDuration": 25200,  # 7h de sono medido
}
RACE = {"time5K": 1758, "time10K": 3700, "timeHalfMarathon": 8200, "timeMarathon": 17000}


def test_snapshot_basic_fields():
    row = snapshot_from_garmin("2026-06-10", SUMMARY, RACE, runs=2, strength=1, train_minutes=95)
    assert row["date"] == "2026-06-10"
    assert row["resting_hr"] == 52
    assert row["steps"] == 8000
    assert row["intensity_minutes"] == 40  # moderate + vigorous
    assert row["sleep_hours"] == 7.0
    assert row["stress_avg"] == 35
    assert row["spo2_avg"] == 96
    assert row["body_battery_high"] == 90
    assert row["race_pred_5k"] == 1758
    assert row["runs"] == 2
    assert row["strength"] == 1
    assert row["train_minutes"] == 95


def test_snapshot_handles_missing_summary():
    row = snapshot_from_garmin("2026-06-10", {}, None, runs=0, strength=0, train_minutes=0)
    assert row["date"] == "2026-06-10"
    assert row["resting_hr"] is None
    assert row["intensity_minutes"] is None
    assert row["sleep_hours"] is None
    assert row["race_pred_5k"] is None


def test_activity_pace_and_fields():
    act = {
        "activityId": 99, "activityName": "Corrida", "startTimeLocal": "2026-06-10 07:00:00",
        "activityType": {"typeKey": "running"}, "distance": 5000.0, "duration": 1500.0,
        "averageSpeed": 3.333, "averageHR": 150, "maxHR": 170, "calories": 400,
        "averageRunningCadenceInStepsPerMinute": 160,
    }
    row = activity_from_garmin(act)
    assert row["activity_id"] == 99
    assert row["type"] == "running"
    assert row["is_strength"] == 0
    assert row["distance_m"] == 5000.0
    assert row["duration_min"] == 25.0
    assert round(row["pace_min_km"], 2) == 5.0  # 3.333 m/s → 5 min/km
    assert row["avg_hr"] == 150


def test_activity_strength_flagged():
    act = {"activityId": 1, "activityName": "Força", "startTimeLocal": "2026-06-09 18:00:00",
           "activityType": {"typeKey": "indoor_cardio"}, "duration": 3600.0}
    row = activity_from_garmin(act)
    assert row["is_strength"] == 1
    assert row["pace_min_km"] is None  # sem averageSpeed


def test_splits_json_shape():
    raw = {"lapDTOs": [
        {"distance": 1000, "duration": 300, "averageSpeed": 3.333, "averageHR": 150, "averageRunCadence": 160},
        {"distance": 1000, "duration": 310, "averageSpeed": 3.22, "averageHR": 155, "averageRunCadence": 158},
    ]}
    splits = splits_from_garmin(raw)
    assert len(splits) == 2
    assert splits[0]["distance_m"] == 1000
    assert round(splits[0]["pace_min_km"], 2) == 5.0
    assert splits[0]["avg_hr"] == 150
