STRENGTH_ACTIVITY_TYPES = {"strength_training", "indoor_cardio"}


def _pace_min_km(speed_m_s):
    if not speed_m_s or speed_m_s <= 0:
        return None
    return (1000 / speed_m_s) / 60


def snapshot_from_garmin(day, summary, race, runs, strength, train_minutes) -> dict:
    summary = summary or {}
    race = race or {}

    moderate = summary.get("moderateIntensityMinutes")
    vigorous = summary.get("vigorousIntensityMinutes")
    intensity = None
    if moderate is not None or vigorous is not None:
        intensity = (moderate or 0) + (vigorous or 0)

    sleep_secs = summary.get("measurableAsleepDuration")
    sleep_hours = round(sleep_secs / 3600, 1) if sleep_secs else None

    return {
        "date": day,
        "resting_hr": summary.get("restingHeartRate"),
        "sleep_hours": sleep_hours,
        "sleep_score": None,  # FR55 não fornece score numérico de sono
        "body_battery_high": summary.get("bodyBatteryHighestValue"),
        "body_battery_low": summary.get("bodyBatteryLowestValue"),
        "stress_avg": summary.get("averageStressLevel"),
        "stress_max": summary.get("maxStressLevel"),
        "respiration_avg": summary.get("avgWakingRespirationValue"),
        "spo2_avg": summary.get("averageSpo2"),
        "intensity_minutes": intensity,
        "steps": summary.get("totalSteps"),
        "floors": summary.get("floorsAscended"),
        "calories_total": summary.get("totalKilocalories"),
        "calories_active": summary.get("activeKilocalories"),
        "race_pred_5k": race.get("time5K"),
        "race_pred_10k": race.get("time10K"),
        "race_pred_21k": race.get("timeHalfMarathon"),
        "race_pred_42k": race.get("timeMarathon"),
        "runs": runs,
        "strength": strength,
        "train_minutes": train_minutes,
    }


def activity_from_garmin(act: dict) -> dict:
    type_key = act.get("activityType", {}).get("typeKey", "")
    duration = act.get("duration")
    return {
        "activity_id": act.get("activityId"),
        "date": act.get("startTimeLocal", "")[:10],
        "name": act.get("activityName", ""),
        "type": type_key,
        "is_strength": 1 if type_key in STRENGTH_ACTIVITY_TYPES else 0,
        "distance_m": act.get("distance"),
        "duration_min": round(duration / 60, 1) if duration else None,
        "pace_min_km": _pace_min_km(act.get("averageSpeed")),
        "avg_hr": act.get("averageHR"),
        "max_hr": act.get("maxHR"),
        "calories": act.get("calories"),
        "cadence": act.get("averageRunningCadenceInStepsPerMinute"),
        "stride_length": act.get("avgStrideLength"),
    }


def splits_from_garmin(raw: dict) -> list:
    laps = (raw or {}).get("lapDTOs", []) or []
    out = []
    for lap in laps:
        out.append({
            "distance_m": lap.get("distance"),
            "duration_s": lap.get("duration"),
            "pace_min_km": _pace_min_km(lap.get("averageSpeed")),
            "avg_hr": lap.get("averageHR"),
            "cadence": lap.get("averageRunCadence"),
        })
    return out
