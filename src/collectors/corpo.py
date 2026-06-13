def normalize_corpo(day, body) -> list:
    entries = (body or {}).get("dateWeightList") or []
    if not entries:
        return []
    e = entries[-1]  # pesagem mais recente do período
    measured_at = e.get("date", day)
    rows = []
    candidates = [
        ("weight_kg", _grams_to_kg(e.get("weight"))),
        ("body_fat_pct", e.get("bodyFat")),
        ("lean_mass_kg", _grams_to_kg(e.get("muscleMass"))),
    ]
    for key, val in candidates:
        if val is not None:
            rows.append({"metric_key": key, "value": val,
                         "measured_at": measured_at, "source": "garmin"})
    return rows


def _grams_to_kg(grams):
    return round(grams / 1000, 1) if grams else None
