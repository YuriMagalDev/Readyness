# Data-Driven Coach (v2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persistir histórico permanente do Garmin (FR55) em SQLite, calcular tendências determinísticas, e usar Haiku para gerar insights de tendência, do dia e por treino — exibidos em novas páginas Tendências e Treinos.

**Architecture:** Ingestão separada da leitura. `Ingestor` grava snapshots diários + atividades em `history.db` (backfill 3 meses + sync incremental, com throttle anti-429). API/`Analytics` só leem do DB. `InsightEngine` (Haiku) consome o Analytics. Snapshot diário vem majoritariamente de `get_stats_and_body(date)` (1 chamada agrega FC/stress/resp/spo2/steps/calorias/battery) + `get_sleep_data(date)`.

**Tech Stack:** Python 3.11+, sqlite3, garminconnect, anthropic (Haiku), FastAPI, React+Vite+TS, Recharts.

**Spec:** `docs/superpowers/specs/2026-06-11-data-driven-coach-design.md`

---

## Decisão de eficiência (desvio justificado do spec)

O spec listou métodos separados `get_stress/get_respiration/get_spo2/get_intensity_minutes`.
A sondagem mostrou que `get_stats_and_body(date)` já devolve `averageStressLevel`,
`avgWakingRespirationValue`, `averageSpo2`, `moderateIntensityMinutes`,
`vigorousIntensityMinutes`, `restingHeartRate`, `totalSteps`, `floorsAscended`,
`totalKilocalories`, `activeKilocalories`, `bodyBatteryHighestValue`,
`bodyBatteryLowestValue` — tudo numa chamada. Então o snapshot usa 2 chamadas/dia
(`get_stats_and_body` + `get_sleep_data`) em vez de 8. Menos chamadas = menos 429.
Não criamos os 4 métodos separados (YAGNI).

Splits de treino: NÃO buscados no backfill (1 chamada por atividade = volume alto).
`splits_json` fica `null` e é preenchido sob demanda em `GET /api/activity/{id}`.

---

## File Map

| Arquivo | Responsabilidade |
|---------|-----------------|
| `src/history_db.py` | Schema + CRUD de `history.db` (snapshot + activity) |
| `src/garmin_client.py` | + `get_daily_summary`, `get_race_predictions`, `get_activity_splits` |
| `src/extractors.py` | Puro: dict Garmin → linha de snapshot / activity |
| `src/ingestor.py` | backfill + sync_today com throttle |
| `src/analytics.py` | Séries, deltas, slope de tendência (puro) |
| `src/insight_engine.py` | Haiku: trend/daily/activity insights + fallback |
| `api/services.py` | + build_trends, build_activities, build_activity_detail, sync; enriquecer build_today |
| `api/main.py` | + rotas /api/trends, /api/activities, /api/activity/{id}, /api/sync |
| `web/src/types.ts` | + Trends, ActivitySummary, ActivityDetail, DailyInsight |
| `web/src/api.ts` | + fetchTrends, fetchActivities, fetchActivity, postSync |
| `web/src/pages/Tendencias.tsx` | nova página B |
| `web/src/pages/Treinos.tsx` | nova página A |
| `web/src/pages/Hoje.tsx` | + insight do dia + stress/resp/spo2 |
| `web/src/components/Sidebar.tsx` | + itens Tendências/Treinos, remove Dados |
| `web/src/App.tsx` | rotas das páginas novas |
| `tests/test_history_db.py` | CRUD idempotente |
| `tests/test_extractors.py` | extração pura |
| `tests/test_ingestor.py` | throttle + gravação + retomada (mock) |
| `tests/test_analytics.py` | tendências determinísticas |
| `tests/test_insight_engine.py` | fallback + depth quick (mock) |
| `tests/test_api.py` | rotas novas (TestClient, mock) |

---

## Task 1: history_db — schema e CRUD

**Files:**
- Create: `src/history_db.py`
- Test: `tests/test_history_db.py`

- [ ] **Step 1: Escrever testes**

`tests/test_history_db.py`:
```python
import pytest
from src.history_db import HistoryDB


@pytest.fixture
def db(tmp_path):
    return HistoryDB(db_path=str(tmp_path / "hist.db"))


def test_upsert_and_get_snapshot(db):
    db.upsert_snapshot({"date": "2026-06-10", "resting_hr": 52, "steps": 8000})
    rows = db.get_snapshots("2026-06-01", "2026-06-30")
    assert len(rows) == 1
    assert rows[0]["resting_hr"] == 52
    assert rows[0]["steps"] == 8000


def test_snapshot_upsert_is_idempotent(db):
    db.upsert_snapshot({"date": "2026-06-10", "resting_hr": 52})
    db.upsert_snapshot({"date": "2026-06-10", "resting_hr": 55})
    rows = db.get_snapshots("2026-06-01", "2026-06-30")
    assert len(rows) == 1
    assert rows[0]["resting_hr"] == 55


def test_get_snapshots_range_filters(db):
    db.upsert_snapshot({"date": "2026-05-01", "resting_hr": 50})
    db.upsert_snapshot({"date": "2026-06-10", "resting_hr": 52})
    rows = db.get_snapshots("2026-06-01", "2026-06-30")
    assert len(rows) == 1
    assert rows[0]["date"] == "2026-06-10"


def test_snapshots_sorted_ascending(db):
    db.upsert_snapshot({"date": "2026-06-10", "resting_hr": 52})
    db.upsert_snapshot({"date": "2026-06-05", "resting_hr": 50})
    rows = db.get_snapshots("2026-06-01", "2026-06-30")
    assert [r["date"] for r in rows] == ["2026-06-05", "2026-06-10"]


def test_upsert_and_get_activity(db):
    db.upsert_activity({"activity_id": 1, "date": "2026-06-10", "name": "Corrida",
                        "type": "running", "is_strength": 0, "distance_m": 5000})
    acts = db.get_activities("2026-06-01", "2026-06-30")
    assert len(acts) == 1
    assert acts[0]["name"] == "Corrida"


def test_activity_upsert_idempotent(db):
    db.upsert_activity({"activity_id": 1, "date": "2026-06-10", "name": "A", "type": "running"})
    db.upsert_activity({"activity_id": 1, "date": "2026-06-10", "name": "B", "type": "running"})
    acts = db.get_activities("2026-06-01", "2026-06-30")
    assert len(acts) == 1
    assert acts[0]["name"] == "B"


def test_get_single_activity(db):
    db.upsert_activity({"activity_id": 7, "date": "2026-06-10", "name": "X", "type": "running"})
    assert db.get_activity(7)["activity_id"] == 7
    assert db.get_activity(999) is None


def test_latest_snapshot_date(db):
    assert db.latest_snapshot_date() is None
    db.upsert_snapshot({"date": "2026-06-05", "resting_hr": 50})
    db.upsert_snapshot({"date": "2026-06-10", "resting_hr": 52})
    assert db.latest_snapshot_date() == "2026-06-10"
```

- [ ] **Step 2: Rodar — confirmar falha**

Run: `pytest tests/test_history_db.py -v`
Expected: `ModuleNotFoundError: No module named 'src.history_db'`

- [ ] **Step 3: Implementar `src/history_db.py`**

```python
import sqlite3

SNAPSHOT_COLUMNS = [
    "date", "resting_hr", "sleep_hours", "sleep_score",
    "body_battery_high", "body_battery_low", "stress_avg", "stress_max",
    "respiration_avg", "spo2_avg", "intensity_minutes", "steps", "floors",
    "calories_total", "calories_active",
    "race_pred_5k", "race_pred_10k", "race_pred_21k", "race_pred_42k",
    "runs", "strength", "train_minutes",
]

ACTIVITY_COLUMNS = [
    "activity_id", "date", "name", "type", "is_strength",
    "distance_m", "duration_min", "pace_min_km", "avg_hr", "max_hr",
    "calories", "cadence", "stride_length", "splits_json",
]


class HistoryDB:
    def __init__(self, db_path: str = "history.db"):
        self._db_path = db_path
        self._init_db()

    def _connect(self):
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        snap_cols = ", ".join(
            f"{c} TEXT PRIMARY KEY" if c == "date" else f"{c} REAL"
            for c in SNAPSHOT_COLUMNS
        )
        act_cols = ", ".join(
            f"{c} INTEGER PRIMARY KEY" if c == "activity_id"
            else f"{c} TEXT" if c in ("date", "name", "type", "splits_json")
            else f"{c} REAL"
            for c in ACTIVITY_COLUMNS
        )
        with self._connect() as conn:
            conn.execute(f"CREATE TABLE IF NOT EXISTS daily_snapshot ({snap_cols})")
            conn.execute(f"CREATE TABLE IF NOT EXISTS activity ({act_cols})")

    def _upsert(self, table: str, columns: list, row: dict):
        cols = [c for c in columns if c in row]
        placeholders = ", ".join("?" for _ in cols)
        col_list = ", ".join(cols)
        updates = ", ".join(f"{c}=excluded.{c}" for c in cols if c != columns[0])
        key = columns[0]
        sql = (
            f"INSERT INTO {table} ({col_list}) VALUES ({placeholders}) "
            f"ON CONFLICT({key}) DO UPDATE SET {updates}"
        )
        with self._connect() as conn:
            conn.execute(sql, [row[c] for c in cols])

    def upsert_snapshot(self, row: dict):
        self._upsert("daily_snapshot", SNAPSHOT_COLUMNS, row)

    def upsert_activity(self, row: dict):
        self._upsert("activity", ACTIVITY_COLUMNS, row)

    def get_snapshots(self, start: str, end: str) -> list:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM daily_snapshot WHERE date >= ? AND date <= ? ORDER BY date ASC",
                (start, end),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_activities(self, start: str, end: str) -> list:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM activity WHERE date >= ? AND date <= ? ORDER BY date DESC",
                (start, end),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_activity(self, activity_id: int):
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM activity WHERE activity_id = ?", (activity_id,)
            ).fetchone()
        return dict(row) if row else None

    def latest_snapshot_date(self):
        with self._connect() as conn:
            row = conn.execute("SELECT MAX(date) AS d FROM daily_snapshot").fetchone()
        return row["d"] if row and row["d"] else None
```

- [ ] **Step 4: Rodar testes**

Run: `pytest tests/test_history_db.py -v`
Expected: 8 PASSED

- [ ] **Step 5: Commit**

```bash
git add src/history_db.py tests/test_history_db.py
git commit -m "feat: add history_db — permanent SQLite warehouse"
```

---

## Task 2: GarminClient — métodos novos

**Files:**
- Modify: `src/garmin_client.py`

> Bate API real — sem teste automatizado. Validação manual.

- [ ] **Step 1: Adicionar 3 métodos à classe `GarminClient`**

Adicionar dentro da classe (após `get_steps`), em `src/garmin_client.py`:
```python
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
```

(`date` já está importado no topo do arquivo: `from datetime import date, timedelta`.)

- [ ] **Step 2: Validar manualmente (1 chamada, cuidado com 429)**

Run:
```bash
python -c "
from src.garmin_client import GarminClient
import datetime
c = GarminClient()
d = (datetime.date.today()-datetime.timedelta(days=1)).isoformat()
s = c.get_daily_summary(d)
print('resting_hr:', s.get('restingHeartRate'), '| steps:', s.get('totalSteps'), '| stress:', s.get('averageStressLevel'))
rp = c.get_race_predictions()
print('race 5k(s):', rp.get('time5K'))
"
```
Expected: imprime FC/steps/stress e tempo de 5k. Se 429: aguardar e repetir.

- [ ] **Step 3: Commit**

```bash
git add src/garmin_client.py
git commit -m "feat: GarminClient — daily summary, race predictions, splits, activities by date"
```

---

## Task 3: Extractors — Garmin → linhas do DB

**Files:**
- Create: `src/extractors.py`
- Test: `tests/test_extractors.py`

- [ ] **Step 1: Escrever testes**

`tests/test_extractors.py`:
```python
from src.extractors import snapshot_from_garmin, activity_from_garmin, splits_from_garmin

SUMMARY = {
    "restingHeartRate": 52, "totalSteps": 8000, "floorsAscended": 12,
    "totalKilocalories": 2200, "activeKilocalories": 600,
    "moderateIntensityMinutes": 30, "vigorousIntensityMinutes": 10,
    "averageStressLevel": 35, "maxStressLevel": 80,
    "avgWakingRespirationValue": 14.5, "averageSpo2": 96,
    "bodyBatteryHighestValue": 90, "bodyBatteryLowestValue": 20,
    "measurableAsleepDuration": 25200,  # 7h de sono medido
}
RACE = {"time5K": 1758, "time10K": 3700, "timeHalfMarathon": 8200, "timeMarathon": 17000}


def test_snapshot_basic_fields():
    row = snapshot_from_garmin("2026-06-10", SUMMARY, RACE, runs=2, strength=1, train_minutes=95)
    assert row["date"] == "2026-06-10"
    assert row["resting_hr"] == 52
    assert row["steps"] == 8000
    assert row["intensity_minutes"] == 40  # moderate + vigorous
    assert row["sleep_hours"] == 7.0
    assert row["stress_avg"] == 35
    assert row["spo2_avg"] == 96
    assert row["body_battery_high"] == 90
    assert row["race_pred_5k"] == 1758
    assert row["runs"] == 2
    assert row["strength"] == 1
    assert row["train_minutes"] == 95


def test_snapshot_handles_missing_summary():
    row = snapshot_from_garmin("2026-06-10", {}, None, runs=0, strength=0, train_minutes=0)
    assert row["date"] == "2026-06-10"
    assert row["resting_hr"] is None
    assert row["intensity_minutes"] is None
    assert row["sleep_hours"] is None
    assert row["race_pred_5k"] is None


def test_activity_pace_and_fields():
    act = {
        "activityId": 99, "activityName": "Corrida", "startTimeLocal": "2026-06-10 07:00:00",
        "activityType": {"typeKey": "running"}, "distance": 5000.0, "duration": 1500.0,
        "averageSpeed": 3.333, "averageHR": 150, "maxHR": 170, "calories": 400,
        "averageRunningCadenceInStepsPerMinute": 160, "averageRunningCadenceInStepsPerMinute": 160,
    }
    row = activity_from_garmin(act)
    assert row["activity_id"] == 99
    assert row["type"] == "running"
    assert row["is_strength"] == 0
    assert row["distance_m"] == 5000.0
    assert row["duration_min"] == 25.0
    assert round(row["pace_min_km"], 2) == 5.0  # 3.333 m/s → 5 min/km
    assert row["avg_hr"] == 150


def test_activity_strength_flagged():
    act = {"activityId": 1, "activityName": "Força", "startTimeLocal": "2026-06-09 18:00:00",
           "activityType": {"typeKey": "indoor_cardio"}, "duration": 3600.0}
    row = activity_from_garmin(act)
    assert row["is_strength"] == 1
    assert row["pace_min_km"] is None  # sem averageSpeed


def test_splits_json_shape():
    raw = {"lapDTOs": [
        {"distance": 1000, "duration": 300, "averageSpeed": 3.33, "averageHR": 150, "averageRunCadence": 160},
        {"distance": 1000, "duration": 310, "averageSpeed": 3.22, "averageHR": 155, "averageRunCadence": 158},
    ]}
    splits = splits_from_garmin(raw)
    assert len(splits) == 2
    assert splits[0]["distance_m"] == 1000
    assert round(splits[0]["pace_min_km"], 2) == 5.0
    assert splits[0]["avg_hr"] == 150
```

- [ ] **Step 2: Rodar — confirmar falha**

Run: `pytest tests/test_extractors.py -v`
Expected: `ModuleNotFoundError: No module named 'src.extractors'`

- [ ] **Step 3: Implementar `src/extractors.py`**

```python
STRENGTH_ACTIVITY_TYPES = {"strength_training", "indoor_cardio"}


def _pace_min_km(speed_m_s):
    if not speed_m_s or speed_m_s <= 0:
        return None
    return (1000 / speed_m_s) / 60


def snapshot_from_garmin(day, summary, race, runs, strength, train_minutes) -> dict:
    summary = summary or {}
    race = race or {}

    moderate = summary.get("moderateIntensityMinutes")
    vigorous = summary.get("vigorousIntensityMinutes")
    intensity = None
    if moderate is not None or vigorous is not None:
        intensity = (moderate or 0) + (vigorous or 0)

    sleep_secs = summary.get("measurableAsleepDuration")
    sleep_hours = round(sleep_secs / 3600, 1) if sleep_secs else None

    return {
        "date": day,
        "resting_hr": summary.get("restingHeartRate"),
        "sleep_hours": sleep_hours,
        "sleep_score": None,  # FR55 não fornece score numérico de sono
        "body_battery_high": summary.get("bodyBatteryHighestValue"),
        "body_battery_low": summary.get("bodyBatteryLowestValue"),
        "stress_avg": summary.get("averageStressLevel"),
        "stress_max": summary.get("maxStressLevel"),
        "respiration_avg": summary.get("avgWakingRespirationValue"),
        "spo2_avg": summary.get("averageSpo2"),
        "intensity_minutes": intensity,
        "steps": summary.get("totalSteps"),
        "floors": summary.get("floorsAscended"),
        "calories_total": summary.get("totalKilocalories"),
        "calories_active": summary.get("activeKilocalories"),
        "race_pred_5k": race.get("time5K"),
        "race_pred_10k": race.get("time10K"),
        "race_pred_21k": race.get("timeHalfMarathon"),
        "race_pred_42k": race.get("timeMarathon"),
        "runs": runs,
        "strength": strength,
        "train_minutes": train_minutes,
    }


def activity_from_garmin(act: dict) -> dict:
    type_key = act.get("activityType", {}).get("typeKey", "")
    duration = act.get("duration")
    return {
        "activity_id": act.get("activityId"),
        "date": act.get("startTimeLocal", "")[:10],
        "name": act.get("activityName", ""),
        "type": type_key,
        "is_strength": 1 if type_key in STRENGTH_ACTIVITY_TYPES else 0,
        "distance_m": act.get("distance"),
        "duration_min": round(duration / 60, 1) if duration else None,
        "pace_min_km": _pace_min_km(act.get("averageSpeed")),
        "avg_hr": act.get("averageHR"),
        "max_hr": act.get("maxHR"),
        "calories": act.get("calories"),
        "cadence": act.get("averageRunningCadenceInStepsPerMinute"),
        "stride_length": act.get("avgStrideLength"),
    }


def splits_from_garmin(raw: dict) -> list:
    laps = (raw or {}).get("lapDTOs", []) or []
    out = []
    for lap in laps:
        out.append({
            "distance_m": lap.get("distance"),
            "duration_s": lap.get("duration"),
            "pace_min_km": _pace_min_km(lap.get("averageSpeed")),
            "avg_hr": lap.get("averageHR"),
            "cadence": lap.get("averageRunCadence"),
        })
    return out
```

- [ ] **Step 4: Rodar testes**

Run: `pytest tests/test_extractors.py -v`
Expected: 5 PASSED

- [ ] **Step 5: Commit**

```bash
git add src/extractors.py tests/test_extractors.py
git commit -m "feat: add extractors — Garmin payloads to DB rows"
```

---

## Task 4: Ingestor — backfill e sync com throttle

**Files:**
- Create: `src/ingestor.py`
- Test: `tests/test_ingestor.py`

- [ ] **Step 1: Escrever testes**

`tests/test_ingestor.py`:
```python
import datetime
from unittest.mock import MagicMock
from src.ingestor import Ingestor


def _summary(rhr=52):
    return {"restingHeartRate": rhr, "totalSteps": 8000, "moderateIntensityMinutes": 20,
            "vigorousIntensityMinutes": 5, "averageStressLevel": 30, "averageSpo2": 96,
            "bodyBatteryHighestValue": 90, "bodyBatteryLowestValue": 20,
            "totalKilocalories": 2200, "activeKilocalories": 500,
            "measurableAsleepDuration": 25200}


def _client():
    c = MagicMock()
    c.get_daily_summary.return_value = _summary()
    c.get_race_predictions.return_value = {"time5K": 1758, "time10K": 3700,
                                           "timeHalfMarathon": 8200, "timeMarathon": 17000}
    c.get_activities_by_date.return_value = [{
        "activityId": 1, "activityName": "Corrida", "startTimeLocal": "2026-06-10 07:00:00",
        "activityType": {"typeKey": "running"}, "distance": 5000, "duration": 1500,
        "averageSpeed": 3.333, "averageHR": 150,
    }]
    return c


def test_backfill_writes_snapshots(tmp_path):
    from src.history_db import HistoryDB
    db = HistoryDB(db_path=str(tmp_path / "h.db"))
    client = _client()
    ing = Ingestor(client, db, sleep_seconds=0)
    ing.backfill(days=3, today=datetime.date(2026, 6, 10))
    rows = db.get_snapshots("2026-06-01", "2026-06-30")
    assert len(rows) == 3
    assert all(r["resting_hr"] == 52 for r in rows)


def test_backfill_throttles_between_days(tmp_path):
    from src.history_db import HistoryDB
    db = HistoryDB(db_path=str(tmp_path / "h.db"))
    sleeper = MagicMock()
    ing = Ingestor(_client(), db, sleep_seconds=0.01, sleeper=sleeper)
    ing.backfill(days=3, today=datetime.date(2026, 6, 10))
    assert sleeper.call_count >= 3  # pausa por dia


def test_backfill_resumes_from_latest(tmp_path):
    from src.history_db import HistoryDB
    db = HistoryDB(db_path=str(tmp_path / "h.db"))
    db.upsert_snapshot({"date": "2026-06-09", "resting_hr": 99})
    client = _client()
    ing = Ingestor(client, db, sleep_seconds=0)
    ing.backfill(days=5, today=datetime.date(2026, 6, 10))
    # 09 já existia → só busca 10 (resume). 09 preservado.
    rows = {r["date"]: r for r in db.get_snapshots("2026-06-01", "2026-06-30")}
    assert rows["2026-06-09"]["resting_hr"] == 99
    assert "2026-06-10" in rows


def test_backfill_retries_on_rate_limit(tmp_path):
    from src.history_db import HistoryDB
    db = HistoryDB(db_path=str(tmp_path / "h.db"))
    client = _client()
    calls = {"n": 0}

    def flaky(day):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("Garmin rate limit hit — try again later")
        return _summary()

    client.get_daily_summary.side_effect = flaky
    sleeper = MagicMock()
    ing = Ingestor(client, db, sleep_seconds=0, sleeper=sleeper)
    ing.backfill(days=1, today=datetime.date(2026, 6, 10))
    rows = db.get_snapshots("2026-06-01", "2026-06-30")
    assert len(rows) == 1  # recuperou após retry


def test_sync_today_writes_one(tmp_path):
    from src.history_db import HistoryDB
    db = HistoryDB(db_path=str(tmp_path / "h.db"))
    ing = Ingestor(_client(), db, sleep_seconds=0)
    ing.sync_today(today=datetime.date(2026, 6, 10))
    rows = db.get_snapshots("2026-06-01", "2026-06-30")
    assert len(rows) == 1
    acts = db.get_activities("2026-06-01", "2026-06-30")
    assert len(acts) == 1
```

- [ ] **Step 2: Rodar — confirmar falha**

Run: `pytest tests/test_ingestor.py -v`
Expected: `ModuleNotFoundError: No module named 'src.ingestor'`

- [ ] **Step 3: Implementar `src/ingestor.py`**

```python
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
                continue  # já temos — resume
            self._write_day(day_str, race if day == today else None, grouped.get(day_str, []))
            self._sleep(self._sleep_seconds)

    def sync_today(self, today: datetime.date = None):
        today = today or datetime.date.today()
        race = self._client.get_race_predictions()
        grouped = self._activities_by_day(today.isoformat(), today.isoformat())
        self._write_day(today.isoformat(), race, grouped.get(today.isoformat(), []))
```

- [ ] **Step 4: Rodar testes**

Run: `pytest tests/test_ingestor.py -v`
Expected: 5 PASSED

- [ ] **Step 5: Commit**

```bash
git add src/ingestor.py tests/test_ingestor.py
git commit -m "feat: add Ingestor — backfill + sync with throttle and resume"
```

---

## Task 5: Analytics — séries, deltas, tendência

**Files:**
- Create: `src/analytics.py`
- Test: `tests/test_analytics.py`

- [ ] **Step 1: Escrever testes**

`tests/test_analytics.py`:
```python
from src.analytics import Analytics


def _snaps():
    # 14 dias: FC subindo de 50 a 56
    rows = []
    for i in range(14):
        rows.append({
            "date": f"2026-06-{i+1:02d}",
            "resting_hr": 50 + i * 0.5,
            "sleep_hours": 7.0,
            "stress_avg": 30,
            "body_battery_high": 90,
            "intensity_minutes": 30,
            "race_pred_5k": 1800 - i,  # melhorando
        })
    return rows


def test_series_extracts_metric():
    a = Analytics()
    s = a.series(_snaps(), "resting_hr")
    assert len(s) == 14
    assert s[0]["valor"] == 50
    assert s[0]["data"] == "2026-06-01"


def test_series_skips_none():
    a = Analytics()
    rows = [{"date": "2026-06-01", "resting_hr": None}, {"date": "2026-06-02", "resting_hr": 52}]
    s = a.series(rows, "resting_hr")
    assert len(s) == 2
    assert s[0]["valor"] is None


def test_trend_rising():
    a = Analytics()
    t = a.trend(_snaps(), "resting_hr")
    assert t["direction"] == "subindo"
    assert t["slope"] > 0


def test_trend_falling_race_pred():
    a = Analytics()
    t = a.trend(_snaps(), "race_pred_5k")
    assert t["direction"] == "descendo"  # tempo caindo = melhora


def test_trend_stable():
    a = Analytics()
    rows = [{"date": f"2026-06-{i+1:02d}", "stress_avg": 30} for i in range(14)]
    t = a.trend(rows, "stress_avg")
    assert t["direction"] == "estável"


def test_trend_insufficient_data():
    a = Analytics()
    t = a.trend([{"date": "2026-06-01", "resting_hr": 50}], "resting_hr")
    assert t["direction"] == "estável"
    assert t["slope"] == 0.0


def test_summary_bundles_metrics():
    a = Analytics()
    out = a.summary(_snaps())
    assert "resting_hr" in out
    assert out["resting_hr"]["trend"]["direction"] == "subindo"
    assert len(out["resting_hr"]["series"]) == 14
```

- [ ] **Step 2: Rodar — confirmar falha**

Run: `pytest tests/test_analytics.py -v`
Expected: `ModuleNotFoundError: No module named 'src.analytics'`

- [ ] **Step 3: Implementar `src/analytics.py`**

```python
TREND_METRICS = [
    "resting_hr", "sleep_hours", "stress_avg", "body_battery_high",
    "intensity_minutes", "race_pred_5k",
]
SLOPE_EPSILON = 0.05  # |slope| abaixo disso = estável


class Analytics:
    def series(self, snapshots: list, metric: str) -> list:
        return [{"data": s["date"], "valor": s.get(metric)} for s in snapshots]

    def trend(self, snapshots: list, metric: str) -> dict:
        pts = [(i, s[metric]) for i, s in enumerate(snapshots) if s.get(metric) is not None]
        if len(pts) < 2:
            return {"slope": 0.0, "direction": "estável"}
        n = len(pts)
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        mx = sum(xs) / n
        my = sum(ys) / n
        denom = sum((x - mx) ** 2 for x in xs)
        if denom == 0:
            return {"slope": 0.0, "direction": "estável"}
        slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / denom
        if abs(slope) < SLOPE_EPSILON:
            direction = "estável"
        elif slope > 0:
            direction = "subindo"
        else:
            direction = "descendo"
        return {"slope": round(slope, 4), "direction": direction}

    def summary(self, snapshots: list) -> dict:
        out = {}
        for metric in TREND_METRICS:
            out[metric] = {
                "series": self.series(snapshots, metric),
                "trend": self.trend(snapshots, metric),
            }
        return out
```

- [ ] **Step 4: Rodar testes**

Run: `pytest tests/test_analytics.py -v`
Expected: 7 PASSED

- [ ] **Step 5: Commit**

```bash
git add src/analytics.py tests/test_analytics.py
git commit -m "feat: add Analytics — time series and linear trend"
```

---

## Task 6: InsightEngine — Haiku

**Files:**
- Create: `src/insight_engine.py`
- Test: `tests/test_insight_engine.py`

- [ ] **Step 1: Escrever testes**

`tests/test_insight_engine.py`:
```python
import json
from unittest.mock import patch
from src.insight_engine import InsightEngine

ANALYTICS = {
    "resting_hr": {"trend": {"direction": "subindo", "slope": 0.5}, "series": []},
    "sleep_hours": {"trend": {"direction": "descendo", "slope": -0.2}, "series": []},
}


@patch("src.insight_engine.ask_coach", return_value=json.dumps(
    {"insights": ["FC repouso subindo", "Sono caindo"]}))
def test_trend_insights_parses(mock_ask):
    eng = InsightEngine()
    out = eng.trend_insights(ANALYTICS)
    assert out == ["FC repouso subindo", "Sono caindo"]


@patch("src.insight_engine.ask_coach", return_value=json.dumps({"insights": []}))
def test_trend_insights_uses_haiku(mock_ask):
    InsightEngine().trend_insights(ANALYTICS)
    call = mock_ask.call_args
    depth = call[1].get("depth") or call[0][2]
    assert depth == "quick"


@patch("src.insight_engine.ask_coach", return_value="not json at all")
def test_trend_insights_fallback_on_bad_json(mock_ask):
    out = InsightEngine().trend_insights(ANALYTICS)
    assert isinstance(out, list)
    assert len(out) == 1  # fallback message


@patch("src.insight_engine.ask_coach", return_value=json.dumps({"insight": "Treine leve hoje"}))
def test_daily_insight_parses(mock_ask):
    out = InsightEngine().daily_insight({"resting_hr_today": 55}, ANALYTICS)
    assert out == "Treine leve hoje"


@patch("src.insight_engine.ask_coach", return_value="boom")
def test_daily_insight_fallback(mock_ask):
    out = InsightEngine().daily_insight({}, ANALYTICS)
    assert isinstance(out, str)
    assert out != ""


@patch("src.insight_engine.ask_coach", return_value=json.dumps({"insight": "Pace consistente"}))
def test_activity_insight_parses(mock_ask):
    out = InsightEngine().activity_insight({"name": "Corrida", "pace_min_km": 5.0}, [])
    assert out == "Pace consistente"
```

- [ ] **Step 2: Rodar — confirmar falha**

Run: `pytest tests/test_insight_engine.py -v`
Expected: `ModuleNotFoundError: No module named 'src.insight_engine'`

- [ ] **Step 3: Implementar `src/insight_engine.py`**

```python
import json
from src.ai_coach import ask_coach

FALLBACK_TRENDS = ["Dados insuficientes para análise de tendência no momento."]
FALLBACK_DAILY = "Sem análise disponível agora. Siga seu plano normalmente."
FALLBACK_ACTIVITY = "Sem análise detalhada para este treino."


def _parse_json(raw: str):
    try:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("```")[1]
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]
        return json.loads(cleaned)
    except (json.JSONDecodeError, IndexError):
        return None


class InsightEngine:
    def trend_insights(self, analytics: dict) -> list:
        prompt = f"""Analise estas tendências de saúde/treino e gere 2-3 observações
curtas e práticas (cada uma 1 frase). Foque no que mudou e no que fazer.

Tendências: {json.dumps(analytics, ensure_ascii=False)}

Retorne EXATAMENTE este JSON: {{"insights": ["...", "..."]}}"""
        data = _parse_json(ask_coach(prompt, {}, depth="quick"))
        if not data or not isinstance(data.get("insights"), list) or not data["insights"]:
            return FALLBACK_TRENDS
        return data["insights"]

    def daily_insight(self, context: dict, analytics: dict) -> str:
        prompt = f"""Com base no estado de hoje e nas tendências recentes, dê UMA
recomendação consolidada para hoje (1-2 frases, prática).

Hoje: {json.dumps(context, ensure_ascii=False)}
Tendências: {json.dumps(analytics, ensure_ascii=False)}

Retorne EXATAMENTE este JSON: {{"insight": "..."}}"""
        data = _parse_json(ask_coach(prompt, context, depth="quick"))
        if not data or not data.get("insight"):
            return FALLBACK_DAILY
        return data["insight"]

    def activity_insight(self, activity: dict, splits: list) -> str:
        prompt = f"""Comente este treino em 1-2 frases: ritmo, FC, consistência dos splits.

Treino: {json.dumps(activity, ensure_ascii=False)}
Splits por km: {json.dumps(splits, ensure_ascii=False)}

Retorne EXATAMENTE este JSON: {{"insight": "..."}}"""
        data = _parse_json(ask_coach(prompt, {}, depth="quick"))
        if not data or not data.get("insight"):
            return FALLBACK_ACTIVITY
        return data["insight"]
```

- [ ] **Step 4: Rodar testes**

Run: `pytest tests/test_insight_engine.py -v`
Expected: 6 PASSED

- [ ] **Step 5: Commit**

```bash
git add src/insight_engine.py tests/test_insight_engine.py
git commit -m "feat: add InsightEngine — Haiku trend/daily/activity insights with fallback"
```

---

## Task 7: API services — trends, activities, sync, enrich today

**Files:**
- Modify: `api/services.py`
- Test: `tests/test_api.py` (adicionar)

- [ ] **Step 1: Adicionar testes de serviço ao fim de `tests/test_api.py`**

```python
from unittest.mock import MagicMock as _MM


def _hist_with_snapshots():
    db = _MM()
    db.get_snapshots.return_value = [
        {"date": f"2026-06-{i+1:02d}", "resting_hr": 50 + i, "sleep_hours": 7,
         "stress_avg": 30, "body_battery_high": 90, "intensity_minutes": 30,
         "race_pred_5k": 1800} for i in range(14)
    ]
    db.get_activities.return_value = [
        {"activity_id": 1, "date": "2026-06-10", "name": "Corrida", "type": "running",
         "is_strength": 0, "pace_min_km": 5.0, "avg_hr": 150, "duration_min": 25,
         "distance_m": 5000, "splits_json": None}
    ]
    db.get_activity.return_value = {
        "activity_id": 1, "date": "2026-06-10", "name": "Corrida", "type": "running",
        "is_strength": 0, "pace_min_km": 5.0, "avg_hr": 150, "duration_min": 25,
        "distance_m": 5000, "splits_json": None,
    }
    return db


def test_build_trends():
    db = _hist_with_snapshots()
    with patch("api.services.InsightEngine") as MockEng:
        MockEng.return_value.trend_insights.return_value = ["obs1", "obs2"]
        payload = services.build_trends(db, period=14)
    assert "metrics" in payload
    assert "insights" in payload
    assert payload["insights"] == ["obs1", "obs2"]
    assert "resting_hr" in payload["metrics"]


def test_build_activities_list():
    db = _hist_with_snapshots()
    payload = services.build_activities(db, period=30)
    assert isinstance(payload, list)
    assert payload[0]["name"] == "Corrida"


def test_build_activity_detail_fetches_splits_if_missing():
    db = _hist_with_snapshots()
    client = MagicMock()
    client.get_activity_splits.return_value = {"lapDTOs": [
        {"distance": 1000, "duration": 300, "averageSpeed": 3.33, "averageHR": 150, "averageRunCadence": 160}
    ]}
    with patch("api.services.InsightEngine") as MockEng:
        MockEng.return_value.activity_insight.return_value = "bom pace"
        payload = services.build_activity_detail(db, client, 1)
    assert payload["splits"][0]["distance_m"] == 1000
    assert payload["insight"] == "bom pace"
    client.get_activity_splits.assert_called_once_with(1)
```

- [ ] **Step 2: Rodar — confirmar falha**

Run: `pytest tests/test_api.py -k "trends or activities or activity_detail" -v`
Expected: FAIL — `AttributeError: module 'api.services' has no attribute 'build_trends'`

- [ ] **Step 3: Adicionar funções a `api/services.py`**

Adicionar imports no topo (junto aos existentes):
```python
import json as _json

from src.analytics import Analytics
from src.insight_engine import InsightEngine
from src.extractors import splits_from_garmin
```

Adicionar no fim de `api/services.py`:
```python
def _period_range(period: int):
    from datetime import date, timedelta
    end = date.today()
    start = end - timedelta(days=period - 1)
    return start.isoformat(), end.isoformat()


def build_trends(db, period: int = 30) -> dict:
    start, end = _period_range(period)
    snaps = db.get_snapshots(start, end)
    metrics = Analytics().summary(snaps)
    insights = InsightEngine().trend_insights(metrics)
    return {"period": period, "metrics": metrics, "insights": insights}


def build_activities(db, period: int = 30) -> list:
    start, end = _period_range(period)
    return db.get_activities(start, end)


def build_activity_detail(db, client, activity_id: int) -> dict:
    act = db.get_activity(activity_id)
    if act is None:
        raise ValueError(f"Atividade {activity_id} não encontrada")
    if act.get("splits_json"):
        splits = _json.loads(act["splits_json"])
    else:
        raw = client.get_activity_splits(activity_id)
        splits = splits_from_garmin(raw)
        act["splits_json"] = _json.dumps(splits)
        db.upsert_activity(act)
    insight = InsightEngine().activity_insight(act, splits)
    return {"activity": act, "splits": splits, "insight": insight}
```

Enriquecer `build_today` — adicionar `daily_insight` e métricas de stress/resp/spo2.
Localizar a função `build_today` e substituir seu corpo por:
```python
def build_today(client, db=None) -> dict:
    dp, context, *_ = _load_context(client)
    status = HealthMonitor().check(context)
    payload = {
        "status": status["status"],
        "motivo": status["motivo"],
        "recomendacao": status["recomendacao"],
        "metrics": {
            "resting_hr_today": context["resting_hr_today"],
            "resting_hr_avg_7d": context["resting_hr_avg_7d"],
            "morning_battery_avg": context["morning_battery_avg"],
            "sleep_debt_hours": context["sleep_debt_hours"],
            "run_sessions_7d": context["run_sessions_7d"],
        },
    }
    if db is not None:
        start, end = _period_range(30)
        analytics = Analytics().summary(db.get_snapshots(start, end))
        payload["daily_insight"] = InsightEngine().daily_insight(context, analytics)
    return payload
```

- [ ] **Step 4: Rodar testes**

Run: `pytest tests/test_api.py -v`
Expected: todos passam (o teste existente `test_build_today_payload` chama `build_today(client)` sem `db` — `db=None` mantém compatível, sem `daily_insight`).

- [ ] **Step 5: Commit**

```bash
git add api/services.py tests/test_api.py
git commit -m "feat: API services for trends, activities, activity detail, daily insight"
```

---

## Task 8: API routes + ingestão no startup

**Files:**
- Modify: `api/main.py`
- Test: `tests/test_api.py` (adicionar testes de rota)

- [ ] **Step 1: Adicionar testes de rota ao fim de `tests/test_api.py`**

```python
def test_trends_route():
    with patch("api.main.GarminClient"), patch("api.main.get_db"), \
         patch("api.main.services.build_trends", return_value={"metrics": {}, "insights": []}):
        from api.main import app
        resp = TestClient(app).get("/api/trends?period=30")
    assert resp.status_code == 200
    assert "insights" in resp.json()


def test_activities_route():
    with patch("api.main.GarminClient"), patch("api.main.get_db"), \
         patch("api.main.services.build_activities", return_value=[{"name": "Corrida"}]):
        from api.main import app
        resp = TestClient(app).get("/api/activities?period=30")
    assert resp.status_code == 200
    assert resp.json()[0]["name"] == "Corrida"


def test_activity_detail_route():
    with patch("api.main.GarminClient"), patch("api.main.get_db"), \
         patch("api.main.services.build_activity_detail",
               return_value={"activity": {}, "splits": [], "insight": "ok"}):
        from api.main import app
        resp = TestClient(app).get("/api/activity/1")
    assert resp.status_code == 200
    assert resp.json()["insight"] == "ok"


def test_sync_route():
    with patch("api.main.GarminClient"), patch("api.main.get_db"), \
         patch("api.main.Ingestor") as MockIng:
        MockIng.return_value.sync_today.return_value = None
        from api.main import app
        resp = TestClient(app).post("/api/sync")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
```

- [ ] **Step 2: Rodar — confirmar falha**

Run: `pytest tests/test_api.py -k "route" -v`
Expected: FAIL nas rotas novas (404 / AttributeError get_db).

- [ ] **Step 3: Modificar `api/main.py`**

Adicionar imports (junto aos existentes):
```python
from src.history_db import HistoryDB
from src.ingestor import Ingestor
```

Adicionar singleton de DB após `get_client`:
```python
_db = None


def get_db() -> HistoryDB:
    global _db
    if _db is None:
        _db = HistoryDB()
    return _db
```

Atualizar a rota `today` para passar o db:
```python
@app.get("/api/today")
def today():
    return _safe(lambda: services.build_today(get_client(), get_db()), code=503)
```

Adicionar rotas novas (antes do mount de estáticos no fim):
```python
@app.get("/api/trends")
def trends(period: int = 30):
    return _safe(lambda: services.build_trends(get_db(), period), code=503)


@app.get("/api/activities")
def activities(period: int = 30):
    return _safe(lambda: services.build_activities(get_db(), period), code=503)


@app.get("/api/activity/{activity_id}")
def activity_detail(activity_id: int):
    return _safe(lambda: services.build_activity_detail(get_db(), get_client(), activity_id), code=503)


@app.post("/api/sync")
def sync():
    def _run():
        Ingestor(get_client(), get_db()).sync_today()
        return {"ok": True}
    return _safe(_run, code=503)
```

- [ ] **Step 4: Rodar testes**

Run: `pytest tests/test_api.py -v`
Expected: todos passam.

- [ ] **Step 5: Commit**

```bash
git add api/main.py tests/test_api.py
git commit -m "feat: add trends/activities/activity/sync routes + history DB singleton"
```

---

## Task 9: CLI de backfill

**Files:**
- Create: `scripts/backfill.py`

> Script pra rodar o backfill inicial de 3 meses uma vez, fora do request HTTP
> (evita timeout). Bate API real — validação manual.

- [ ] **Step 1: Criar `scripts/backfill.py`**

```python
"""Backfill inicial do histórico (3 meses). Rodar uma vez:
    python scripts/backfill.py
Throttle embutido para evitar rate limit do Garmin."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.garmin_client import GarminClient
from src.history_db import HistoryDB
from src.ingestor import Ingestor

DAYS = 90

if __name__ == "__main__":
    client = GarminClient()
    db = HistoryDB()
    ing = Ingestor(client, db, sleep_seconds=1.5)
    print(f"Backfill de {DAYS} dias (resume de onde parou)...")
    ing.backfill(days=DAYS)
    rows = db.get_snapshots("2000-01-01", "2100-01-01")
    print(f"OK — {len(rows)} snapshots no history.db")
```

- [ ] **Step 2: Validar manualmente**

Run: `python scripts/backfill.py`
Expected: roda com pausas, imprime contagem de snapshots ao fim. Se 429: o ingestor
faz retry; se persistir, re-rodar (resume).

- [ ] **Step 3: Commit**

```bash
git add scripts/backfill.py
git commit -m "feat: add backfill CLI script for initial 3-month history"
```

---

## Task 10: Frontend — types e api client

**Files:**
- Modify: `web/src/types.ts`
- Modify: `web/src/api.ts`

- [ ] **Step 1: Adicionar tipos ao fim de `web/src/types.ts`**

```typescript
export interface TrendInfo {
  slope: number;
  direction: "subindo" | "descendo" | "estável";
}

export interface MetricTrend {
  series: SeriePoint[];
  trend: TrendInfo;
}

export interface Trends {
  period: number;
  metrics: Record<string, MetricTrend>;
  insights: string[];
}

export interface ActivitySummary {
  activity_id: number;
  date: string;
  name: string;
  type: string;
  is_strength: number;
  distance_m: number | null;
  duration_min: number | null;
  pace_min_km: number | null;
  avg_hr: number | null;
}

export interface Split {
  distance_m: number | null;
  duration_s: number | null;
  pace_min_km: number | null;
  avg_hr: number | null;
  cadence: number | null;
}

export interface ActivityDetail {
  activity: ActivitySummary;
  splits: Split[];
  insight: string;
}
```

E adicionar `daily_insight` à interface `Today` existente (campo opcional):
```typescript
// dentro de interface Today, adicionar:
  daily_insight?: string;
```

- [ ] **Step 2: Adicionar funções ao fim de `web/src/api.ts`**

```typescript
import type { Trends, ActivitySummary, ActivityDetail } from "./types";

export const fetchTrends = (period = 30) => get<Trends>(`/api/trends?period=${period}`);
export const fetchActivities = (period = 30) =>
  get<ActivitySummary[]>(`/api/activities?period=${period}`);
export const fetchActivity = (id: number) => get<ActivityDetail>(`/api/activity/${id}`);

export async function postSync(): Promise<{ ok: boolean }> {
  const resp = await fetch("/api/sync", { method: "POST" });
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({ erro: resp.statusText }));
    throw new Error(body.erro || `Erro ${resp.status}`);
  }
  return resp.json();
}
```

> Nota: `import type {...}` adicional no topo do arquivo é permitido pelo bundler;
> se o linter reclamar de import duplicado, una com o import existente de `./types`.

- [ ] **Step 3: Commit**

```bash
git add web/src/types.ts web/src/api.ts
git commit -m "feat: frontend types and api client for trends/activities"
```

---

## Task 11: Frontend — página Tendências

**Files:**
- Create: `web/src/pages/Tendencias.tsx`

- [ ] **Step 1: Criar `web/src/pages/Tendencias.tsx`**

```tsx
import { useEffect, useState } from "react";
import { fetchTrends } from "../api";
import type { Trends } from "../types";
import Sparkline from "../components/Sparkline";

const LABELS: Record<string, string> = {
  resting_hr: "FC repouso",
  sleep_hours: "Sono (h)",
  stress_avg: "Stress médio",
  body_battery_high: "Body Battery (pico)",
  intensity_minutes: "Minutos de intensidade",
  race_pred_5k: "Previsão 5k (s)",
};

const DIR_COR: Record<string, string> = {
  subindo: "var(--amber)", descendo: "var(--green)", estável: "var(--text-dim)",
};

export default function Tendencias() {
  const [period, setPeriod] = useState(30);
  const [data, setData] = useState<Trends | null>(null);
  const [erro, setErro] = useState("");

  useEffect(() => {
    setData(null);
    setErro("");
    fetchTrends(period).then(setData).catch((e) => setErro(e.message));
  }, [period]);

  return (
    <>
      <div className="page-title">Tendências</div>
      <div className="page-sub">Padrões de saúde e treino + leitura da IA</div>

      <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
        {[7, 30, 90].map((p) => (
          <button key={p} className="nav-item" style={{ width: "auto", borderRadius: 8,
            background: p === period ? "#222" : "var(--surface)", color: p === period ? "#fff" : "var(--text-dim)" }}
            onClick={() => setPeriod(p)}>{p}d</button>
        ))}
      </div>

      {erro && <div className="banner-erro">{erro}</div>}
      {!data && !erro && <div className="page-sub">Carregando…</div>}

      {data && (
        <>
          <div className="card" style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 11, fontWeight: 600, textTransform: "uppercase",
              letterSpacing: ".05em", color: "var(--text-faint)", marginBottom: 8 }}>Insights da IA</div>
            {data.insights.map((ins, i) => (
              <div key={i} style={{ fontSize: 13, color: "var(--text)", marginBottom: 6 }}>• {ins}</div>
            ))}
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            {Object.entries(data.metrics).map(([key, m]) => (
              <div key={key} className="card">
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span style={{ fontSize: 11, color: "var(--text-faint)" }}>{LABELS[key] || key}</span>
                  <span style={{ fontSize: 10, color: DIR_COR[m.trend.direction] }}>{m.trend.direction}</span>
                </div>
                <Sparkline data={m.series} cor={DIR_COR[m.trend.direction]} />
              </div>
            ))}
          </div>
        </>
      )}
    </>
  );
}
```

- [ ] **Step 2: Build pra validar TS**

Run: `cd web && npm run build`
Expected: OK (App ainda não referencia Tendencias — só valida o arquivo compila).

- [ ] **Step 3: Commit**

```bash
git add web/src/pages/Tendencias.tsx
git commit -m "feat: add Tendencias page with period selector and AI insights"
```

---

## Task 12: Frontend — página Treinos

**Files:**
- Create: `web/src/pages/Treinos.tsx`

- [ ] **Step 1: Criar `web/src/pages/Treinos.tsx`**

```tsx
import { useEffect, useState } from "react";
import { fetchActivities, fetchActivity } from "../api";
import type { ActivitySummary, ActivityDetail } from "../types";

function paceLabel(pace: number | null): string {
  if (!pace) return "—";
  const m = Math.floor(pace);
  const s = Math.round((pace - m) * 60);
  return `${m}:${String(s).padStart(2, "0")}/km`;
}

export default function Treinos() {
  const [list, setList] = useState<ActivitySummary[] | null>(null);
  const [erro, setErro] = useState("");
  const [detail, setDetail] = useState<ActivityDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);

  useEffect(() => {
    fetchActivities(30).then(setList).catch((e) => setErro(e.message));
  }, []);

  async function abrir(id: number) {
    setLoadingDetail(true);
    setDetail(null);
    try {
      setDetail(await fetchActivity(id));
    } catch (e) {
      setErro((e as Error).message);
    } finally {
      setLoadingDetail(false);
    }
  }

  if (erro) return <div className="banner-erro">{erro}</div>;
  if (!list) return <div className="page-sub">Carregando…</div>;

  return (
    <>
      <div className="page-title">Treinos</div>
      <div className="page-sub">Últimos 30 dias · clique para detalhes e leitura da IA</div>

      <div style={{ display: "flex", gap: 16 }}>
        <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 8 }}>
          {list.map((a) => (
            <div key={a.activity_id} className="card" style={{ cursor: "pointer",
              borderLeft: `3px solid ${a.is_strength ? "var(--blue)" : "var(--green)"}` }}
              onClick={() => abrir(a.activity_id)}>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ fontSize: 13, color: "#fff" }}>{a.is_strength ? "💪" : "🏃"} {a.name}</span>
                <span style={{ fontSize: 11, color: "var(--text-faint)" }}>{a.date}</span>
              </div>
              <div style={{ fontSize: 11, color: "var(--text-dim)", marginTop: 4 }}>
                {a.duration_min ? `${a.duration_min} min` : ""}
                {a.pace_min_km ? ` · ${paceLabel(a.pace_min_km)}` : ""}
                {a.avg_hr ? ` · ${a.avg_hr} bpm` : ""}
              </div>
            </div>
          ))}
        </div>

        <div style={{ flex: 1 }}>
          {loadingDetail && <div className="page-sub">Analisando…</div>}
          {detail && (
            <div className="card">
              <div style={{ fontSize: 14, color: "#fff", marginBottom: 4 }}>{detail.activity.name}</div>
              <div style={{ fontSize: 12, color: "var(--green)", marginBottom: 12 }}>{detail.insight}</div>
              {detail.splits.length > 0 && (
                <div>
                  <div style={{ fontSize: 11, color: "var(--text-faint)", marginBottom: 6 }}>Splits por volta</div>
                  {detail.splits.map((s, i) => (
                    <div key={i} style={{ display: "flex", justifyContent: "space-between",
                      fontSize: 12, padding: "5px 0", borderBottom: "1px solid #1f1f1f" }}>
                      <span style={{ color: "var(--text-dim)" }}>Km {i + 1}</span>
                      <span style={{ color: "#ccc" }}>{paceLabel(s.pace_min_km)}</span>
                      <span style={{ color: "var(--text-faint)" }}>{s.avg_hr ?? "—"} bpm</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </>
  );
}
```

- [ ] **Step 2: Build pra validar TS**

Run: `cd web && npm run build`
Expected: OK.

- [ ] **Step 3: Commit**

```bash
git add web/src/pages/Treinos.tsx
git commit -m "feat: add Treinos page with splits and AI activity insight"
```

---

## Task 13: Frontend — Hoje enriquecida + navegação + sync

**Files:**
- Modify: `web/src/pages/Hoje.tsx`
- Modify: `web/src/components/Sidebar.tsx`
- Modify: `web/src/App.tsx`

- [ ] **Step 1: Atualizar `web/src/components/Sidebar.tsx`**

Substituir a const `ITEMS`:
```tsx
const ITEMS = [
  { id: "hoje", label: "☀ Hoje" },
  { id: "tendencias", label: "📈 Tendências" },
  { id: "treinos", label: "🏃 Treinos" },
  { id: "plano", label: "📅 Plano Semanal" },
];
```

- [ ] **Step 2: Atualizar `web/src/App.tsx`**

Substituir todo o arquivo:
```tsx
import { useState } from "react";
import Sidebar from "./components/Sidebar";
import Hoje from "./pages/Hoje";
import Tendencias from "./pages/Tendencias";
import Treinos from "./pages/Treinos";
import Plano from "./pages/Plano";

export default function App() {
  const [page, setPage] = useState("hoje");
  return (
    <div className="app-shell">
      <Sidebar page={page} onNavigate={setPage} />
      <main className="main">
        {page === "hoje" && <Hoje />}
        {page === "tendencias" && <Tendencias />}
        {page === "treinos" && <Treinos />}
        {page === "plano" && <Plano />}
      </main>
    </div>
  );
}
```

(Remove referência à página Dados — fundida em Tendências.)

- [ ] **Step 3: Adicionar card de insight do dia + botão sync em `web/src/pages/Hoje.tsx`**

Adicionar import no topo:
```tsx
import { postSync } from "../api";
```

Logo após `const m = data.metrics;` e antes do `return`, adicionar:
```tsx
  const [syncing, setSyncing] = useState(false);
```
(mover para junto dos outros useState no topo do componente — declarar lá:
`const [syncing, setSyncing] = useState(false);`)

Substituir o cabeçalho do `return` (as duas primeiras linhas `page-title`/`page-sub`) por:
```tsx
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <div className="page-title">Status do Dia</div>
          <div className="page-sub">Prontidão para treino hoje</div>
        </div>
        <button className="btn-gen" disabled={syncing}
          onClick={async () => { setSyncing(true); try { await postSync(); } finally { setSyncing(false); } }}>
          {syncing ? "Sincronizando…" : "🔄 Sincronizar"}
        </button>
      </div>
      {data.daily_insight && (
        <div className="card" style={{ marginBottom: 16, borderLeft: "3px solid var(--green)" }}>
          <div style={{ fontSize: 11, color: "var(--text-faint)", marginBottom: 4 }}>💡 Insight do dia</div>
          <div style={{ fontSize: 13, color: "var(--text)" }}>{data.daily_insight}</div>
        </div>
      )}
```

- [ ] **Step 4: Build e validar TS de tudo**

Run: `cd web && npm run build`
Expected: OK, gera `web/dist/`. Corrigir qualquer erro TS antes de seguir.

- [ ] **Step 5: Commit**

```bash
git add web/src/pages/Hoje.tsx web/src/components/Sidebar.tsx web/src/App.tsx
git commit -m "feat: enrich Hoje with daily insight + sync, add nav for new pages"
```

---

## Task 14: Verificação end-to-end

**Files:** nenhum (validação)

- [ ] **Step 1: Rodar suíte completa**

Run: `pytest tests/ -v`
Expected: todos passam (cache, data_processor, health_monitor, training_planner, api, history_db, extractors, ingestor, analytics, insight_engine).

- [ ] **Step 2: Backfill inicial**

Run: `python scripts/backfill.py`
Expected: cria `history.db` com snapshots (~90 dias, alguns campos null em dias sem dado). Throttle visível.

- [ ] **Step 3: Subir API e validar rotas**

Run: `uvicorn api.main:app --port 8000`
Verificar:
- `http://localhost:8000/api/trends?period=30` → JSON com metrics + insights
- `http://localhost:8000/api/activities?period=30` → lista de treinos
- `http://localhost:8000/api/today` → inclui `daily_insight`

- [ ] **Step 4: Build frontend + validar no browser**

Run: `cd web && npm run build` então abrir `http://localhost:8000`.
Verificar: Tendências (gráficos + insights), Treinos (lista → detalhe com splits),
Hoje (card insight do dia + botão Sincronizar).

- [ ] **Step 5: Confirmar Haiku usado nos insights**

Verificar nos logs/custo que os insights chamaram Haiku (depth="quick"), não Sonnet.

---

## Verificação Final

- [ ] `pytest tests/ -v` → todos passam
- [ ] `python scripts/backfill.py` → history.db populado, resume se re-rodado
- [ ] Tendências mostra séries + tendência (subindo/descendo/estável) + insights Haiku
- [ ] Treinos lista treinos; detalhe busca splits sob demanda + comentário IA
- [ ] Hoje mostra insight do dia consolidado + botão Sincronizar funciona
- [ ] Plano Semanal e auth Garmin continuam funcionando (não quebrados)
- [ ] Ingestor throttla e não dispara 429 no uso normal
