from src.data_processor import DataProcessor
from src.daily_analysis import DailyAnalysis

_KEYS = ("resting_hr_today", "resting_hr_avg_7d", "morning_battery_avg",
         "sleep_debt_hours", "run_sessions_7d")


def collect_metrics(context: dict) -> dict:
    return {k: context.get(k) for k in _KEYS}


def load_context(client) -> dict:
    dp = DataProcessor()
    activities = client.get_activities(28)
    hr = client.get_heart_rate_stats(7)
    sleep = client.get_sleep(14)
    battery = client.get_body_battery(7)
    return dp.build_context_summary(activities, hr, sleep, battery)


def daily_analysis(db, day: str, force: bool = False) -> dict:
    return DailyAnalysis(db=db).build(day, force=force)
