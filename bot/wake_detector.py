import datetime as _dt


def wake_time_local(sleep_day: dict):
    """Hora de acordar 'HH:MM' a partir do DTO de sono, ou None se ainda não há.
    Os timestamps *Local do Garmin vêm em ms já no fuso local (tratar como UTC)."""
    if not sleep_day:
        return None
    dto = sleep_day.get("dailySleepDTO") or {}
    ts = dto.get("sleepEndTimestampLocal")
    if not ts:
        return None
    return _dt.datetime.fromtimestamp(ts / 1000, _dt.timezone.utc).strftime("%H:%M")


def woke_up_today(sleep_day: dict) -> bool:
    return wake_time_local(sleep_day) is not None
