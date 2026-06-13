def _row(key, value, day):
    return {"metric_key": key, "value": value, "measured_at": f"{day}T00:00", "source": "garmin"}


def normalize_atividade(day, summary) -> list:
    summary = summary or {}
    moderate = summary.get("moderateIntensityMinutes")
    vigorous = summary.get("vigorousIntensityMinutes")
    intensity = None
    if moderate is not None or vigorous is not None:
        intensity = (moderate or 0) + (vigorous or 0)

    candidates = [
        ("steps", summary.get("totalSteps")),
        ("floors", summary.get("floorsAscended")),
        ("intensity_minutes", intensity),
        ("calories_total", summary.get("totalKilocalories")),
    ]
    return [_row(k, v, day) for k, v in candidates if v is not None]
