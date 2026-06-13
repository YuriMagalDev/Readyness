# Camada de Análise Rastreável — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produzir a análise diária com veredito determinístico (regra) + insights cujas conclusões são rastreáveis até as métricas que as geraram (LLM cita keys, nós validamos).

**Architecture:** Extrai a leitura de métricas (catálogo × valores + status) de `api/services.build_metrics` para `src/metric_reader.py` (reutilizável). `DailyAnalysis` combina o veredito determinístico (`HealthMonitor.verdict` via `context_from_metrics`) com insights gerados pelo LLM (Haiku) cujas `keys` citadas são validadas contra as métricas alimentadas. Novo endpoint `/api/analysis`.

**Tech Stack:** Python 3.11, sqlite3, FastAPI, anthropic (Haiku), pytest.

---

### Task 1: Extrair `read_metrics` para `src/metric_reader.py`

Refatoração: mover a lógica de `build_metrics` para um módulo em `src/` (sem ciclo de import), `build_metrics` passa a delegar. Comportamento idêntico.

**Files:**
- Create: `src/metric_reader.py`
- Modify: `api/services.py`
- Test: `tests/test_metric_reader.py` (new), `tests/test_api.py` (ajustar se necessário)

- [ ] **Step 1: Write the failing test**

Create `tests/test_metric_reader.py`:

```python
import datetime
from unittest.mock import MagicMock
from src.metric_reader import read_metrics


def test_read_metrics_groups_and_status():
    db = MagicMock()
    db.get_metrics.return_value = [
        {"date": "2026-06-13", "metric_key": "resting_hr", "value": 52,
         "measured_at": "2026-06-13T00:00", "source": "garmin"},
        {"date": "2026-06-13", "metric_key": "race_pred_5k", "value": 1758,
         "measured_at": "2026-06-13T00:00", "source": "estimado"},
    ]
    db.get_metric_series.return_value = [
        {"date": "2026-06-10", "metric_key": "weight_kg", "value": 80.0,
         "measured_at": "2026-06-10T07:00", "source": "garmin"}]
    payload = read_metrics(db, "2026-06-13", today=datetime.date(2026, 6, 13))

    dominios = payload["dominios"]
    rec = {m["key"]: m for m in dominios["recuperacao"]}
    assert rec["resting_hr"]["status"] == "fresco"
    assert rec["hrv_overnight"]["status"] == "ausente"
    pront = {m["key"]: m for m in dominios["prontidao"]}
    assert pront["race_pred_5k"]["status"] == "estimado"
    corpo = {m["key"]: m for m in dominios["corpo"]}
    assert corpo["weight_kg"]["value"] == 80.0
    assert corpo["weight_kg"]["status"] == "fresco"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_metric_reader.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.metric_reader'`

- [ ] **Step 3: Write minimal implementation**

Create `src/metric_reader.py` (move the logic currently in `api/services.build_metrics` + `_latest_on_or_before`):

```python
import datetime as _dt
from src.metric_catalog import CATALOG, DOMAIN_ORDER
from src.metric_status import compute_status


def read_metrics(db, date: str, today: _dt.date = None) -> dict:
    today = today or _dt.date.today()
    rows_today = {r["metric_key"]: r for r in db.get_metrics(date)}

    dominios = {d: [] for d in DOMAIN_ORDER}
    for spec in CATALOG:
        row = rows_today.get(spec.key)
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

In `api/services.py`, replace the body of `build_metrics` and remove the now-moved `_latest_on_or_before`. Keep the import of `compute_status`/`CATALOG`/`DOMAIN_ORDER` only if still used elsewhere; otherwise replace with:

```python
from src.metric_reader import read_metrics


def build_metrics(db, date: str, today: _dt.date = None) -> dict:
    return read_metrics(db, date, today=today)
```

Leave the existing `test_build_metrics_groups_and_status` in `tests/test_api.py` as-is — it must still pass (build_metrics now delegates).

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_metric_reader.py tests/test_api.py -k "metrics" -v`
Expected: PASS (new reader test + existing build_metrics test green)

- [ ] **Step 5: Commit**

```bash
git add src/metric_reader.py api/services.py tests/test_metric_reader.py
git commit -m "refactor: extract read_metrics into src/metric_reader; build_metrics delegates"
```

---

### Task 2: `context_from_metrics` em `metric_reader`

Monta o dict que `HealthMonitor` consome, a partir do `metric_value`.

**Files:**
- Modify: `src/metric_reader.py`
- Test: `tests/test_metric_reader.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_metric_reader.py`:

```python
from src.metric_reader import context_from_metrics


def test_context_from_metrics_computes_hr_avg_and_debt():
    db = MagicMock()

    def series(metric_key, start, end):
        if metric_key == "resting_hr":
            return [{"value": 50, "measured_at": f"2026-06-{6+i:02d}T00:00", "date": f"2026-06-{6+i:02d}"}
                    for i in range(7)]  # todos 50
        if metric_key == "sleep_hours":
            return [{"value": 6.0, "measured_at": f"2026-06-{6+i:02d}T00:00", "date": f"2026-06-{6+i:02d}"}
                    for i in range(7)]  # 1h de déficit/dia * 7 = 7h
        if metric_key == "body_battery_high":
            return [{"value": 80, "measured_at": "2026-06-13T00:00", "date": "2026-06-13"}]
        return []

    db.get_metric_series.side_effect = series
    db.get_activities.return_value = [
        {"date": "2026-06-12", "type": "running", "is_strength": 0},
        {"date": "2026-06-11", "type": "strength_training", "is_strength": 1},
    ]
    ctx = context_from_metrics(db, "2026-06-13", today=datetime.date(2026, 6, 13))
    assert ctx["resting_hr_today"] == 50
    assert ctx["resting_hr_avg_7d"] == 50.0
    assert ctx["sleep_debt_hours"] == 7.0
    assert ctx["morning_battery_avg"] == 80
    assert ctx["run_sessions_7d"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_metric_reader.py -k context_from_metrics -v`
Expected: FAIL — `ImportError: cannot import name 'context_from_metrics'`

- [ ] **Step 3: Write minimal implementation**

Append to `src/metric_reader.py`:

```python
SLEEP_TARGET_HOURS = 7.0
RUN_TYPES = {"running", "trail_running", "treadmill_running"}


def context_from_metrics(db, date: str, today: _dt.date = None) -> dict:
    today = today or _dt.date.today()
    week_start = (_dt.date.fromisoformat(date) - _dt.timedelta(days=6)).isoformat()

    hr_series = db.get_metric_series("resting_hr", week_start, date)
    hr_vals = [r["value"] for r in hr_series if r["value"] is not None]
    hr_avg = round(sum(hr_vals) / len(hr_vals), 1) if hr_vals else 0.0
    hr_today = hr_vals[-1] if hr_vals else hr_avg

    sleep_series = db.get_metric_series("sleep_hours", week_start, date)
    debt = sum(max(SLEEP_TARGET_HOURS - r["value"], 0)
               for r in sleep_series if r["value"] is not None)

    bat_series = db.get_metric_series("body_battery_high", week_start, date)
    bat_vals = [r["value"] for r in bat_series if r["value"] is not None]
    battery = bat_vals[-1] if bat_vals else 100

    acts = db.get_activities(week_start, date)
    runs = sum(1 for a in acts if not a.get("is_strength") and a.get("type") in RUN_TYPES)

    return {
        "resting_hr_today": hr_today,
        "resting_hr_avg_7d": hr_avg,
        "sleep_debt_hours": round(debt, 1),
        "morning_battery_avg": battery,
        "run_sessions_7d": runs,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_metric_reader.py -k context_from_metrics -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/metric_reader.py tests/test_metric_reader.py
git commit -m "feat: context_from_metrics — health_monitor context from metric_value"
```

---

### Task 3: `HealthMonitor.verdict` (veredito determinístico)

`check()` consulta o LLM; a análise precisa do veredito puramente determinístico. Expor as regras como método público.

**Files:**
- Modify: `src/health_monitor.py`
- Test: `tests/test_health_monitor.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_health_monitor.py`:

```python
def test_verdict_is_deterministic_no_llm():
    from src.health_monitor import HealthMonitor
    ctx = {"resting_hr_today": 60, "resting_hr_avg_7d": 50,
           "morning_battery_avg": 80, "sleep_debt_hours": 0}
    out = HealthMonitor().verdict(ctx)  # FC +10 → vermelho, sem chamar LLM
    assert out["status"] == "vermelho"
    assert "FC repouso" in out["motivo"]


def test_verdict_green_when_normal():
    from src.health_monitor import HealthMonitor
    ctx = {"resting_hr_today": 50, "resting_hr_avg_7d": 50,
           "morning_battery_avg": 80, "sleep_debt_hours": 0}
    assert HealthMonitor().verdict(ctx)["status"] == "verde"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_health_monitor.py -k verdict -v`
Expected: FAIL — `AttributeError: 'HealthMonitor' object has no attribute 'verdict'`

- [ ] **Step 3: Write minimal implementation**

In `src/health_monitor.py`, add a public method to `HealthMonitor` (delegates to existing `_evaluate_rules`, no LLM):

```python
    def verdict(self, context: dict) -> dict:
        """Veredito determinístico (só regras, sem LLM)."""
        return self._evaluate_rules(context)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_health_monitor.py -v`
Expected: PASS (novos + existentes)

- [ ] **Step 5: Commit**

```bash
git add src/health_monitor.py tests/test_health_monitor.py
git commit -m "feat: HealthMonitor.verdict — deterministic rule-only verdict"
```

---

### Task 4: `DailyAnalysis._insights` — LLM + validação

**Files:**
- Create: `src/daily_analysis.py`
- Test: `tests/test_daily_analysis.py` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/test_daily_analysis.py`:

```python
import json
from unittest.mock import MagicMock, patch
from src.daily_analysis import DailyAnalysis

METRICS = {
    "date": "2026-06-13",
    "dominios": {
        "recuperacao": [
            {"key": "resting_hr", "label": "FC repouso", "value": 58, "unidade": " bpm",
             "measured_at": "2026-06-13T00:00", "status": "fresco", "source": "garmin"},
            {"key": "hrv_overnight", "label": "HRV noturno", "value": None, "unidade": " ms",
             "measured_at": None, "status": "ausente", "source": "garmin"},
        ],
        "prontidao": [], "atividade": [], "corpo": [], "checkin": [],
    },
}


@patch("src.daily_analysis.ask_coach", return_value=json.dumps(
    {"insights": [{"texto": "FC subiu.", "metricas_usadas": ["resting_hr"]}]}))
def test_insights_resolves_valid_key(mock_ask):
    eng = DailyAnalysis(db=MagicMock())
    out = eng._insights(METRICS, force=True)
    assert len(out) == 1
    src = out[0]["metricas_usadas"][0]
    assert src["key"] == "resting_hr"
    assert src["valor"] == 58
    assert src["label"] == "FC repouso"
    assert src["status"] == "fresco"


@patch("src.daily_analysis.ask_coach", return_value=json.dumps(
    {"insights": [{"texto": "X.", "metricas_usadas": ["inexistente"]}]}))
def test_insights_drops_insight_with_no_valid_key(mock_ask):
    eng = DailyAnalysis(db=MagicMock())
    out = eng._insights(METRICS, force=True)
    assert out == []


@patch("src.daily_analysis.ask_coach", return_value=json.dumps(
    {"insights": [{"texto": "Y.", "metricas_usadas": ["resting_hr", "inexistente"]}]}))
def test_insights_filters_invalid_keeps_valid(mock_ask):
    eng = DailyAnalysis(db=MagicMock())
    out = eng._insights(METRICS, force=True)
    assert len(out) == 1
    assert [s["key"] for s in out[0]["metricas_usadas"]] == ["resting_hr"]


@patch("src.daily_analysis.ask_coach", return_value="not json")
def test_insights_empty_on_llm_failure(mock_ask):
    eng = DailyAnalysis(db=MagicMock())
    assert eng._insights(METRICS, force=True) == []


@patch("src.daily_analysis.ask_coach", return_value=json.dumps({"insights": [
    {"texto": "Z.", "metricas_usadas": ["resting_hr"]}]}))
def test_insights_cache_hit_no_second_call(mock_ask):
    db = MagicMock()
    db.get_insight.side_effect = [None, [{"texto": "Z.", "metricas_usadas": [
        {"key": "resting_hr", "label": "FC repouso", "valor": 58, "unidade": " bpm", "status": "fresco"}]}]]
    eng = DailyAnalysis(db=db)
    eng._insights(METRICS)        # miss → chama + grava
    eng._insights(METRICS)        # hit → não chama
    assert mock_ask.call_count == 1
    db.set_insight.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_daily_analysis.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.daily_analysis'`

- [ ] **Step 3: Write minimal implementation**

Create `src/daily_analysis.py`:

```python
import json
from datetime import date
from src.ai_coach import ask_coach
from src.insight_engine import _parse_json


class DailyAnalysis:
    def __init__(self, db=None):
        self.db = db

    def _flatten(self, metrics: dict) -> dict:
        """metric_key -> cell, só métricas com valor (status != ausente)."""
        flat = {}
        for cells in metrics["dominios"].values():
            for c in cells:
                if c["status"] != "ausente":
                    flat[c["key"]] = c
        return flat

    def _insights(self, metrics: dict, force: bool = False) -> list:
        key = f"daily_v2:{metrics['date']}"
        if self.db is not None and not force:
            hit = self.db.get_insight("daily_v2", key)
            if hit is not None:
                return hit

        flat = self._flatten(metrics)
        lista = [{"key": k, "label": c["label"], "valor": c["value"], "status": c["status"]}
                 for k, c in flat.items()]
        prompt = f"""Gere 2-5 observações curtas (1 frase cada) sobre prontidão/recuperação/treino,
com base SOMENTE nas métricas abaixo. Cite só as keys fornecidas.

Métricas: {json.dumps(lista, ensure_ascii=False)}

Retorne EXATAMENTE este JSON:
{{"insights": [{{"texto": "...", "metricas_usadas": ["key1", "key2"]}}]}}"""
        data = _parse_json(ask_coach(prompt, {}, depth="quick"))
        if not data or not isinstance(data.get("insights"), list):
            return []

        result = []
        for ins in data["insights"]:
            texto = (ins or {}).get("texto")
            keys = (ins or {}).get("metricas_usadas") or []
            fontes = []
            for k in keys:
                c = flat.get(k)
                if c is None:
                    continue
                fontes.append({"key": k, "label": c["label"], "valor": c["value"],
                               "unidade": c["unidade"], "status": c["status"]})
            if texto and fontes:  # sem fonte válida → descarta
                result.append({"texto": texto, "metricas_usadas": fontes})

        if self.db is not None and result:
            self.db.set_insight("daily_v2", key, result, date.today().isoformat())
        return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_daily_analysis.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add src/daily_analysis.py tests/test_daily_analysis.py
git commit -m "feat: DailyAnalysis._insights — LLM insights with validated source citations"
```

---

### Task 5: `DailyAnalysis.build` — veredito + insights

**Files:**
- Modify: `src/daily_analysis.py`
- Test: `tests/test_daily_analysis.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_daily_analysis.py`:

```python
import datetime as _dt3


@patch("src.daily_analysis.ask_coach", return_value=json.dumps({"insights": []}))
def test_build_combines_verdict_and_insights(mock_ask):
    db = MagicMock()
    with patch("src.daily_analysis.read_metrics", return_value=METRICS), \
         patch("src.daily_analysis.context_from_metrics", return_value={}), \
         patch("src.daily_analysis.HealthMonitor") as MockMon:
        MockMon.return_value.verdict.return_value = {
            "status": "amarelo", "motivo": "x", "recomendacao": "y"}
        eng = DailyAnalysis(db=db)
        out = eng.build("2026-06-13", today=_dt3.date(2026, 6, 13), force=True)
    assert out["date"] == "2026-06-13"
    assert out["veredito"]["status"] == "amarelo"
    assert out["insights"] == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_daily_analysis.py -k build_combines -v`
Expected: FAIL — `AttributeError: 'DailyAnalysis' object has no attribute 'build'`

- [ ] **Step 3: Write minimal implementation**

In `src/daily_analysis.py`, add imports at top:

```python
import datetime as _dt
from src.metric_reader import read_metrics, context_from_metrics
from src.health_monitor import HealthMonitor
```

Add the method to `DailyAnalysis`:

```python
    def build(self, date_str: str, today: _dt.date = None, force: bool = False) -> dict:
        today = today or _dt.date.today()
        metrics = read_metrics(self.db, date_str, today=today)
        context = context_from_metrics(self.db, date_str, today=today)
        veredito = HealthMonitor().verdict(context)
        insights = self._insights(metrics, force=force)
        return {"date": date_str, "veredito": veredito, "insights": insights}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_daily_analysis.py -v`
Expected: PASS (todos)

- [ ] **Step 5: Commit**

```bash
git add src/daily_analysis.py tests/test_daily_analysis.py
git commit -m "feat: DailyAnalysis.build — deterministic verdict + traceable insights"
```

---

### Task 6: `build_analysis` service + rotas `/api/analysis`

**Files:**
- Modify: `api/services.py`, `api/main.py`
- Test: `tests/test_api.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_api.py`:

```python
def test_build_analysis_delegates():
    db = _MM()
    with patch("api.services.DailyAnalysis") as MockDA:
        MockDA.return_value.build.return_value = {"date": "2026-06-13", "veredito": {}, "insights": []}
        out = services.build_analysis(db, "2026-06-13", force=True)
    assert out["date"] == "2026-06-13"
    assert MockDA.return_value.build.call_args[1]["force"] is True


def test_analysis_route():
    with patch("api.main.get_db"), \
         patch("api.main.services.build_analysis",
               return_value={"date": "2026-06-13", "veredito": {}, "insights": []}):
        from api.main import app
        resp = TestClient(app).get("/api/analysis?date=2026-06-13")
    assert resp.status_code == 200
    assert resp.json()["date"] == "2026-06-13"


def test_analysis_route_post_forces():
    with patch("api.main.get_db"), \
         patch("api.main.services.build_analysis",
               return_value={"date": "2026-06-13", "veredito": {}, "insights": []}) as mock_ba:
        from api.main import app
        resp = TestClient(app).post("/api/analysis", json={"date": "2026-06-13"})
    assert resp.status_code == 200
    assert mock_ba.call_args[1]["force"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_api.py -k "analysis" -v`
Expected: FAIL — `AttributeError: module 'api.services' has no attribute 'build_analysis'` / rota 404.

- [ ] **Step 3: Write minimal implementation**

In `api/services.py`, add import + function:

```python
from src.daily_analysis import DailyAnalysis


def build_analysis(db, date: str, force: bool = False) -> dict:
    return DailyAnalysis(db=db).build(date, force=force)
```

In `api/main.py`, add routes before the StaticFiles mount:

```python
@app.get("/api/analysis")
def analysis(date: str = None):
    import datetime as _d
    d = date or _d.date.today().isoformat()
    return _safe(lambda: services.build_analysis(get_db(), d), code=503)


@app.post("/api/analysis")
def analysis_force(payload: dict = Body(default={})):
    import datetime as _d
    d = payload.get("date") or _d.date.today().isoformat()
    return _safe(lambda: services.build_analysis(get_db(), d, force=True), code=503)
```

(`Body` and `JSONResponse` já estão importados de features anteriores; se `Body` não estiver, troque `from fastapi import FastAPI` por `from fastapi import FastAPI, Body`.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_api.py -k analysis -v` then `python -m pytest -q`
Expected: PASS (todos)

- [ ] **Step 5: Commit**

```bash
git add api/services.py api/main.py tests/test_api.py
git commit -m "feat: build_analysis service + GET/POST /api/analysis"
```

---

## Verificação final

- [ ] `python -m pytest -q` — tudo verde.
- [ ] Conferir rotas legadas intactas (`/api/today`, `/api/metrics`, `/api/trends`).
- [ ] Smoke opcional: `GET /api/analysis` retorna `{date, veredito, insights}` com insights citando métricas reais.
