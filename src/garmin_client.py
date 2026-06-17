import os
from datetime import date, timedelta
from dotenv import load_dotenv
from garminconnect import (
    Garmin,
    GarminConnectAuthenticationError,
    GarminConnectTooManyRequestsError,
)
from src.cache import Cache

load_dotenv()

class GarminClient:
    def __init__(self):
        self._cache = Cache(ttl_hours=float(os.getenv("CACHE_TTL_HOURS", 6)))
        self._client = self._authenticate()

    def _authenticate(self) -> Garmin:
        email = os.getenv("GARMIN_EMAIL")
        password = os.getenv("GARMIN_PASSWORD")
        if not email or not password:
            raise ValueError("GARMIN_EMAIL and GARMIN_PASSWORD must be set in .env")
        # tokenstore: loga só 1x e reusa o token salvo nos próximos starts (evita
        # 429 de login). Caminho persiste entre reinícios/boot da VM.
        self._tokenstore = os.getenv("GARMINTOKENS") or os.path.expanduser("~/.garminconnect")
        try:
            client = Garmin(email, password)
            client.login(self._tokenstore)
            return client
        except GarminConnectAuthenticationError as e:
            raise RuntimeError(f"Garmin auth failed: {e}") from e

    def _cached(self, key: str, fetch_fn):
        data = self._cache.get(key)
        if data is not None:
            return data
        try:
            data = fetch_fn()
        except GarminConnectAuthenticationError:
            self._client.login(getattr(self, "_tokenstore", None))
            data = fetch_fn()
        except GarminConnectTooManyRequestsError as e:
            raise RuntimeError("Garmin rate limit hit — try again later") from e
        self._cache.set(key, data)
        return data

    def get_activities(self, days: int = 28) -> list:
        return self._cached(
            f"activities_{days}_{date.today()}",
            lambda: self._client.get_activities(0, days),
        )

    def get_sleep(self, days: int = 14) -> list:
        results = []
        for i in range(days):
            day = (date.today() - timedelta(days=i)).isoformat()
            data = self._cached(
                f"sleep_{day}",
                lambda d=day: self._client.get_sleep_data(d),
            )
            results.append(data)
        return results

    def get_heart_rate_stats(self, days: int = 7) -> list:
        results = []
        for i in range(days):
            day = (date.today() - timedelta(days=i)).isoformat()
            data = self._cached(
                f"hr_{day}",
                lambda d=day: self._client.get_heart_rates(d),
            )
            results.append(data)
        return results

    def get_body_battery(self, days: int = 7) -> list:
        results = []
        for i in range(days):
            day = (date.today() - timedelta(days=i)).isoformat()
            data = self._cached(
                f"battery_{day}",
                lambda d=day: self._client.get_body_battery(d),
            )
            results.append(data)
        return results

    def get_steps(self, days: int = 7) -> list:
        results = []
        for i in range(days):
            day = (date.today() - timedelta(days=i)).isoformat()
            data = self._cached(
                f"steps_{day}",
                lambda d=day: self._client.get_steps_data(d),
            )
            results.append(data)
        return results

    def get_sleep_day(self, day: str) -> dict:
        return self._cached(
            f"sleepday_{day}",
            lambda: self._client.get_sleep_data(day),
        )

    def get_daily_summary(self, day: str) -> dict:
        return self._cached(
            f"summary_{day}",
            lambda: self._client.get_stats_and_body(day),
        )

    def get_race_predictions(self) -> dict:
        return self._cached(
            f"racepred_{date.today()}",
            lambda: self._client.get_race_predictions(),
        )

    def get_activity_splits(self, activity_id: int) -> dict:
        return self._cached(
            f"splits_{activity_id}",
            lambda: self._client.get_activity_splits(activity_id),
        )

    def get_activities_by_date(self, start: str, end: str) -> list:
        return self._cached(
            f"acts_{start}_{end}",
            lambda: self._client.get_activities_by_date(start, end),
        )

    def get_training_readiness(self, day: str) -> dict:
        return self._cached(
            f"readiness_{day}",
            lambda: self._client.get_morning_training_readiness(day),
        )

    def get_max_metrics(self, day: str) -> dict:
        return self._cached(
            f"maxmetrics_{day}",
            lambda: self._client.get_max_metrics(day),
        )

    def get_endurance_score(self, day: str) -> dict:
        return self._cached(
            f"endurance_{day}",
            lambda: self._client.get_endurance_score(day),
        )

    def get_hrv(self, day: str) -> dict:
        return self._cached(
            f"hrv_{day}",
            lambda: self._client.get_hrv_data(day),
        )

    def get_body_composition(self, start: str, end: str) -> dict:
        return self._cached(
            f"bodycomp_{start}_{end}",
            lambda: self._client.get_body_composition(start, end),
        )

    def get_activity_exercise_sets(self, activity_id: int) -> dict:
        return self._cached(
            f"exercise_sets_{activity_id}",
            lambda: self._client.get_activity_exercise_sets(activity_id),
        )

    def clear_cache(self) -> None:
        self._cache.clear()
