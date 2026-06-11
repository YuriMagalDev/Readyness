import datetime
import time

from src.extractors import snapshot_from_garmin, activity_from_garmin

RATE_LIMIT_MARKER = "rate limit"
MAX_RETRIES = 3


class Ingestor:
    def __init__(self, client, db, sleep_seconds: float = 1.0, sleeper=None):
        self._client = client
        self._db = db
        self._sleep_seconds = sleep_seconds
        self._sleep = sleeper or time.sleep

    def _day_summary(self, day: str):
        for attempt in range(MAX_RETRIES):
            try:
                return self._client.get_daily_summary(day)
            except RuntimeError as e:
                if RATE_LIMIT_MARKER in str(e).lower() and attempt < MAX_RETRIES - 1:
                    self._sleep(self._sleep_seconds * (attempt + 2))
                    continue
                raise
        return {}

    def _activities_by_day(self, start: str, end: str) -> dict:
        acts = self._client.get_activities_by_date(start, end)
        grouped = {}
        for a in acts:
            row = activity_from_garmin(a)
            grouped.setdefault(row["date"], []).append(row)
        return grouped

    def _write_day(self, day: str, race, acts_for_day: list):
        summary = self._day_summary(day)
        runs = sum(1 for a in acts_for_day if not a["is_strength"]
                   and a["type"] in {"running", "trail_running", "treadmill_running"})
        strength = sum(1 for a in acts_for_day if a["is_strength"])
        train_minutes = sum(a["duration_min"] or 0 for a in acts_for_day)
        snap = snapshot_from_garmin(day, summary, race,
                                    runs=runs, strength=strength, train_minutes=train_minutes)
        self._db.upsert_snapshot(snap)
        for a in acts_for_day:
            self._db.upsert_activity(a)

    def backfill(self, days: int = 90, today: datetime.date = None):
        today = today or datetime.date.today()
        start = today - datetime.timedelta(days=days - 1)
        latest = self._db.latest_snapshot_date()
        race = self._client.get_race_predictions()
        grouped = self._activities_by_day(start.isoformat(), today.isoformat())
        for i in range(days):
            day = (start + datetime.timedelta(days=i))
            day_str = day.isoformat()
            if latest is not None and day_str <= latest:
                continue  # already have — resume
            self._write_day(day_str, race if day == today else None, grouped.get(day_str, []))
            self._sleep(self._sleep_seconds)

    def sync_today(self, today: datetime.date = None):
        today = today or datetime.date.today()
        race = self._client.get_race_predictions()
        grouped = self._activities_by_day(today.isoformat(), today.isoformat())
        self._write_day(today.isoformat(), race, grouped.get(today.isoformat(), []))
