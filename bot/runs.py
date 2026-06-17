RUN_TYPES = {"running", "treadmill_running", "trail_running"}


def _type_of(act: dict) -> str:
    """typeKey, aceitando tanto o raw do Garmin quanto a row do DB (snake_case)."""
    return act.get("type") or (act.get("activityType") or {}).get("typeKey") or ""


def is_run(act: dict) -> bool:
    return _type_of(act) in RUN_TYPES


def filter_runs(activities: list) -> list:
    """Só corridas, preservando a ordem de entrada (Garmin já vem da mais recente)."""
    return [a for a in (activities or []) if is_run(a)]
