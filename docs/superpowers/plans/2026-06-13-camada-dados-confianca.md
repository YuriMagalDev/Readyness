# Camada de Dados + Confiança — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Centralizar um catálogo curado de métricas Garmin + 4 check-ins manuais numa tabela longa `metric_value` com frescor por métrica, expondo uma API que entrega valor + contexto de confiança.

**Architecture:** Catálogo estático em código define as métricas esperadas e suas cadências. Normalizadores puros por domínio convertem respostas cruas do Garmin em linhas `(date, metric_key, value, measured_at, source)`. O Ingestor orquestra fetch→normalize→upsert e faz dual-write no `daily_snapshot` legado. Status (fresco/velho/ausente/estimado) é calculado na leitura cruzando catálogo × valores.

**Tech Stack:** Python 3.11, sqlite3, FastAPI, pytest, garminconnect.

---

### Task 1: Tabela `metric_value` + acessores em HistoryDB

**Files:**
- Modify: `src/history_db.py`
- Test: `tests/test_history_db.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_history_db.py`:

```python
def test_metric_value_upsert_and_get(tmp_path):
    from src.history_db import HistoryDB
    db = HistoryDB(db_path=str(tmp_path / "h.db"))
    db.upsert_metric("2026-06-13", "vo2max", 48.0, "2026-06-13T06:40", "garmin")
    rows = db.get_metrics("2026-06-13")
    assert rows == [{"date": "2026-06-13", "metric_key": "vo2max", "value": 48.0,
                     "measured_at": "2026-06-13T06:40", "source": "garmin"}]


def test_metric_value_upsert_overwrites(tmp_path):
    from src.history_db import HistoryDB
    db = HistoryDB(db_path=str(tmp_path / "h.db"))
    db.upsert_metric("2026-06-13", "weight_kg", 80.0, "2026-06-13T07:00", "garmin")
    db.upsert_metric("2026-06-13", "weight_kg", 79.5, "2026-06-13T07:05", "garmin")
    rows = db.get_metrics("2026-06-13")
    assert len(rows) == 1 and rows[0]["value"] == 79.5


def test_metric_series_range(tmp_path):
    from src.history_db import HistoryDB
    db = HistoryDB(db_path=str(tmp_path / "h.db"))
    db.upsert_metric("2026-06-10", "weight_kg", 81.0, "2026-06-10T07:00", "garmin")
    db.upsert_metric("2026-06-13", "weight_kg", 80.0, "2026-06-13T07:00", "garmin")
    db.upsert_metric("2026-06-13", "vo2max", 48.0, "2026-06-13T06:40", "garmin")
    series = db.get_metric_series("weight_kg", "2026-06-01", "2026-06-30")
    assert [r["value"] for r in series] == [81.0, 80.0]  # ordenado por data asc
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_history_db.py -k metric_value -v`
Expected: FAIL — `AttributeError: 'HistoryDB' object has no attribute 'upsert_metric'`

- [ ] **Step 3: Write minimal implementation**

In `src/history_db.py`, inside `_init_db`'s `with self._connect() as conn:` block, after the `ai_insights` CREATE TABLE, add:

```python
            conn.execute(
                "CREATE TABLE IF NOT EXISTS metric_value ("
                "date TEXT NOT NULL, metric_key TEXT NOT NULL, value REAL, "
                "measured_at TEXT, source TEXT NOT NULL, "
                "PRIMARY KEY (date, metric_key))"
            )
```

Add these methods to the `HistoryDB` class:

```python
    def upsert_metric(self, date: str, metric_key: str, value, measured_at, source: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO metric_value (date, metric_key, value, measured_at, source) "
                "VALUES (?, ?, ?, ?, ?) ON CONFLICT(date, metric_key) DO UPDATE SET "
                "value=excluded.value, measured_at=excluded.measured_at, source=excluded.source",
                (date, metric_key, value, measured_at, source),
            )

    def get_metrics(self, date: str) -> list:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT date, metric_key, value, measured_at, source FROM metric_value "
                "WHERE date = ? ORDER BY metric_key", (date,)
            ).fetchall()
        return [dict(r) for r in rows]

    def get_metric_series(self, metric_key: str, start: str, end: str) -> list:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT date, metric_key, value, measured_at, source FROM metric_value "
                "WHERE metric_key = ? AND date >= ? AND date <= ? ORDER BY date ASC",
                (metric_key, start, end)
            ).fetchall()
        return [dict(r) for r in rows]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_history_db.py -k metric -v`
Expected: PASS (3 new tests)

- [ ] **Step 5: Commit**

```bash
git add src/history_db.py tests/test_history_db.py
git commit -m "feat: metric_value table + accessors in HistoryDB"
```

---

### Task 2: Catálogo de métricas (`metric_catalog.py`)

**Files:**
- Create: `src/metric_catalog.py`
- Test: `tests/test_metric_catalog.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_metric_catalog.py`:

```python
from src.metric_catalog import CATALOG, MetricSpec, CADENCE_WINDOW_DAYS, by_domain


def test_catalog_keys_unique():
    keys = [m.key for m in CATALOG]
    assert len(keys) == len(set(keys))


def test_catalog_cadences_valid():
    valid = {"diaria", "corpo", "fitness", "evento"}
    assert all(m.cadencia in valid for m in CATALOG)


def test_catalog_domains_valid():
    valid = {"prontidao", "recuperacao", "atividade", "corpo", "checkin"}
    assert all(m.dominio in valid for m in CATALOG)


def test_catalog_has_expected_metrics():
    keys = {m.key for m in CATALOG}
    for k in ["vo2max", "sleep_hours", "resting_hr", "weight_kg",
              "steps", "hidratacao", "race_pred_5k"]:
        assert k in keys


def test_race_predictions_are_estimado():
    race = [m for m in CATALOG if m.key.startswith("race_pred_")]
    assert len(race) == 4
    assert all(m.source_default == "estimado" for m in race)


def test_checkins_are_manual():
    checkins = by_domain("checkin")
    assert {m.key for m in checkins} == {"hidratacao", "energia", "soreness", "alimentacao"}
    assert all(m.source_default == "manual" for m in checkins)


def test_cadence_windows():
    assert CADENCE_WINDOW_DAYS == {"diaria": 0, "corpo": 7, "fitness": 14}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_metric_catalog.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.metric_catalog'`

- [ ] **Step 3: Write minimal implementation**

Create `src/metric_catalog.py`:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class MetricSpec:
    key: str
    label: str
    unidade: str
    dominio: str        # prontidao | recuperacao | atividade | corpo | checkin
    cadencia: str       # diaria | corpo | fitness | evento
    source_default: str = "garmin"


# Janela de frescor em dias. evento é tratado à parte (sempre fresco se existe).
CADENCE_WINDOW_DAYS = {"diaria": 0, "corpo": 7, "fitness": 14}

CATALOG = [
    # Prontidão / treino
    MetricSpec("training_readiness", "Training readiness", "", "prontidao", "diaria"),
    MetricSpec("vo2max", "VO2max", "", "prontidao", "fitness"),
    MetricSpec("endurance_score", "Endurance score", "", "prontidao", "fitness"),
    MetricSpec("training_status", "Training status", "", "prontidao", "diaria"),
    MetricSpec("race_pred_5k", "Prova 5k", "time", "prontidao", "fitness", "estimado"),
    MetricSpec("race_pred_10k", "Prova 10k", "time", "prontidao", "fitness", "estimado"),
    MetricSpec("race_pred_21k", "Prova 21k", "time", "prontidao", "fitness", "estimado"),
    MetricSpec("race_pred_42k", "Prova 42k", "time", "prontidao", "fitness", "estimado"),
    # Recuperação / sono
    MetricSpec("sleep_hours", "Sono", " h", "recuperacao", "diaria"),
    MetricSpec("sleep_deep_h", "Sono profundo", " h", "recuperacao", "diaria"),
    MetricSpec("sleep_light_h", "Sono leve", " h", "recuperacao", "diaria"),
    MetricSpec("sleep_rem_h", "Sono REM", " h", "recuperacao", "diaria"),
    MetricSpec("resting_hr", "FC repouso", " bpm", "recuperacao", "diaria"),
    MetricSpec("hrv_overnight", "HRV noturno", " ms", "recuperacao", "diaria"),
    MetricSpec("body_battery_high", "Body Battery alta", "", "recuperacao", "diaria"),
    MetricSpec("body_battery_low", "Body Battery baixa", "", "recuperacao", "diaria"),
    MetricSpec("stress_avg", "Stress médio", "", "recuperacao", "diaria"),
    MetricSpec("stress_max", "Stress máx", "", "recuperacao", "diaria"),
    MetricSpec("respiration_avg", "Respiração", " rpm", "recuperacao", "diaria"),
    MetricSpec("spo2_avg", "SpO2", "%", "recuperacao", "diaria"),
    # Atividade diária
    MetricSpec("steps", "Passos", "", "atividade", "diaria"),
    MetricSpec("floors", "Andares", "", "atividade", "diaria"),
    MetricSpec("intensity_minutes", "Min. intensidade", " min", "atividade", "diaria"),
    MetricSpec("calories_total", "Calorias", " kcal", "atividade", "diaria"),
    # Corpo
    MetricSpec("weight_kg", "Peso", " kg", "corpo", "corpo"),
    MetricSpec("body_fat_pct", "% gordura", "%", "corpo", "corpo"),
    MetricSpec("lean_mass_kg", "Massa magra", " kg", "corpo", "corpo"),
    # Check-ins manuais (1-5)
    MetricSpec("hidratacao", "Hidratação", "", "checkin", "diaria", "manual"),
    MetricSpec("energia", "Energia/disposição", "", "checkin", "diaria", "manual"),
    MetricSpec("soreness", "Dor muscular", "", "checkin", "diaria", "manual"),
    MetricSpec("alimentacao", "Qualidade alimentação", "", "checkin", "diaria", "manual"),
]

CATALOG_BY_KEY = {m.key: m for m in CATALOG}
DOMAIN_ORDER = ["prontidao", "recuperacao", "atividade", "corpo", "checkin"]


def by_domain(dominio: str) -> list:
    return [m for m in CATALOG if m.dominio == dominio]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_metric_catalog.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add src/metric_catalog.py tests/test_metric_catalog.py
git commit -m "feat: static metric catalog (~20 metrics + 4 manual checkins)"
```

---

### Task 3: Cálculo de status (`metric_status.py`)

**Files:**
- Create: `src/metric_status.py`
- Test: `tests/test_metric_status.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_metric_status.py`:

```python
import datetime
from src.metric_status import compute_status

TODAY = datetime.date(2026, 6, 13)


def test_estimado_overrides_everything():
    assert compute_status("fitness", "estimado", "2026-01-01T00:00", TODAY) == "estimado"


def test_ausente_when_no_measured_at():
    assert compute_status("diaria", "garmin", None, TODAY) == "ausente"


def test_diaria_fresco_today():
    assert compute_status("diaria", "garmin", "2026-06-13T06:40", TODAY) == "fresco"


def test_diaria_velho_yesterday():
    assert compute_status("diaria", "garmin", "2026-06-12T06:40", TODAY) == "velho"


def test_corpo_fresco_within_7_days():
    assert compute_status("corpo", "garmin", "2026-06-10T07:00", TODAY) == "fresco"


def test_corpo_velho_after_7_days():
    assert compute_status("corpo", "garmin", "2026-06-05T07:00", TODAY) == "velho"


def test_fitness_fresco_within_14_days():
    assert compute_status("fitness", "garmin", "2026-06-01T00:00", TODAY) == "fresco"


def test_fitness_velho_after_14_days():
    assert compute_status("fitness", "garmin", "2026-05-20T00:00", TODAY) == "velho"


def test_evento_always_fresco_if_present():
    assert compute_status("evento", "garmin", "2025-01-01T00:00", TODAY) == "fresco"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_metric_status.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.metric_status'`

- [ ] **Step 3: Write minimal implementation**

Create `src/metric_status.py`:

```python
import datetime
from src.metric_catalog import CADENCE_WINDOW_DAYS


def compute_status(cadencia: str, source: str, measured_at, today: datetime.date) -> str:
    """Calcula o badge de confiança de uma métrica na leitura.
    Retorna: estimado | ausente | fresco | velho."""
    if source == "estimado":
        return "estimado"
    if measured_at is None:
        return "ausente"
    if cadencia == "evento":
        return "fresco"
    measured_date = datetime.date.fromisoformat(measured_at[:10])
    age_days = (today - measured_date).days
    window = CADENCE_WINDOW_DAYS[cadencia]
    return "fresco" if age_days <= window else "velho"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_metric_status.py -v`
Expected: PASS (9 tests)

- [ ] **Step 5: Commit**

```bash
git add src/metric_status.py tests/test_metric_status.py
git commit -m "feat: compute_status — per-metric freshness badge"
```

---

### Task 4: Normalizador de recuperação/sono

**Files:**
- Create: `src/collectors/__init__.py` (vazio), `src/collectors/recuperacao.py`
- Test: `tests/test_collectors.py`

Cada normalizador é uma função pura: recebe respostas cruas do Garmin + o dia, devolve linhas `{"metric_key", "value", "measured_at", "source"}`. Linhas só são geradas quando há valor (campo ausente → não entra; a API marca ⚪ ausente via catálogo).

- [ ] **Step 1: Write the failing test**

Create `tests/test_collectors.py`:

```python
from src.collectors.recuperacao import normalize_recuperacao

DAY = "2026-06-13"


def _summary():
    return {"restingHeartRate": 52, "averageStressLevel": 30, "maxStressLevel": 75,
            "averageSpo2": 96, "bodyBatteryHighestValue": 90, "bodyBatteryLowestValue": 20,
            "avgWakingRespirationValue": 14}


def _sleep():
    return {"dailySleepDTO": {"sleepTimeSeconds": 25200, "deepSleepSeconds": 5400,
            "lightSleepSeconds": 14400, "remSleepSeconds": 5400}}


def test_recuperacao_extracts_core_metrics():
    rows = normalize_recuperacao(DAY, summary=_summary(), sleep=_sleep(),
                                 hrv=None, respiration=None)
    by_key = {r["metric_key"]: r for r in rows}
    assert by_key["resting_hr"]["value"] == 52
    assert by_key["resting_hr"]["source"] == "garmin"
    assert by_key["resting_hr"]["measured_at"] == "2026-06-13T00:00"
    assert by_key["sleep_hours"]["value"] == 7.0
    assert by_key["sleep_deep_h"]["value"] == 1.5
    assert by_key["stress_avg"]["value"] == 30
    assert by_key["spo2_avg"]["value"] == 96
    assert by_key["body_battery_high"]["value"] == 90


def test_recuperacao_skips_missing_fields():
    rows = normalize_recuperacao(DAY, summary={}, sleep={}, hrv=None, respiration=None)
    assert rows == []


def test_recuperacao_hrv_when_present():
    rows = normalize_recuperacao(DAY, summary={}, sleep={},
                                 hrv={"hrvSummary": {"lastNightAvg": 42}}, respiration=None)
    by_key = {r["metric_key"]: r for r in rows}
    assert by_key["hrv_overnight"]["value"] == 42
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_collectors.py -k recuperacao -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.collectors'`

- [ ] **Step 3: Write minimal implementation**

Create empty `src/collectors/__init__.py`. Create `src/collectors/recuperacao.py`:

```python
def _row(key, value, day):
    return {"metric_key": key, "value": value, "measured_at": f"{day}T00:00", "source": "garmin"}


def _hours(seconds):
    return round(seconds / 3600, 1) if seconds else None


def normalize_recuperacao(day, summary, sleep, hrv, respiration) -> list:
    summary = summary or {}
    sleep_dto = (sleep or {}).get("dailySleepDTO", {}) or {}
    rows = []

    simple = [
        ("resting_hr", summary.get("restingHeartRate")),
        ("stress_avg", summary.get("averageStressLevel")),
        ("stress_max", summary.get("maxStressLevel")),
        ("spo2_avg", summary.get("averageSpo2")),
        ("body_battery_high", summary.get("bodyBatteryHighestValue")),
        ("body_battery_low", summary.get("bodyBatteryLowestValue")),
        ("respiration_avg", summary.get("avgWakingRespirationValue")),
    ]
    sleep_metrics = [
        ("sleep_hours", _hours(sleep_dto.get("sleepTimeSeconds"))),
        ("sleep_deep_h", _hours(sleep_dto.get("deepSleepSeconds"))),
        ("sleep_light_h", _hours(sleep_dto.get("lightSleepSeconds"))),
        ("sleep_rem_h", _hours(sleep_dto.get("remSleepSeconds"))),
    ]
    hrv_val = (hrv or {}).get("hrvSummary", {}).get("lastNightAvg") if hrv else None
    extra = [("hrv_overnight", hrv_val)]

    for key, val in simple + sleep_metrics + extra:
        if val is not None:
            rows.append(_row(key, val, day))
    return rows
```

(O parâmetro `respiration` fica reservado pra um endpoint dedicado futuro; hoje a respiração vem do summary. Mantido na assinatura pro orquestrador passar `None` sem quebrar.)

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_collectors.py -k recuperacao -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/collectors/__init__.py src/collectors/recuperacao.py tests/test_collectors.py
git commit -m "feat: recuperacao normalizer (sleep, hr, stress, spo2, battery, hrv)"
```

---

### Task 5: Normalizador de atividade diária

**Files:**
- Create: `src/collectors/atividade.py`
- Test: `tests/test_collectors.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_collectors.py`:

```python
from src.collectors.atividade import normalize_atividade


def test_atividade_extracts_daily_metrics():
    summary = {"totalSteps": 8000, "floorsAscended": 5,
               "moderateIntensityMinutes": 20, "vigorousIntensityMinutes": 5,
               "totalKilocalories": 2200}
    rows = normalize_atividade(DAY, summary)
    by_key = {r["metric_key"]: r for r in rows}
    assert by_key["steps"]["value"] == 8000
    assert by_key["floors"]["value"] == 5
    assert by_key["intensity_minutes"]["value"] == 25  # moderate + vigorous
    assert by_key["calories_total"]["value"] == 2200
    assert by_key["steps"]["measured_at"] == "2026-06-13T00:00"


def test_atividade_intensity_none_when_both_absent():
    rows = normalize_atividade(DAY, {"totalSteps": 100})
    keys = {r["metric_key"] for r in rows}
    assert "intensity_minutes" not in keys
    assert "steps" in keys
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_collectors.py -k atividade -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.collectors.atividade'`

- [ ] **Step 3: Write minimal implementation**

Create `src/collectors/atividade.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_collectors.py -k atividade -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add src/collectors/atividade.py tests/test_collectors.py
git commit -m "feat: atividade normalizer (steps, floors, intensity, calories)"
```

---

### Task 6: Normalizador de prontidão

**Files:**
- Create: `src/collectors/prontidao.py`
- Test: `tests/test_collectors.py` (append)

`measured_at` das predições de prova e do readiness vem do dia (`{day}T00:00`). Predições têm `source="estimado"`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_collectors.py`:

```python
from src.collectors.prontidao import normalize_prontidao


def test_prontidao_extracts_metrics():
    rows = normalize_prontidao(
        DAY,
        readiness={"score": 72},
        max_metrics=[{"generic": {"vo2MaxValue": 48.0}}],
        endurance={"overallScore": 5600},
        race={"time5K": 1758, "time10K": 3700,
              "timeHalfMarathon": 8200, "timeMarathon": 17000},
    )
    by_key = {r["metric_key"]: r for r in rows}
    assert by_key["training_readiness"]["value"] == 72
    assert by_key["vo2max"]["value"] == 48.0
    assert by_key["endurance_score"]["value"] == 5600
    assert by_key["race_pred_5k"]["value"] == 1758
    assert by_key["race_pred_5k"]["source"] == "estimado"
    assert by_key["vo2max"]["source"] == "garmin"


def test_prontidao_skips_missing():
    rows = normalize_prontidao(DAY, readiness=None, max_metrics=None,
                               endurance=None, race=None)
    assert rows == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_collectors.py -k prontidao -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.collectors.prontidao'`

- [ ] **Step 3: Write minimal implementation**

Create `src/collectors/prontidao.py`:

```python
def _row(key, value, day, source="garmin"):
    return {"metric_key": key, "value": value, "measured_at": f"{day}T00:00", "source": source}


def _vo2max(max_metrics):
    if not max_metrics or not isinstance(max_metrics, list):
        return None
    return (max_metrics[0] or {}).get("generic", {}).get("vo2MaxValue")


def normalize_prontidao(day, readiness, max_metrics, endurance, race) -> list:
    rows = []
    garmin_vals = [
        ("training_readiness", (readiness or {}).get("score") if readiness else None),
        ("vo2max", _vo2max(max_metrics)),
        ("endurance_score", (endurance or {}).get("overallScore") if endurance else None),
    ]
    for key, val in garmin_vals:
        if val is not None:
            rows.append(_row(key, val, day))

    race = race or {}
    race_vals = [
        ("race_pred_5k", race.get("time5K")),
        ("race_pred_10k", race.get("time10K")),
        ("race_pred_21k", race.get("timeHalfMarathon")),
        ("race_pred_42k", race.get("timeMarathon")),
    ]
    for key, val in race_vals:
        if val is not None:
            rows.append(_row(key, val, day, source="estimado"))
    return rows
```

(`training_status` não é normalizado aqui — o endpoint do FR55 é instável; entra como ⚪ ausente via catálogo. Adicionar quando confirmado.)

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_collectors.py -k prontidao -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add src/collectors/prontidao.py tests/test_collectors.py
git commit -m "feat: prontidao normalizer (readiness, vo2max, endurance, race preds)"
```

---

### Task 7: Normalizador de corpo

**Files:**
- Create: `src/collectors/corpo.py`
- Test: `tests/test_collectors.py` (append)

Composição corporal traz timestamp real da pesagem — usar como `measured_at` (não o dia).

- [ ] **Step 1: Write the failing test**

Append to `tests/test_collectors.py`:

```python
from src.collectors.corpo import normalize_corpo


def test_corpo_extracts_weight_with_real_measured_at():
    body = {"dateWeightList": [{
        "weight": 80500, "bodyFat": 18.5, "muscleMass": 60000,
        "date": "2026-06-13", "timestampGMT": 1781000000000,
    }]}
    rows = normalize_corpo(DAY, body)
    by_key = {r["metric_key"]: r for r in rows}
    assert by_key["weight_kg"]["value"] == 80.5      # gramas → kg
    assert by_key["body_fat_pct"]["value"] == 18.5
    assert by_key["lean_mass_kg"]["value"] == 60.0
    assert by_key["weight_kg"]["measured_at"].startswith("2026-06-13")


def test_corpo_empty_when_no_weigh_in():
    assert normalize_corpo(DAY, {"dateWeightList": []}) == []
    assert normalize_corpo(DAY, None) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_collectors.py -k corpo -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.collectors.corpo'`

- [ ] **Step 3: Write minimal implementation**

Create `src/collectors/corpo.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_collectors.py -k corpo -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add src/collectors/corpo.py tests/test_collectors.py
git commit -m "feat: corpo normalizer (weight, body fat, lean mass)"
```

---

### Task 8: Wrappers cacheados novos no GarminClient

**Files:**
- Modify: `src/garmin_client.py`
- Test: `tests/test_garmin_client.py` (new)

Cada wrapper segue o padrão existente `_cached(key, fetch_fn)`. Chave inclui o dia/data pra cache diário.

- [ ] **Step 1: Write the failing test**

Create `tests/test_garmin_client.py`:

```python
from unittest.mock import MagicMock, patch


def _client_with_stub():
    # Evita login real: injeta cliente Garmin e cache em memória
    from src.garmin_client import GarminClient
    gc = GarminClient.__new__(GarminClient)  # sem __init__ (não autentica)
    from src.cache import Cache
    import tempfile, os
    gc._cache = Cache(db_path=os.path.join(tempfile.mkdtemp(), "c.db"), ttl_hours=6)
    gc._client = MagicMock()
    return gc


def test_get_training_readiness_caches():
    gc = _client_with_stub()
    gc._client.get_morning_training_readiness.return_value = {"score": 70}
    out = gc.get_training_readiness("2026-06-13")
    assert out == {"score": 70}
    gc.get_training_readiness("2026-06-13")  # 2ª vez = cache
    assert gc._client.get_morning_training_readiness.call_count == 1


def test_get_body_composition_caches():
    gc = _client_with_stub()
    gc._client.get_body_composition.return_value = {"dateWeightList": []}
    out = gc.get_body_composition("2026-06-06", "2026-06-13")
    assert out == {"dateWeightList": []}
    gc.get_body_composition("2026-06-06", "2026-06-13")
    assert gc._client.get_body_composition.call_count == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_garmin_client.py -v`
Expected: FAIL — `AttributeError: 'GarminClient' object has no attribute 'get_training_readiness'`

- [ ] **Step 3: Write minimal implementation**

In `src/garmin_client.py`, add these methods to the `GarminClient` class (after `get_activities_by_date`):

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_garmin_client.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add src/garmin_client.py tests/test_garmin_client.py
git commit -m "feat: cached GarminClient wrappers (readiness, vo2max, endurance, hrv, body comp)"
```

---

### Task 9: Ingestor roda coletores + dual-write

**Files:**
- Modify: `src/ingestor.py`
- Test: `tests/test_ingestor.py` (append)

`_write_day` passa a, além do dual-write do snapshot legado, chamar os normalizadores e gravar linhas `metric_value`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_ingestor.py`:

```python
def _client_full():
    c = _client()  # reusa o mock base do arquivo
    c.get_training_readiness.return_value = {"score": 70}
    c.get_max_metrics.return_value = [{"generic": {"vo2MaxValue": 48.0}}]
    c.get_endurance_score.return_value = {"overallScore": 5600}
    c.get_hrv.return_value = None
    c.get_body_composition.return_value = {"dateWeightList": [
        {"weight": 80000, "bodyFat": 18.0, "muscleMass": 60000, "date": "2026-06-10"}]}
    return c


def test_sync_today_writes_metric_value_and_snapshot(tmp_path):
    from src.history_db import HistoryDB
    db = HistoryDB(db_path=str(tmp_path / "h.db"))
    ing = Ingestor(_client_full(), db, sleep_seconds=0)
    ing.sync_today(today=datetime.date(2026, 6, 10))

    # dual-write: snapshot legado ainda preenchido
    snaps = db.get_snapshots("2026-06-01", "2026-06-30")
    assert len(snaps) == 1

    # metric_value preenchido
    metrics = {m["metric_key"]: m for m in db.get_metrics("2026-06-10")}
    assert metrics["resting_hr"]["value"] == 52
    assert metrics["steps"]["value"] == 8000
    assert metrics["vo2max"]["value"] == 48.0
    assert metrics["race_pred_5k"]["source"] == "estimado"
    assert metrics["weight_kg"]["value"] == 80.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_ingestor.py -k metric_value -v`
Expected: FAIL — `get_metrics` retorna vazio (KeyError) porque `_write_day` ainda não grava metric_value.

- [ ] **Step 3: Write minimal implementation**

In `src/ingestor.py`, add imports at the top:

```python
from src.collectors.recuperacao import normalize_recuperacao
from src.collectors.atividade import normalize_atividade
from src.collectors.prontidao import normalize_prontidao
from src.collectors.corpo import normalize_corpo
import datetime as _dt
```

Replace the `_write_day` method with:

```python
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
        sleep = self._safe_call(lambda: self._client.get_sleep(1))
        sleep_one = sleep[0] if isinstance(sleep, list) and sleep else (sleep or {})
        readiness = self._safe_call(lambda: self._client.get_training_readiness(day))
        max_metrics = self._safe_call(lambda: self._client.get_max_metrics(day))
        endurance = self._safe_call(lambda: self._client.get_endurance_score(day))
        hrv = self._safe_call(lambda: self._client.get_hrv(day))
        start = (_dt.date.fromisoformat(day) - _dt.timedelta(days=7)).isoformat()
        body = self._safe_call(lambda: self._client.get_body_composition(start, day))

        rows = []
        rows += normalize_recuperacao(day, summary=summary, sleep=sleep_one,
                                      hrv=hrv, respiration=None)
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
```

Note: `get_sleep` no mock base de `_client()` não existe — adicione no helper `_client()` (topo do arquivo) a linha `c.get_sleep.return_value = [{"dailySleepDTO": {"sleepTimeSeconds": 25200, "deepSleepSeconds": 5400, "lightSleepSeconds": 14400, "remSleepSeconds": 5400}}]` para os testes existentes seguirem passando.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_ingestor.py -v`
Expected: PASS (todos — novos + existentes; snapshot dual-write intacto)

- [ ] **Step 5: Commit**

```bash
git add src/ingestor.py tests/test_ingestor.py
git commit -m "feat: ingestor writes metric_value via collectors + dual-writes snapshot"
```

---

### Task 10: `build_metrics` cruza catálogo × valores com status

**Files:**
- Modify: `api/services.py`
- Test: `tests/test_api.py` (append)

Carry-forward para `corpo`/`fitness`: busca o valor mais recente ≤ data via `get_metric_series`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_api.py`:

```python
import datetime as _dt2


def test_build_metrics_groups_and_status():
    db = _MM()
    # valores de hoje
    db.get_metrics.return_value = [
        {"date": "2026-06-13", "metric_key": "resting_hr", "value": 52,
         "measured_at": "2026-06-13T00:00", "source": "garmin"},
        {"date": "2026-06-13", "metric_key": "race_pred_5k", "value": 1758,
         "measured_at": "2026-06-13T00:00", "source": "estimado"},
    ]
    # carry-forward (corpo/fitness) busca série; peso medido há 3 dias
    db.get_metric_series.return_value = [
        {"date": "2026-06-10", "metric_key": "weight_kg", "value": 80.0,
         "measured_at": "2026-06-10T07:00", "source": "garmin"}]
    payload = services.build_metrics(db, "2026-06-13", today=_dt2.date(2026, 6, 13))

    dominios = payload["dominios"]
    rec = {m["key"]: m for m in dominios["recuperacao"]}
    assert rec["resting_hr"]["status"] == "fresco"
    assert rec["hrv_overnight"]["status"] == "ausente"  # sem dado → ausente
    pront = {m["key"]: m for m in dominios["prontidao"]}
    assert pront["race_pred_5k"]["status"] == "estimado"
    corpo = {m["key"]: m for m in dominios["corpo"]}
    assert corpo["weight_kg"]["value"] == 80.0
    assert corpo["weight_kg"]["status"] == "fresco"  # 3 dias < janela 7d
    assert corpo["weight_kg"]["measured_at"] == "2026-06-10T07:00"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_api.py -k build_metrics -v`
Expected: FAIL — `AttributeError: module 'api.services' has no attribute 'build_metrics'`

- [ ] **Step 3: Write minimal implementation**

In `api/services.py`, add imports at the top:

```python
import datetime as _dt
from src.metric_catalog import CATALOG, DOMAIN_ORDER
from src.metric_status import compute_status
```

Add these functions:

```python
def build_metrics(db, date: str, today: _dt.date = None) -> dict:
    today = today or _dt.date.today()
    rows_today = {r["metric_key"]: r for r in db.get_metrics(date)}

    dominios = {d: [] for d in DOMAIN_ORDER}
    for spec in CATALOG:
        row = rows_today.get(spec.key)
        # carry-forward pra métricas corpo/fitness sem valor hoje
        if row is None and spec.cadencia in ("corpo", "fitness"):
            row = _latest_on_or_before(db, spec.key, date)

        if row is None:
            value, measured_at, source = None, None, spec.source_default
        else:
            value, measured_at, source = row["value"], row["measured_at"], row["source"]

        status = compute_status(spec.cadencia, source, measured_at, today)
        dominios[spec.dominio].append({
            "key": spec.key, "label": spec.label, "value": value,
            "unidade": spec.unidade, "measured_at": measured_at,
            "status": status, "source": source,
        })
    return {"date": date, "dominios": dominios}


def _latest_on_or_before(db, metric_key: str, date: str):
    start = (_dt.date.fromisoformat(date) - _dt.timedelta(days=60)).isoformat()
    series = db.get_metric_series(metric_key, start, date)
    return series[-1] if series else None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_api.py -k build_metrics -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add api/services.py tests/test_api.py
git commit -m "feat: build_metrics — catalog x values with per-metric status + carry-forward"
```

---

### Task 11: Endpoints `GET /api/metrics` e `POST /api/checkin`

**Files:**
- Modify: `api/main.py`, `api/services.py`
- Test: `tests/test_api.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_api.py`:

```python
def test_save_checkin_writes_manual_rows():
    db = _MM()
    services.save_checkin(db, {"hidratacao": 3, "energia": 4}, today=_dt2.date(2026, 6, 13))
    keys = [c.args[1] for c in db.upsert_metric.call_args_list]
    assert "hidratacao" in keys and "energia" in keys
    # source manual
    assert all(c.args[4] == "manual" for c in db.upsert_metric.call_args_list)


def test_save_checkin_rejects_out_of_range():
    db = _MM()
    import pytest
    with pytest.raises(ValueError):
        services.save_checkin(db, {"hidratacao": 9}, today=_dt2.date(2026, 6, 13))


def test_metrics_route():
    with patch("api.main.get_db"), \
         patch("api.main.services.build_metrics", return_value={"date": "2026-06-13", "dominios": {}}):
        from api.main import app
        resp = TestClient(app).get("/api/metrics?date=2026-06-13")
    assert resp.status_code == 200
    assert resp.json()["date"] == "2026-06-13"


def test_checkin_route():
    with patch("api.main.get_db"), \
         patch("api.main.services.save_checkin", return_value={"ok": True}) as mock_save:
        from api.main import app
        resp = TestClient(app).post("/api/checkin", json={"hidratacao": 3})
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    assert mock_save.called


def test_checkin_route_invalid_returns_422():
    with patch("api.main.get_db"), \
         patch("api.main.services.save_checkin", side_effect=ValueError("1-5")):
        from api.main import app
        resp = TestClient(app).post("/api/checkin", json={"hidratacao": 9})
    assert resp.status_code == 422
    assert "erro" in resp.json()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_api.py -k "checkin or metrics_route" -v`
Expected: FAIL — `save_checkin` não existe / rotas 404.

- [ ] **Step 3: Write minimal implementation**

In `api/services.py`, add:

```python
_CHECKIN_KEYS = {"hidratacao", "energia", "soreness", "alimentacao"}


def save_checkin(db, payload: dict, today: _dt.date = None) -> dict:
    today = today or _dt.date.today()
    now = _dt.datetime.now().isoformat(timespec="minutes")
    day = today.isoformat()
    for key, val in payload.items():
        if key not in _CHECKIN_KEYS:
            continue
        if not isinstance(val, int) or not (1 <= val <= 5):
            raise ValueError(f"{key} deve ser inteiro 1-5")
        db.upsert_metric(day, key, val, now, "manual")
    return {"ok": True}
```

In `api/main.py`, the fastapi import already includes `Body` (from a previous feature). Add these routes before the StaticFiles mount:

```python
@app.get("/api/metrics")
def metrics(date: str = None):
    import datetime as _d
    d = date or _d.date.today().isoformat()
    return _safe(lambda: services.build_metrics(get_db(), d), code=503)


@app.post("/api/checkin")
def checkin(payload: dict = Body(default={})):
    def _run():
        return services.save_checkin(get_db(), payload)
    try:
        return _run()
    except ValueError as e:
        return JSONResponse(status_code=422, content={"erro": str(e)})
    except Exception as e:  # noqa: BLE001
        return JSONResponse(status_code=503, content={"erro": str(e)})
```

If `Body` is not yet imported in `api/main.py`, change `from fastapi import FastAPI` to `from fastapi import FastAPI, Body`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_api.py -v`
Expected: PASS (todos)

- [ ] **Step 5: Commit**

```bash
git add api/main.py api/services.py tests/test_api.py
git commit -m "feat: GET /api/metrics + POST /api/checkin endpoints"
```

---

### Task 12: Séries/reps de musculação em atividades

**Files:**
- Modify: `src/history_db.py`, `src/extractors.py`, `src/ingestor.py`
- Test: `tests/test_extractors.py` (append), `tests/test_history_db.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_extractors.py`:

```python
from src.extractors import sets_from_garmin


def test_sets_from_garmin_extracts_reps_weight():
    raw = {"exerciseSets": [
        {"setType": "ACTIVE", "repetitionCount": 10, "weight": 20000, "duration": 40},
        {"setType": "REST", "repetitionCount": None, "weight": None, "duration": 60},
    ]}
    sets = sets_from_garmin(raw)
    assert len(sets) == 1  # só ACTIVE
    assert sets[0]["reps"] == 10
    assert sets[0]["weight_kg"] == 20.0


def test_sets_from_garmin_empty():
    assert sets_from_garmin({}) == []
    assert sets_from_garmin(None) == []
```

Append to `tests/test_history_db.py`:

```python
def test_activity_stores_sets_json(tmp_path):
    from src.history_db import HistoryDB
    db = HistoryDB(db_path=str(tmp_path / "h.db"))
    db.upsert_activity({"activity_id": 9, "date": "2026-06-13", "name": "Força",
                        "type": "strength_training", "is_strength": 1,
                        "sets_json": '[{"reps":10,"weight_kg":20.0}]'})
    act = db.get_activity(9)
    assert act["sets_json"] == '[{"reps":10,"weight_kg":20.0}]'
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_extractors.py -k sets tests/test_history_db.py -k sets_json -v`
Expected: FAIL — `ImportError: cannot import name 'sets_from_garmin'` / coluna `sets_json` inexistente.

- [ ] **Step 3: Write minimal implementation**

In `src/history_db.py`, add `"sets_json"` to the end of the `ACTIVITY_COLUMNS` list. (The `_upsert` helper and the `act_cols` builder treat any column not in the special-cased names as TEXT/REAL; `sets_json` matches the `splits_json` text-column pattern — add it to the text-column tuple in `_init_db`: change `else f"{c} TEXT" if c in ("date", "name", "type", "splits_json")` to `else f"{c} TEXT" if c in ("date", "name", "type", "splits_json", "sets_json")`.)

In `src/extractors.py`, add:

```python
def sets_from_garmin(raw: dict) -> list:
    sets = (raw or {}).get("exerciseSets", []) or []
    out = []
    for s in sets:
        if s.get("setType") != "ACTIVE":
            continue
        weight = s.get("weight")
        out.append({
            "reps": s.get("repetitionCount"),
            "weight_kg": round(weight / 1000, 1) if weight else None,
            "duration_s": s.get("duration"),
        })
    return out
```

In `src/ingestor.py`, in `_activities_by_day`, after building `row = activity_from_garmin(a)`, enrich strength activities:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_extractors.py tests/test_history_db.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/history_db.py src/extractors.py src/ingestor.py tests/test_extractors.py tests/test_history_db.py
git commit -m "feat: capture strength sets/reps into activity.sets_json"
```

---

## Verificação final

- [ ] `python -m pytest -q` — tudo verde.
- [ ] Conferir que rotas legadas (`/api/today`, `/api/trends`) seguem passando (dual-write).
- [ ] Smoke manual opcional: `python scripts/backfill.py` popula `metric_value` + `daily_snapshot`; `GET /api/metrics` retorna domínios com status.
