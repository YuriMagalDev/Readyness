def _row(key, value, day, source="garmin"):
    return {"metric_key": key, "value": value, "measured_at": f"{day}T00:00", "source": source}


def _vo2max(max_metrics):
    if not max_metrics or not isinstance(max_metrics, list):
        return None
    return (max_metrics[0] or {}).get("generic", {}).get("vo2MaxValue")


def normalize_prontidao(day, readiness, max_metrics, endurance, race) -> list:
    rows = []
    garmin_vals = [
        ("training_readiness", (readiness or {}).get("score") if readiness else None),
        ("vo2max", _vo2max(max_metrics)),
        ("endurance_score", (endurance or {}).get("overallScore") if endurance else None),
    ]
    for key, val in garmin_vals:
        if val is not None:
            rows.append(_row(key, val, day))

    race = race or {}
    race_vals = [
        ("race_pred_5k", race.get("time5K")),
        ("race_pred_10k", race.get("time10K")),
        ("race_pred_21k", race.get("timeHalfMarathon")),
        ("race_pred_42k", race.get("timeMarathon")),
    ]
    for key, val in race_vals:
        if val is not None:
            rows.append(_row(key, val, day, source="estimado"))
    return rows
