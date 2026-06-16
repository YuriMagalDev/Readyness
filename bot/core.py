from src.data_processor import DataProcessor
from src.daily_analysis import DailyAnalysis

_KEYS = ("resting_hr_today", "resting_hr_avg_7d", "morning_battery_avg",
         "sleep_debt_hours", "run_sessions_7d")


def collect_metrics(context: dict) -> dict:
    return {k: context.get(k) for k in _KEYS}


def _last_night_sleep(sleep_data: list) -> dict:
    """Horas da última noite (mais recente = índice 0) a partir do DTO de sono."""
    if not sleep_data:
        return {}
    dto = (sleep_data[0] or {}).get("dailySleepDTO") or {}

    def _h(sec):
        return round(sec / 3600, 2) if sec else None

    return {
        "sleep_last_night_h": _h(dto.get("sleepTimeSeconds")),
        "sleep_deep_h": _h(dto.get("deepSleepSeconds")),
        "sleep_rem_h": _h(dto.get("remSleepSeconds")),
    }


def load_context(client) -> dict:
    dp = DataProcessor()
    activities = client.get_activities(28)
    hr = client.get_heart_rate_stats(7)
    sleep = client.get_sleep(14)
    battery = client.get_body_battery(7)
    context = dp.build_context_summary(activities, hr, sleep, battery)
    context.update(_last_night_sleep(sleep))
    return context


def sleep_view(context: dict) -> dict:
    """Recorte de sono pro card de bom dia (tolera campos ausentes)."""
    return {
        "hours": context.get("sleep_last_night_h"),
        "deep_h": context.get("sleep_deep_h"),
        "rem_h": context.get("sleep_rem_h"),
        "debt_h": context.get("sleep_debt_hours"),
        "target": 7.0,
    }


def daily_analysis(db, day: str, force: bool = False) -> dict:
    return DailyAnalysis(db=db).build(day, force=force)
