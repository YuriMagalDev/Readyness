def _row(key, value, day):
    return {"metric_key": key, "value": value, "measured_at": f"{day}T00:00", "source": "garmin"}


def _hours(seconds):
    return round(seconds / 3600, 1) if seconds else None


def normalize_recuperacao(day, summary, sleep, hrv) -> list:
    summary = summary or {}
    sleep_dto = (sleep or {}).get("dailySleepDTO", {}) or {}
    rows = []

    simple = [
        ("resting_hr", summary.get("restingHeartRate")),
        ("stress_avg", summary.get("averageStressLevel")),
        ("stress_max", summary.get("maxStressLevel")),
        ("spo2_avg", summary.get("averageSpo2")),
        ("body_battery_high", summary.get("bodyBatteryHighestValue")),
        ("body_battery_low", summary.get("bodyBatteryLowestValue")),
        ("respiration_avg", summary.get("avgWakingRespirationValue")),
    ]
    sleep_metrics = [
        ("sleep_hours", _hours(sleep_dto.get("sleepTimeSeconds"))),
        ("sleep_deep_h", _hours(sleep_dto.get("deepSleepSeconds"))),
        ("sleep_light_h", _hours(sleep_dto.get("lightSleepSeconds"))),
        ("sleep_rem_h", _hours(sleep_dto.get("remSleepSeconds"))),
    ]
    hrv_val = (hrv or {}).get("hrvSummary", {}).get("lastNightAvg") if hrv else None
    extra = [("hrv_overnight", hrv_val)]

    for key, val in simple + sleep_metrics + extra:
        if val is not None:
            rows.append(_row(key, val, day))
    return rows
