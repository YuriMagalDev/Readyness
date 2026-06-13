import datetime
import time
import datetime as _dt

from src.extractors import snapshot_from_garmin, activity_from_garmin
from src.collectors.recuperacao import normalize_recuperacao
from src.collectors.atividade import normalize_atividade
from src.collectors.prontidao import normalize_prontidao
from src.collectors.corpo import normalize_corpo

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
            if row["is_strength"] and row.get("activity_id"):
                raw_sets = self._safe_call(
                    lambda aid=row["activity_id"]: self._client.get_activity_exercise_sets(aid))
                if raw_sets:
                    import json as _json
                    from src.extractors import sets_from_garmin
                    row["sets_json"] = _json.dumps(sets_from_garmin(raw_sets))
            grouped.setdefault(row["date"], []).append(row)
        return grouped

    def _write_day(self, day: str, race, acts_for_day: list):
        summary = self._day_summary(day)
        runs = sum(1 for a in acts_for_day if not a["is_strength"]
                   and a["type"] in {"running", "trail_running", "treadmill_running"})
        strength = sum(1 for a in acts_for_day if a["is_strength"])
        train_minutes = sum(a["duration_min"] or 0 for a in acts_for_day)

        # dual-write: snapshot legado (Hoje/Tendências atuais dependem dele)
        snap = snapshot_from_garmin(day, summary, race,
                                    runs=runs, strength=strength, train_minutes=train_minutes)
        self._db.upsert_snapshot(snap)
        for a in acts_for_day:
            self._db.upsert_activity(a)

        # metric_value via coletores
        self._write_metrics(day, summary, race)

    def _write_metrics(self, day: str, summary, race):
        sleep_one = self._safe_call(lambda: self._client.get_sleep_day(day)) or {}
        readiness = self._safe_call(lambda: self._client.get_training_readiness(day))
        max_metrics = self._safe_call(lambda: self._client.get_max_metrics(day))
        endurance = self._safe_call(lambda: self._client.get_endurance_score(day))
        hrv = self._safe_call(lambda: self._client.get_hrv(day))
        start = (_dt.date.fromisoformat(day) - _dt.timedelta(days=7)).isoformat()
        body = self._safe_call(lambda: self._client.get_body_composition(start, day))

        rows = []
        rows += normalize_recuperacao(day, summary=summary, sleep=sleep_one,
                                      hrv=hrv)
        rows += normalize_atividade(day, summary)
        rows += normalize_prontidao(day, readiness=readiness, max_metrics=max_metrics,
                                    endurance=endurance, race=race)
        rows += normalize_corpo(day, body)
        for r in rows:
            self._db.upsert_metric(day, r["metric_key"], r["value"],
                                   r["measured_at"], r["source"])

    @staticmethod
    def _safe_call(fn):
        """Endpoint novo/instável: falha vira None (métrica fica ausente)."""
        try:
            return fn()
        except Exception:  # noqa: BLE001
            return None

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
