# Camada de Carga/Tendência (fundação) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Computar carga de treino (TRIMP) por sessão e derivar ACWR, monotonia e baseline rolante de FC como métricas novas, sem mexer no veredito atual.

**Architecture:** Módulo puro `src/training_load.py` (sem IO, sem rede, sem LLM) com funções determinísticas. O `Ingestor` chama essas funções no fim de cada dia ingerido e grava 3 métricas (`acwr`, `training_monotony`, `resting_hr_baseline`) em `metric_value` via o caminho de escrita existente (dual-write). `read_metrics` pega elas naturalmente pelo catálogo.

**Tech Stack:** Python 3.11+, `math`/`statistics` da stdlib, pytest. SQLite via `HistoryDB`.

## Global Constraints

- **Determinístico**: nenhuma chamada de LLM neste sub-projeto.
- **Forerunner 55**: dados faltam. Toda função degrada com fallback, nunca levanta exceção por dado ausente.
- **Frescor**: carga sem `avg_hr` é marcada `estimado` (flag de retorno), não silenciosamente tratada como real.
- **Musculação fora**: só `type in {"running","trail_running","treadmill_running"}` e `is_strength` falsy entram na carga.
- **Dual-track**: NÃO alterar `HealthMonitor.verdict` nem `context_from_metrics`. Veredito tem que sair idêntico ao de hoje.
- **TRIMP (Banister, homem)**: `HRr = clamp((avg_hr−hr_rest)/(hr_max−hr_rest), 0, 1)`; `trimp = duration_min × HRr × 0.64 × e^(1.92·HRr)`.
- **FCmáx**: maior `max_hr` observado se ≥ Tanaka `round(208−0.7·idade)`; senão Tanaka. idade de `athlete_profile.json`.
- **ACWR (EWMA)**: agudo τ=7d, crônico τ=28d, `α=2/(τ+1)`. Zonas: `<0.8 baixo` · `0.8–1.5 otimo` · `>1.5 risco`.
- **Idioma**: nomes de métricas/labels em pt-BR como no catálogo existente.

---

### Task 1: `session_trimp`

**Files:**
- Create: `src/training_load.py`
- Test: `tests/test_training_load.py`

**Interfaces:**
- Produces: `session_trimp(activity: dict, hr_rest: float, hr_max: float) -> tuple[float, bool]` — retorna `(carga, estimado)`. `activity` tem chaves `duration_min`, `avg_hr`.

- [ ] **Step 1: Write the failing test**

```python
import math
import pytest
from src.training_load import session_trimp


def test_trimp_com_fc_conhecida():
    act = {"duration_min": 30, "avg_hr": 150}
    carga, estimado = session_trimp(act, hr_rest=50, hr_max=190)
    assert carga == pytest.approx(54.05, abs=0.5)
    assert estimado is False


def test_trimp_clampa_hrr_acima_de_um():
    # avg_hr acima de hr_max não deve estourar (HRr clampa em 1.0)
    act = {"duration_min": 10, "avg_hr": 200}
    carga, estimado = session_trimp(act, hr_rest=50, hr_max=190)
    esperado = 10 * 1.0 * 0.64 * math.exp(1.92 * 1.0)
    assert carga == pytest.approx(esperado, abs=0.1)
    assert estimado is False


def test_trimp_sem_avg_hr_usa_duracao_estimado():
    act = {"duration_min": 40, "avg_hr": None}
    carga, estimado = session_trimp(act, hr_rest=50, hr_max=190)
    assert carga == 40.0
    assert estimado is True


def test_trimp_sem_duracao_zero_estimado():
    act = {"duration_min": None, "avg_hr": 150}
    carga, estimado = session_trimp(act, hr_rest=50, hr_max=190)
    assert carga == 0.0
    assert estimado is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_training_load.py -q`
Expected: FAIL — `ImportError: cannot import name 'session_trimp'`.

- [ ] **Step 3: Write minimal implementation**

```python
import math


def session_trimp(activity: dict, hr_rest: float, hr_max: float) -> tuple[float, bool]:
    """Carga TRIMP (Banister, homem). Retorna (carga, estimado).
    Sem avg_hr ou hr_max<=hr_rest: fallback duração (estimado=True)."""
    duration = activity.get("duration_min")
    if duration is None:
        return 0.0, True
    avg_hr = activity.get("avg_hr")
    if avg_hr is None or hr_max <= hr_rest:
        return float(duration), True
    hrr = (avg_hr - hr_rest) / (hr_max - hr_rest)
    hrr = max(0.0, min(1.0, hrr))
    trimp = duration * hrr * 0.64 * math.exp(1.92 * hrr)
    return trimp, False
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_training_load.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add src/training_load.py tests/test_training_load.py
git commit -m "feat(load): session_trimp (Banister) com fallback duracao"
```

---

### Task 2: `estimate_hr_max`

**Files:**
- Modify: `src/training_load.py`
- Test: `tests/test_training_load.py`

**Interfaces:**
- Produces: `estimate_hr_max(activities: list[dict], idade: int) -> int` — maior `max_hr` observado se ≥ Tanaka, senão Tanaka `round(208−0.7·idade)`.

- [ ] **Step 1: Write the failing test**

```python
from src.training_load import estimate_hr_max


def test_hr_max_usa_observada_quando_maior():
    acts = [{"max_hr": 195}, {"max_hr": 188}, {"max_hr": None}]
    assert estimate_hr_max(acts, idade=25) == 195


def test_hr_max_usa_tanaka_quando_observada_menor():
    acts = [{"max_hr": 150}]
    assert estimate_hr_max(acts, idade=25) == 190  # 208 - 0.7*25 = 190.5 -> 190


def test_hr_max_sem_atividades_usa_tanaka():
    assert estimate_hr_max([], idade=25) == 190
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_training_load.py -k hr_max -q`
Expected: FAIL — `ImportError: cannot import name 'estimate_hr_max'`.

- [ ] **Step 3: Write minimal implementation**

Adicionar em `src/training_load.py`:

```python
def estimate_hr_max(activities: list, idade: int) -> int:
    tanaka = round(208 - 0.7 * idade)
    observados = [a.get("max_hr") for a in activities if a.get("max_hr")]
    if observados:
        return max(max(observados), tanaka)
    return tanaka
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_training_load.py -k hr_max -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add src/training_load.py tests/test_training_load.py
git commit -m "feat(load): estimate_hr_max (observada com fallback Tanaka)"
```

---

### Task 3: `daily_load_series`

**Files:**
- Modify: `src/training_load.py`
- Test: `tests/test_training_load.py`

**Interfaces:**
- Consumes: `session_trimp`.
- Produces: `daily_load_series(activities: list[dict], hr_rest_by_date: dict, hr_max: float, default_rest: float = 60.0) -> dict[str, float]` — soma TRIMP das corridas por `date` (ISO). Ignora `is_strength` e tipos fora de `RUN_TYPES`. `hr_rest` da data vem de `hr_rest_by_date`, senão `default_rest`.

- [ ] **Step 1: Write the failing test**

```python
from src.training_load import daily_load_series, RUN_TYPES


def test_daily_load_agrupa_e_ignora_musculacao():
    acts = [
        {"date": "2026-06-20", "type": "running", "is_strength": 0,
         "duration_min": 30, "avg_hr": 150, "max_hr": 170},
        {"date": "2026-06-20", "type": "indoor_cardio", "is_strength": 1,
         "duration_min": 45, "avg_hr": 120, "max_hr": 140},
        {"date": "2026-06-19", "type": "treadmill_running", "is_strength": 0,
         "duration_min": 20, "avg_hr": None, "max_hr": None},
    ]
    series = daily_load_series(acts, {"2026-06-20": 50}, hr_max=190)
    assert set(series.keys()) == {"2026-06-20", "2026-06-19"}
    assert series["2026-06-20"] > 0          # só a corrida contou
    assert series["2026-06-19"] == 20.0      # fallback duração (sem FC)


def test_run_types_exclui_cardio():
    assert "running" in RUN_TYPES
    assert "indoor_cardio" not in RUN_TYPES
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_training_load.py -k daily_load -q`
Expected: FAIL — `ImportError`.

- [ ] **Step 3: Write minimal implementation**

Adicionar em `src/training_load.py`:

```python
RUN_TYPES = {"running", "trail_running", "treadmill_running"}


def daily_load_series(activities: list, hr_rest_by_date: dict,
                      hr_max: float, default_rest: float = 60.0) -> dict:
    series: dict = {}
    for a in activities:
        if a.get("is_strength") or a.get("type") not in RUN_TYPES:
            continue
        d = a.get("date")
        if not d:
            continue
        hr_rest = hr_rest_by_date.get(d, default_rest)
        carga, _ = session_trimp(a, hr_rest, hr_max)
        series[d] = series.get(d, 0.0) + carga
    return series
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_training_load.py -k daily_load -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add src/training_load.py tests/test_training_load.py
git commit -m "feat(load): daily_load_series (soma TRIMP por dia, exclui musculacao)"
```

---

### Task 4: `ewma`

**Files:**
- Modify: `src/training_load.py`
- Test: `tests/test_training_load.py`

**Interfaces:**
- Produces: `ewma(series_by_date: dict, end_date: str, tau_days: int, span_days: int) -> float` — média exponencial da carga diária terminando em `end_date` (ISO), preenchendo dias faltantes com 0, iterando do mais antigo ao mais novo. `α = 2/(tau_days+1)`.

- [ ] **Step 1: Write the failing test**

```python
from src.training_load import ewma


def test_ewma_serie_constante_retorna_constante():
    series = {"2026-06-18": 5.0, "2026-06-19": 5.0, "2026-06-20": 5.0}
    assert ewma(series, "2026-06-20", tau_days=1, span_days=3) == pytest.approx(5.0)


def test_ewma_preenche_faltantes_com_zero():
    # span 3 dias terminando em 06-20; só 06-20 tem 10; α=2/(1+1)=1.0
    # loads (antigo->novo) = [0, 0, 10]; α=1 => ewma = último = 10
    series = {"2026-06-20": 10.0}
    assert ewma(series, "2026-06-20", tau_days=1, span_days=3) == pytest.approx(10.0)


def test_ewma_alpha_meio():
    # α=2/(3+1)=0.5; loads=[0,0,10] -> 0; 0; 0.5*10+0.5*0=5.0
    series = {"2026-06-20": 10.0}
    assert ewma(series, "2026-06-20", tau_days=3, span_days=3) == pytest.approx(5.0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_training_load.py -k ewma -q`
Expected: FAIL — `ImportError`.

- [ ] **Step 3: Write minimal implementation**

Adicionar em `src/training_load.py` (topo já tem `import math`; adicionar `import datetime as _dt`):

```python
import datetime as _dt


def ewma(series_by_date: dict, end_date: str, tau_days: int, span_days: int) -> float:
    end = _dt.date.fromisoformat(end_date)
    alpha = 2.0 / (tau_days + 1)
    loads = []
    for i in range(span_days - 1, -1, -1):  # antigo -> novo
        d = (end - _dt.timedelta(days=i)).isoformat()
        loads.append(series_by_date.get(d, 0.0))
    val = loads[0]
    for x in loads[1:]:
        val = alpha * x + (1 - alpha) * val
    return val
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_training_load.py -k ewma -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add src/training_load.py tests/test_training_load.py
git commit -m "feat(load): ewma deterministica com preenchimento de zeros"
```

---

### Task 5: `acwr` + `acwr_zone`

**Files:**
- Modify: `src/training_load.py`
- Test: `tests/test_training_load.py`

**Interfaces:**
- Consumes: `ewma`.
- Produces:
  - `acwr_zone(ratio: float | None) -> str` — `"ausente"` se None; `"baixo"` `<0.8`; `"otimo"` `0.8..1.5`; `"risco"` `>1.5`.
  - `acwr(series_by_date: dict, end_date: str) -> tuple[float | None, str]` — `(razão, zona)`. Crônico 0 → `(None, "ausente")`.

- [ ] **Step 1: Write the failing test**

```python
from src.training_load import acwr, acwr_zone


def test_acwr_zonas_nos_limiares():
    assert acwr_zone(None) == "ausente"
    assert acwr_zone(0.79) == "baixo"
    assert acwr_zone(0.8) == "otimo"
    assert acwr_zone(1.5) == "otimo"
    assert acwr_zone(1.51) == "risco"


def test_acwr_serie_constante_da_um():
    # carga igual todo dia -> agudo == cronico -> razão 1.0
    series = {(_dt_date(2026, 6, 20) - _td(days=i)).isoformat(): 10.0 for i in range(28)}
    ratio, zona = acwr("placeholder", "2026-06-20") if False else acwr(series, "2026-06-20")
    assert ratio == pytest.approx(1.0, abs=0.01)
    assert zona == "otimo"


def test_acwr_sem_cronico_ausente():
    ratio, zona = acwr({}, "2026-06-20")
    assert ratio is None
    assert zona == "ausente"
```

Adicionar no topo do arquivo de teste (se ainda não houver):

```python
from datetime import date as _dt_date, timedelta as _td
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_training_load.py -k acwr -q`
Expected: FAIL — `ImportError`.

- [ ] **Step 3: Write minimal implementation**

Adicionar em `src/training_load.py`:

```python
def acwr_zone(ratio) -> str:
    if ratio is None:
        return "ausente"
    if ratio < 0.8:
        return "baixo"
    if ratio <= 1.5:
        return "otimo"
    return "risco"


def acwr(series_by_date: dict, end_date: str) -> tuple:
    agudo = ewma(series_by_date, end_date, tau_days=7, span_days=7)
    cronico = ewma(series_by_date, end_date, tau_days=28, span_days=28)
    if cronico == 0:
        return None, "ausente"
    ratio = agudo / cronico
    return ratio, acwr_zone(ratio)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_training_load.py -k acwr -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add src/training_load.py tests/test_training_load.py
git commit -m "feat(load): acwr (EWMA agudo/cronico) + zonas"
```

---

### Task 6: `monotony`

**Files:**
- Modify: `src/training_load.py`
- Test: `tests/test_training_load.py`

**Interfaces:**
- Produces: `monotony(series_by_date: dict, end_date: str) -> float | None` — Foster: `média(carga 7d) / pstdev(7d)`. Desvio 0 → `None`.

- [ ] **Step 1: Write the failing test**

```python
from src.training_load import monotony


def test_monotony_carga_constante_none():
    series = {(_dt_date(2026, 6, 20) - _td(days=i)).isoformat(): 10.0 for i in range(7)}
    assert monotony(series, "2026-06-20") is None


def test_monotony_serie_alternada():
    # loads dos 7 dias = [10,0,10,0,10,0,10] (06-20 mais novo); mean=50/7, pstdev~5.1507
    series = {}
    for i in range(7):
        d = (_dt_date(2026, 6, 20) - _td(days=i)).isoformat()
        series[d] = 10.0 if i % 2 == 0 else 0.0
    assert monotony(series, "2026-06-20") == pytest.approx(1.39, abs=0.03)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_training_load.py -k monotony -q`
Expected: FAIL — `ImportError`.

- [ ] **Step 3: Write minimal implementation**

Adicionar em `src/training_load.py` (adicionar `import statistics` no topo):

```python
import statistics


def monotony(series_by_date: dict, end_date: str) -> float | None:
    end = _dt.date.fromisoformat(end_date)
    loads = [series_by_date.get((end - _dt.timedelta(days=i)).isoformat(), 0.0)
             for i in range(7)]
    desvio = statistics.pstdev(loads)
    if desvio == 0:
        return None
    return statistics.mean(loads) / desvio
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_training_load.py -k monotony -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add src/training_load.py tests/test_training_load.py
git commit -m "feat(load): monotony (Foster) sobre janela 7d"
```

---

### Task 7: `resting_hr_baseline`

**Files:**
- Modify: `src/training_load.py`
- Test: `tests/test_training_load.py`

**Interfaces:**
- Produces: `resting_hr_baseline(hr_series: list[dict], end_date: str) -> tuple[float | None, float | None]` — `(baseline, desvio_do_dia)`. `hr_series` são rows `{"date","value"}` (de `get_metric_series`). Baseline = média dos últimos 30d com `value` não-None. `desvio_do_dia = value_de_end_date − baseline` (None se não houver valor em `end_date`). Sem dados → `(None, None)`.

- [ ] **Step 1: Write the failing test**

```python
from src.training_load import resting_hr_baseline


def test_baseline_media_e_desvio():
    series = [
        {"date": "2026-06-18", "value": 50},
        {"date": "2026-06-19", "value": 52},
        {"date": "2026-06-20", "value": 60},
    ]
    base, desvio = resting_hr_baseline(series, "2026-06-20")
    assert base == pytest.approx(54.0)          # (50+52+60)/3
    assert desvio == pytest.approx(6.0)         # 60 - 54


def test_baseline_sem_dados_none():
    base, desvio = resting_hr_baseline([], "2026-06-20")
    assert base is None and desvio is None


def test_baseline_sem_valor_no_dia_desvio_none():
    series = [{"date": "2026-06-18", "value": 50}, {"date": "2026-06-19", "value": 52}]
    base, desvio = resting_hr_baseline(series, "2026-06-20")
    assert base == pytest.approx(51.0)
    assert desvio is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_training_load.py -k baseline -q`
Expected: FAIL — `ImportError`.

- [ ] **Step 3: Write minimal implementation**

Adicionar em `src/training_load.py`:

```python
def resting_hr_baseline(hr_series: list, end_date: str) -> tuple:
    end = _dt.date.fromisoformat(end_date)
    start = (end - _dt.timedelta(days=29)).isoformat()
    vals = [r["value"] for r in hr_series
            if r.get("value") is not None and start <= r["date"] <= end_date]
    if not vals:
        return None, None
    base = statistics.mean(vals)
    hoje = next((r["value"] for r in hr_series
                 if r["date"] == end_date and r.get("value") is not None), None)
    desvio = (hoje - base) if hoje is not None else None
    return base, desvio
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_training_load.py -k baseline -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add src/training_load.py tests/test_training_load.py
git commit -m "feat(load): resting_hr_baseline (media 30d + desvio do dia)"
```

---

### Task 8: Catálogo — 3 métricas novas

**Files:**
- Modify: `src/metric_catalog.py:53` (depois dos check-ins, antes do fechamento da lista)
- Test: `tests/test_metric_catalog.py`

**Interfaces:**
- Produces: keys `acwr`, `training_monotony`, `resting_hr_baseline` em `CATALOG`/`CATALOG_BY_KEY`, `source_default="computed"`.

- [ ] **Step 1: Write the failing test**

```python
from src.metric_catalog import CATALOG_BY_KEY
from src.metric_status import compute_status
import datetime


def test_metricas_de_carga_no_catalogo():
    for key in ("acwr", "training_monotony", "resting_hr_baseline"):
        assert key in CATALOG_BY_KEY
        assert CATALOG_BY_KEY[key].source_default == "computed"


def test_computed_fresco_no_dia():
    spec = CATALOG_BY_KEY["acwr"]
    status = compute_status(spec.cadencia, "computed",
                            "2026-06-20T10:00:00", datetime.date(2026, 6, 20))
    assert status == "fresco"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_metric_catalog.py -k carga -q`
Expected: FAIL — `KeyError: 'acwr'`.

- [ ] **Step 3: Write minimal implementation**

Em `src/metric_catalog.py`, adicionar dentro da lista `CATALOG`, logo após a linha do `alimentacao` (linha 53):

```python
    # Carga / tendência (computadas — sub-projeto 1)
    MetricSpec("acwr", "Carga aguda:crônica", "", "prontidao", "diaria", "computed"),
    MetricSpec("training_monotony", "Monotonia", "", "prontidao", "diaria", "computed"),
    MetricSpec("resting_hr_baseline", "FC repouso (base 30d)", " bpm", "recuperacao", "diaria", "computed"),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_metric_catalog.py -q`
Expected: PASS (inclui os pré-existentes do arquivo).

- [ ] **Step 5: Commit**

```bash
git add src/metric_catalog.py tests/test_metric_catalog.py
git commit -m "feat(catalog): metricas computed acwr/monotony/baseline"
```

---

### Task 9: Ingestor dual-write + integração

**Files:**
- Modify: `src/ingestor.py` (adicionar `_write_load_metrics`, chamar no fim de `_write_day`)
- Test: `tests/test_ingestor_load.py` (criar)

**Interfaces:**
- Consumes: `estimate_hr_max`, `daily_load_series`, `acwr`, `monotony`, `resting_hr_baseline` de `src/training_load.py`; `db.get_activities(start,end)`, `db.get_metric_series("resting_hr",start,end)`, `db.upsert_metric(...)`.
- Produces: grava `acwr`/`training_monotony`/`resting_hr_baseline` em `metric_value` com `source="computed"`; não grava quando dado insuficiente.

- [ ] **Step 1: Write the failing test**

```python
import datetime as dt
from src.history_db import HistoryDB
from src.ingestor import Ingestor


def _seed_runs(db, end="2026-06-20", n=28, trimp_hr=150):
    end_d = dt.date.fromisoformat(end)
    for i in range(n):
        d = (end_d - dt.timedelta(days=i)).isoformat()
        db.upsert_activity({
            "activity_id": 1000 + i, "date": d, "name": "run", "type": "running",
            "is_strength": 0, "distance_m": 5000, "duration_min": 30,
            "pace_min_km": 6.0, "avg_hr": trimp_hr, "max_hr": 175,
            "calories": 300, "cadence": 160, "stride_length": 1.0,
        })
        db.upsert_metric(d, "resting_hr", 50, d + "T08:00:00", "garmin")


def test_write_load_metrics_grava_computed(tmp_path):
    db = HistoryDB(str(tmp_path / "h.db"))
    _seed_runs(db)
    ing = Ingestor(client=None, db=db)
    ing._write_load_metrics("2026-06-20")
    metrics = {m["metric_key"]: m for m in db.get_metrics("2026-06-20")}
    assert "acwr" in metrics and metrics["acwr"]["source"] == "computed"
    assert "training_monotony" in metrics
    assert "resting_hr_baseline" in metrics
    assert metrics["resting_hr_baseline"]["value"] == 50.0


def test_write_load_metrics_sem_corridas_nao_grava(tmp_path):
    db = HistoryDB(str(tmp_path / "h2.db"))
    ing = Ingestor(client=None, db=db)
    ing._write_load_metrics("2026-06-20")
    keys = {m["metric_key"] for m in db.get_metrics("2026-06-20")}
    assert "acwr" not in keys          # sem crônico -> não grava
    assert "training_monotony" not in keys
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_ingestor_load.py -q`
Expected: FAIL — `AttributeError: 'Ingestor' object has no attribute '_write_load_metrics'`.

- [ ] **Step 3: Write minimal implementation**

Em `src/ingestor.py`, adicionar imports no topo:

```python
import json
import os
from src.training_load import (
    estimate_hr_max, daily_load_series, acwr, monotony, resting_hr_baseline,
)
```

Adicionar método na classe `Ingestor`:

```python
    @staticmethod
    def _idade(default: int = 30) -> int:
        path = os.getenv("ATHLETE_PROFILE") or "athlete_profile.json"
        try:
            with open(path, encoding="utf-8") as f:
                return int(json.load(f).get("idade") or default)
        except Exception:  # noqa: BLE001 — perfil ausente: usa default p/ não quebrar ingestão
            return default

    def _write_load_metrics(self, day: str) -> None:
        start28 = (_dt.date.fromisoformat(day) - _dt.timedelta(days=27)).isoformat()
        start30 = (_dt.date.fromisoformat(day) - _dt.timedelta(days=29)).isoformat()
        acts = self._db.get_activities(start28, day)
        hr_rows = self._db.get_metric_series("resting_hr", start30, day)
        hr_rest_by_date = {r["date"]: r["value"] for r in hr_rows if r["value"] is not None}
        rests = list(hr_rest_by_date.values())
        default_rest = sum(rests) / len(rests) if rests else 60.0
        hr_max = estimate_hr_max(acts, self._idade())
        series = daily_load_series(acts, hr_rest_by_date, hr_max, default_rest)

        now = _dt.datetime.now().isoformat(timespec="seconds")
        ratio, _zone = acwr(series, day)
        if ratio is not None:
            self._db.upsert_metric(day, "acwr", round(ratio, 2), now, "computed")
        mono = monotony(series, day)
        if mono is not None:
            self._db.upsert_metric(day, "training_monotony", round(mono, 2), now, "computed")
        base, _desvio = resting_hr_baseline(hr_rows, day)
        if base is not None:
            self._db.upsert_metric(day, "resting_hr_baseline", round(base, 1), now, "computed")
```

Chamar no fim de `_write_day` (após `self._write_metrics(day, summary, race)` na linha 63):

```python
        # camada de carga/tendência (computada do que já está no DB)
        self._write_load_metrics(day)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_ingestor_load.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add src/ingestor.py tests/test_ingestor_load.py
git commit -m "feat(ingestor): dual-write das metricas de carga (computed)"
```

---

### Task 10: Regressão — veredito inalterado + suite verde

**Files:**
- Test: `tests/test_training_load_regression.py` (criar)

**Interfaces:**
- Consumes: `context_from_metrics` de `src/metric_reader.py`, `read_metrics`.

- [ ] **Step 1: Write the failing test**

```python
import datetime
from src.history_db import HistoryDB
from src.metric_reader import context_from_metrics, read_metrics


def test_context_ignora_metricas_de_carga(tmp_path):
    """Dual-track: as métricas computed NÃO entram no context do veredito."""
    db = HistoryDB(str(tmp_path / "r.db"))
    db.upsert_metric("2026-06-20", "acwr", 1.8, "2026-06-20T10:00:00", "computed")
    db.upsert_metric("2026-06-20", "resting_hr", 55, "2026-06-20T08:00:00", "garmin")
    ctx = context_from_metrics(db, "2026-06-20", today=datetime.date(2026, 6, 20))
    # chaves do context são exatamente as de hoje (sem acwr/monotony/baseline)
    assert set(ctx.keys()) == {
        "resting_hr_today", "resting_hr_avg_7d", "sleep_debt_hours",
        "morning_battery_avg", "run_sessions_7d",
    }


def test_read_metrics_expoe_acwr(tmp_path):
    db = HistoryDB(str(tmp_path / "r2.db"))
    db.upsert_metric("2026-06-20", "acwr", 1.2, "2026-06-20T10:00:00", "computed")
    out = read_metrics(db, "2026-06-20", today=datetime.date(2026, 6, 20))
    cells = {c["key"]: c for c in out["dominios"]["prontidao"]}
    assert cells["acwr"]["value"] == 1.2
    assert cells["acwr"]["status"] == "fresco"
```

- [ ] **Step 2: Run test to verify it fails or passes**

Run: `python -m pytest tests/test_training_load_regression.py -q`
Expected: PASS direto (nenhuma mudança em `context_from_metrics`/`read_metrics` foi feita — este teste trava o comportamento). Se `test_context_ignora...` falhar, alguém alterou o context indevidamente: reverter.

- [ ] **Step 3: Rodar a suite inteira**

Run: `python -m pytest -q`
Expected: tudo verde (214 pré-existentes + novos).

- [ ] **Step 4: Commit**

```bash
git add tests/test_training_load_regression.py
git commit -m "test(load): regressao dual-track (context inalterado, read expoe acwr)"
```

---

## Self-Review

**1. Spec coverage:**
- `session_trimp` (TRIMP Banister + fallback) → Task 1 ✅
- `estimate_hr_max` (observada+Tanaka) → Task 2 ✅
- `daily_load_series` (soma por dia, exclui musculação) → Task 3 ✅
- `ewma` → Task 4 ✅
- `acwr` + zonas → Task 5 ✅
- `monotony` (Foster) → Task 6 ✅
- `resting_hr_baseline` (30d) → Task 7 ✅
- 3 métricas no catálogo + `compute_status` trata `computed` → Task 8 ✅
- Ingestor dual-write, não grava sem dado → Task 9 ✅
- read_metrics expõe; veredito inalterado → Task 10 ✅
- Verificação end-to-end (`/metrics`, `/semana`, veredito idêntico) → coberto por Task 10 (regressão) + checagem manual pós-merge.

**2. Placeholder scan:** sem TBD/TODO; todo step tem código real.

**3. Type consistency:** `session_trimp` retorna `(float,bool)` usado por `daily_load_series`; `ewma` consumido por `acwr` com mesmos params; `acwr_zone` reusada por `acwr`; `_write_load_metrics` usa as assinaturas exatas das Tasks 1–7; `hr_series` (rows `date`/`value`) consistente entre `resting_hr_baseline` e o ingestor. OK.
