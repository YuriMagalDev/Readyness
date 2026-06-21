# Proatividade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** O bot manda sozinho um briefing semanal (domingo 19:00) e três alertas (FC subindo, ACWR risco, overreaching) que disparam 1x por episódio.

**Architecture:** Dois detectores puros (`src/alerts.py`) + um builder puro (`src/weekly_briefing.py`) + dois formatadores (`bot/messages.py`) + dois jobs (`bot/jobs.py`) + wiring (`bot/main.py`). Tudo determinístico (sem LLM). Anti-spam por estado em `bot_state`.

**Tech Stack:** Python 3.11+, python-telegram-bot v22 (JobQueue run_daily), pytest (asyncio).

## Global Constraints

- **Determinístico, sem LLM** em alertas e briefing.
- **Bom com metade vazia (FR55)**: sinal ausente (None) → detector retorna None, job não quebra.
- **Anti-spam por episódio**: alerta dispara 1x ao cruzar pra ruim (`state != "1"`), não repete enquanto ruim, reseta (`state="0"`) quando normaliza.
- **Loga falhas** nos jobs (não engolir — lição do job_runs): `_log.warning(...)`.
- **Cache primeiro**: jobs fazem best-effort `sync_today()` em try/except, degradam sobre o DB.
- Briefing: domingo (auto-guard `weekday()==6`, Mon=0), 19:00 SP. Alertas: diário 10:00 SP.
- Alerta FC: 3 dias seguidos FC repouso ≥ baseline+3bpm.
- pt-BR nas mensagens. Reusa `acwr_zone`, `RUN_TYPES`, `estimate_hr_max` de `src/training_load.py`.
- Estado: `db.get_state(k)`/`db.set_state(k, v)` (já existem). Horários tz-aware com `tzinfo=TZ` (PTB roda UTC por padrão).

---

### Task 1: `src/alerts.py` — detectores puros

**Files:**
- Create: `src/alerts.py`
- Test: `tests/test_alerts.py`

**Interfaces:**
- Consumes: `acwr_zone(acwr) -> str` de `src/training_load.py`.
- Produces: `hr_rising(hr_rows, baseline, days=3, margin=3) -> dict|None`; `acwr_risk(acwr) -> dict|None`.

- [ ] **Step 1: Write the failing test**

```python
from src.alerts import hr_rising, acwr_risk


def _rows(*vals):
    return [{"date": f"2026-06-{10+i:02d}", "value": v} for i, v in enumerate(vals)]


def test_hr_rising_dispara_3_dias_acima():
    # baseline 50, margin 3 -> limiar 53; últimos 3 todos >=53
    out = hr_rising(_rows(52, 54, 55, 56), baseline=50)
    assert out is not None and out["kind"] == "hr_rising"
    assert out["valores"] == [54, 55, 56] and out["dias"] == 3


def test_hr_rising_um_dia_abaixo_nao_dispara():
    assert hr_rising(_rows(54, 52, 56), baseline=50) is None   # 52 < 53


def test_hr_rising_sem_baseline_ou_poucos_dias():
    assert hr_rising(_rows(54, 55, 56), baseline=None) is None
    assert hr_rising(_rows(54, 55), baseline=50) is None       # só 2 dias


def test_acwr_risk():
    assert acwr_risk(1.8)["kind"] == "acwr_risk"               # zona risco (>1.5)
    assert acwr_risk(1.8)["acwr"] == 1.8
    assert acwr_risk(1.0) is None                              # ótimo
    assert acwr_risk(0.5) is None                              # baixo
    assert acwr_risk(None) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_alerts.py -q`
Expected: FAIL — `ImportError: cannot import name 'hr_rising'`.

- [ ] **Step 3: Write minimal implementation**

```python
from src.training_load import acwr_zone


def hr_rising(hr_rows, baseline, days: int = 3, margin: int = 3):
    """Alerta se os últimos `days` dias de FC repouso ficaram cada um >= baseline+margin."""
    if baseline is None:
        return None
    vals = [r.get("value") for r in hr_rows if r.get("value") is not None]
    if len(vals) < days:
        return None
    ultimos = vals[-days:]
    if all(v >= baseline + margin for v in ultimos):
        return {"kind": "hr_rising", "dias": days,
                "baseline": round(baseline, 1), "valores": ultimos}
    return None


def acwr_risk(acwr):
    """Alerta quando a carga aguda:crônica entra na zona de risco (>1.5)."""
    if acwr is None:
        return None
    if acwr_zone(acwr) == "risco":
        return {"kind": "acwr_risk", "acwr": round(acwr, 2)}
    return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_alerts.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add src/alerts.py tests/test_alerts.py
git commit -m "feat(alerts): detectores puros hr_rising + acwr_risk"
```

---

### Task 2: `src/weekly_briefing.py` — builder do resumo

**Files:**
- Create: `src/weekly_briefing.py`
- Test: `tests/test_weekly_briefing.py`

**Interfaces:**
- Consumes: `db.get_activities(start,end)`, `db.get_metrics(date)`, `db.get_metric_series(key,start,end)`; `RUN_TYPES`, `estimate_hr_max`, `acwr_zone` de `src/training_load.py`; `Ingestor._idade()` de `src/ingestor.py`.
- Produces: `build_weekly_briefing(db, today) -> dict` com chaves `km_7d`, `sessoes`, `acwr`, `sono_medio`, `fc_max`, `recomendacao`.

- [ ] **Step 1: Write the failing test**

```python
import datetime as dt
from src.history_db import HistoryDB
from src.weekly_briefing import build_weekly_briefing


def test_briefing_agrega_semana(tmp_path):
    db = HistoryDB(str(tmp_path / "b.db"))
    for i, km in enumerate([5, 8]):       # 2 corridas na semana
        d = (dt.date(2026, 6, 20) - dt.timedelta(days=i)).isoformat()
        db.upsert_activity({"activity_id": 10 + i, "date": d, "name": "run",
                            "type": "running", "is_strength": 0,
                            "distance_m": km * 1000, "duration_min": 30,
                            "pace_min_km": 6.0, "avg_hr": 150, "max_hr": 175,
                            "calories": 300, "cadence": 160, "stride_length": 1.0})
        db.upsert_metric(d, "sleep_hours", 7.0, d + "T08:00:00", "garmin")
    db.upsert_metric("2026-06-20", "acwr", 1.8, "2026-06-20T10:00:00", "computed")
    out = build_weekly_briefing(db, dt.date(2026, 6, 20))
    assert out["km_7d"] == 13.0 and out["sessoes"] == 2
    assert out["acwr"] == 1.8
    assert out["sono_medio"] == 7.0
    assert out["recomendacao"].startswith("Semana de deload")   # zona risco


def test_briefing_sem_dados_degrada(tmp_path):
    db = HistoryDB(str(tmp_path / "b2.db"))
    out = build_weekly_briefing(db, dt.date(2026, 6, 20))
    assert out["km_7d"] == 0.0 and out["sessoes"] == 0
    assert out["acwr"] is None and out["sono_medio"] is None
    assert out["recomendacao"] == "Mantenha a carga atual."     # zona None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_weekly_briefing.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.weekly_briefing'`.

- [ ] **Step 3: Write minimal implementation**

```python
import datetime as _dt
from src.training_load import RUN_TYPES, estimate_hr_max, acwr_zone
from src.ingestor import Ingestor

_REC = {
    "risco": "Semana de deload: reduza volume/intensidade.",
    "baixo": "Pode aumentar a carga com cuidado.",
    "otimo": "Mantenha a carga atual.",
}
_REC_DEFAULT = "Mantenha a carga atual."


def build_weekly_briefing(db, today: _dt.date = None) -> dict:
    today = today or _dt.date.today()
    end = today.isoformat()
    start7 = (today - _dt.timedelta(days=6)).isoformat()

    acts = db.get_activities(start7, end)
    runs = [a for a in acts if not a.get("is_strength") and a.get("type") in RUN_TYPES]
    km_7d = round(sum((a.get("distance_m") or 0) for a in runs) / 1000, 1)

    day_metrics = {r["metric_key"]: r["value"] for r in db.get_metrics(end)}
    acwr = day_metrics.get("acwr")

    sleep_rows = db.get_metric_series("sleep_hours", start7, end)
    sleep_vals = [r["value"] for r in sleep_rows if r["value"] is not None]
    sono_medio = round(sum(sleep_vals) / len(sleep_vals), 1) if sleep_vals else None

    start90 = (today - _dt.timedelta(days=89)).isoformat()
    acts90 = db.get_activities(start90, end)
    fc_max = estimate_hr_max(acts90, Ingestor._idade())

    zona = acwr_zone(acwr) if acwr is not None else None
    rec = _REC.get(zona, _REC_DEFAULT)

    return {
        "km_7d": km_7d,
        "sessoes": len(runs),
        "acwr": round(acwr, 2) if acwr is not None else None,
        "sono_medio": sono_medio,
        "fc_max": fc_max,
        "recomendacao": rec,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_weekly_briefing.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add src/weekly_briefing.py tests/test_weekly_briefing.py
git commit -m "feat(briefing): build_weekly_briefing (agrega semana + recomendacao por zona)"
```

---

### Task 3: `bot/messages.py` — `format_alert` + `format_briefing`

**Files:**
- Modify: `bot/messages.py` (adicionar duas funções no fim do arquivo)
- Test: `tests/bot/test_messages.py`

**Interfaces:**
- Consumes: `_e`, `_RULE`, `PARSE_MODE` (já no módulo). detail dicts de `src/alerts.py` + `{"kind":"overreaching","veredito":dict}`. data dict de `build_weekly_briefing`.
- Produces: `format_alert(detail) -> str`; `format_briefing(data) -> str`.

- [ ] **Step 1: Write the failing test**

```python
def test_format_alert_cada_kind():
    from bot import messages
    hr = messages.format_alert({"kind": "hr_rising", "dias": 3, "baseline": 50.0,
                                "valores": [54, 55, 56]})
    assert "FC repouso" in hr
    acwr = messages.format_alert({"kind": "acwr_risk", "acwr": 1.8})
    assert "1.8" in acwr and "risco" in acwr.lower()
    over = messages.format_alert({"kind": "overreaching",
                                  "veredito": {"motivo": "FC alta + carga + dor"}})
    assert "Overreaching" in over
    # kind desconhecido não quebra
    assert isinstance(messages.format_alert({"kind": "zzz"}), str)


def test_format_briefing():
    from bot import messages
    txt = messages.format_briefing({"km_7d": 13.0, "sessoes": 2, "acwr": 1.2,
                                    "sono_medio": 7.0, "fc_max": 190,
                                    "recomendacao": "Mantenha a carga atual."})
    assert "Resumo da semana" in txt and "13.0" in txt
    # campos None viram em-dash, não quebra
    vazio = messages.format_briefing({"km_7d": 0.0, "sessoes": 0, "acwr": None,
                                      "sono_medio": None, "fc_max": 190,
                                      "recomendacao": "Mantenha a carga atual."})
    assert "—" in vazio
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/bot/test_messages.py -k "format_alert or format_briefing" -q`
Expected: FAIL — `AttributeError: module 'bot.messages' has no attribute 'format_alert'`.

- [ ] **Step 3: Write minimal implementation**

Adicionar no fim de `bot/messages.py`:

```python
def _dash(v):
    return _e(v) if v is not None else "—"


def format_alert(detail: dict) -> str:
    kind = (detail or {}).get("kind")
    if kind == "hr_rising":
        vals = " · ".join(str(v) for v in detail.get("valores", []))
        return (f"⚠️ <b>FC repouso subindo</b>\n{_RULE}\n"
                f"{detail.get('dias')} dias acima da base ({_dash(detail.get('baseline'))} bpm): {vals}\n"
                "Possível fadiga/infecção — considere pegar leve.")
    if kind == "acwr_risk":
        return (f"⚠️ <b>Carga em risco</b>\n{_RULE}\n"
                f"ACWR {_dash(detail.get('acwr'))} (zona de risco).\n"
                "Pico de carga, risco de lesão — pisa no freio.")
    if kind == "overreaching":
        motivo = (detail.get("veredito") or {}).get("motivo", "")
        return (f"🛑 <b>Overreaching</b>\n{_RULE}\n{_e(motivo)}\n"
                "Descanso recomendado.")
    return "⚠️ Alerta."


def format_briefing(data: dict) -> str:
    linhas = [
        "📊 <b>Resumo da semana</b>", _RULE,
        f"🏃 Distância  <b>{_dash(data.get('km_7d'))}</b> km · {_dash(data.get('sessoes'))} sessões",
        f"📈 ACWR  <b>{_dash(data.get('acwr'))}</b>",
        f"😴 Sono médio  <b>{_dash(data.get('sono_medio'))}</b> h",
        f"❤️ FCmáx  <b>{_dash(data.get('fc_max'))}</b>",
        _RULE,
        f"→ {_e(data.get('recomendacao', ''))}",
    ]
    return "\n".join(linhas)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/bot/test_messages.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add bot/messages.py tests/bot/test_messages.py
git commit -m "feat(bot): format_alert + format_briefing"
```

---

### Task 4: `job_alerts` (anti-spam por episódio)

**Files:**
- Modify: `bot/jobs.py` (imports + função `job_alerts`)
- Test: `tests/bot/test_jobs.py`

**Interfaces:**
- Consumes: `src.alerts.hr_rising`/`acwr_risk`; `src.metric_reader.context_from_metrics`; `core.daily_analysis`; `db.get_metric_series`, `db.get_state`/`set_state`; `messages.format_alert`.
- Produces: `async def job_alerts(context)`.

- [ ] **Step 1: Write the failing test**

```python
@pytest.mark.asyncio
async def test_job_alerts_anti_spam(tmp_path, monkeypatch):
    db = HistoryDB(db_path=str(tmp_path / "a.db"))
    client = MagicMock()
    monkeypatch.setattr(jobs, "Ingestor", lambda c, d: MagicMock(sync_today=lambda: None))
    # contexto com ACWR em risco; sem FC/baseline (só ACWR dispara)
    monkeypatch.setattr(jobs, "context_from_metrics", lambda db, day: {
        "acwr": 1.8, "resting_hr_baseline": None})
    monkeypatch.setattr(jobs.core, "daily_analysis", lambda db, day, force=False: {
        "veredito": {"overreaching": False}})
    ctx = _job_ctx(db, client)

    await jobs.job_alerts(ctx)
    assert ctx.bot.send_message.await_count == 1      # ACWR cruzou -> 1 alerta
    await jobs.job_alerts(ctx)
    assert ctx.bot.send_message.await_count == 1      # ainda risco -> não repete

    # ACWR normaliza -> reseta episódio
    monkeypatch.setattr(jobs, "context_from_metrics", lambda db, day: {
        "acwr": 1.0, "resting_hr_baseline": None})
    await jobs.job_alerts(ctx)
    assert ctx.bot.send_message.await_count == 1      # sem alerta
    assert db.get_state("alert_acwr") == "0"

    # volta a risco -> dispara de novo
    monkeypatch.setattr(jobs, "context_from_metrics", lambda db, day: {
        "acwr": 1.9, "resting_hr_baseline": None})
    await jobs.job_alerts(ctx)
    assert ctx.bot.send_message.await_count == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/bot/test_jobs.py -k job_alerts -q`
Expected: FAIL — `AttributeError: module 'bot.jobs' has no attribute 'job_alerts'`.

- [ ] **Step 3: Write minimal implementation**

Em `bot/jobs.py`, adicionar imports no topo (junto dos existentes):

```python
from src import alerts
from src.metric_reader import context_from_metrics
```

E a função:

```python
async def job_alerts(context: ContextTypes.DEFAULT_TYPE):
    """Diário: checa FC subindo / ACWR risco / overreaching e alerta 1x por episódio."""
    cfg = context.bot_data["cfg"]
    db = context.bot_data["db"]
    client = context.bot_data["client"]
    day = dt.date.today().isoformat()
    try:
        Ingestor(client, db).sync_today()
    except Exception as e:  # noqa: BLE001
        _log.warning("job_alerts: sync falhou: %s", e)
    try:
        ctx = context_from_metrics(db, day)
        veredito = core.daily_analysis(db, day)["veredito"]
    except Exception as e:  # noqa: BLE001
        _log.warning("job_alerts: contexto falhou: %s", e)
        return

    start7 = (dt.date.today() - dt.timedelta(days=6)).isoformat()
    hr_rows = db.get_metric_series("resting_hr", start7, day)
    over = {"kind": "overreaching", "veredito": veredito} if veredito.get("overreaching") else None
    checks = [
        ("alert_hr", alerts.hr_rising(hr_rows, ctx.get("resting_hr_baseline"))),
        ("alert_acwr", alerts.acwr_risk(ctx.get("acwr"))),
        ("alert_over", over),
    ]
    for key, detail in checks:
        if detail is not None:
            if db.get_state(key) != "1":
                await context.bot.send_message(
                    chat_id=cfg.chat_id, text=messages.format_alert(detail),
                    parse_mode=messages.PARSE_MODE)
                db.set_state(key, "1")
        else:
            db.set_state(key, "0")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/bot/test_jobs.py -k job_alerts -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add bot/jobs.py tests/bot/test_jobs.py
git commit -m "feat(bot): job_alerts (FC/ACWR/overreaching, anti-spam por episodio)"
```

---

### Task 5: `job_briefing` (domingo, auto-guard)

**Files:**
- Modify: `bot/jobs.py` (função `job_briefing`)
- Test: `tests/bot/test_jobs.py`

**Interfaces:**
- Consumes: `src.weekly_briefing.build_weekly_briefing`; `messages.format_briefing`; `db.get_state`/`set_state`.
- Produces: `async def job_briefing(context)`.

- [ ] **Step 1: Write the failing test**

```python
@pytest.mark.asyncio
async def test_job_briefing_so_domingo_e_uma_vez(tmp_path, monkeypatch):
    db = HistoryDB(db_path=str(tmp_path / "br.db"))
    client = MagicMock()
    monkeypatch.setattr(jobs, "Ingestor", lambda c, d: MagicMock(sync_today=lambda: None))
    monkeypatch.setattr(jobs, "build_weekly_briefing", lambda db, today: {
        "km_7d": 13.0, "sessoes": 2, "acwr": 1.2, "sono_medio": 7.0,
        "fc_max": 190, "recomendacao": "Mantenha a carga atual."})
    ctx = _job_ctx(db, client)

    # segunda-feira (weekday 0) -> não manda
    monkeypatch.setattr(jobs.dt, "date", _FakeDate(dt.date(2026, 6, 22)))   # 2026-06-22 = segunda
    await jobs.job_briefing(ctx)
    assert ctx.bot.send_message.await_count == 0

    # domingo (weekday 6) -> manda 1x, não repete
    monkeypatch.setattr(jobs.dt, "date", _FakeDate(dt.date(2026, 6, 21)))   # 2026-06-21 = domingo
    await jobs.job_briefing(ctx)
    assert ctx.bot.send_message.await_count == 1
    await jobs.job_briefing(ctx)
    assert ctx.bot.send_message.await_count == 1
```

Adicionar no topo do arquivo de teste (se ainda não existir) o helper de data fixa — uma
função-fábrica que devolve uma subclasse de `dt.date` cujo `today()` é fixo:

```python
def _FakeDate(fixed):
    class _D(dt.date):
        @classmethod
        def today(cls):
            return fixed
    return _D
```

O teste faz `monkeypatch.setattr(jobs.dt, "date", _FakeDate(dt.date(2026, 6, 21)))` pra fixar o
`today()` que o `job_briefing` enxerga. `2026-06-21` é domingo (weekday 6); `2026-06-22` é segunda
(weekday 0).

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/bot/test_jobs.py -k job_briefing -q`
Expected: FAIL — `AttributeError: module 'bot.jobs' has no attribute 'job_briefing'`.

- [ ] **Step 3: Write minimal implementation**

Em `bot/jobs.py`, adicionar import no topo:

```python
from src.weekly_briefing import build_weekly_briefing
```

E a função:

```python
_BRIEFING_DATE = "briefing_date"


async def job_briefing(context: ContextTypes.DEFAULT_TYPE):
    """Domingo 19:00: resumo da semana. Auto-guard por weekday (6=domingo, Mon=0)."""
    cfg = context.bot_data["cfg"]
    db = context.bot_data["db"]
    client = context.bot_data["client"]
    today = dt.date.today()
    if today.weekday() != 6:
        return
    day = today.isoformat()
    if db.get_state(_BRIEFING_DATE) == day:
        return
    try:
        Ingestor(client, db).sync_today()
    except Exception as e:  # noqa: BLE001
        _log.warning("job_briefing: sync falhou: %s", e)
    data = build_weekly_briefing(db, today)
    await context.bot.send_message(
        chat_id=cfg.chat_id, text=messages.format_briefing(data),
        parse_mode=messages.PARSE_MODE)
    db.set_state(_BRIEFING_DATE, day)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/bot/test_jobs.py -k job_briefing -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add bot/jobs.py tests/bot/test_jobs.py
git commit -m "feat(bot): job_briefing (domingo, auto-guard weekday)"
```

---

### Task 6: Wiring em `bot/main.py`

**Files:**
- Modify: `bot/main.py:35-40` (bloco do `job_queue`)
- Test: `tests/bot/test_main_wiring.py`

**Interfaces:**
- Consumes: `jobs.job_alerts`, `jobs.job_briefing`.
- Produces: ambos registrados em `run_daily` com `tzinfo=TZ`.

- [ ] **Step 1: Write the failing test**

Adicionar em `tests/bot/test_main_wiring.py` (seguindo o padrão dos testes de wiring já existentes nesse arquivo — inspecionar os callbacks registrados na `job_queue`):

```python
def test_alerts_e_briefing_registrados(monkeypatch):
    import os
    monkeypatch.setenv("TELEGRAM_TOKEN", "x")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "1")
    monkeypatch.setattr("bot.main.HistoryDB", lambda db_path: object())
    monkeypatch.setattr("bot.main.GarminClient", lambda: object())
    from bot import main, jobs
    app = main.build_app()
    callbacks = {j.callback for j in app.job_queue.jobs()}
    assert jobs.job_alerts in callbacks
    assert jobs.job_briefing in callbacks
```

(Se o arquivo já tem um helper de setup/`build_app`, reusar; o ponto é checar que os dois callbacks
estão na fila. Ajustar nomes de env às fixtures existentes do arquivo.)

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/bot/test_main_wiring.py -k registrados -q`
Expected: FAIL — os callbacks ainda não estão na fila.

- [ ] **Step 3: Write minimal implementation**

Em `bot/main.py`, dentro de `build_app`, após `jq.run_repeating(jobs.job_runs, ...)` (linha ~39):

```python
    jq.run_daily(jobs.job_alerts, time=dt.time(hour=10, minute=0, tzinfo=TZ))
    jq.run_daily(jobs.job_briefing, time=dt.time(hour=19, minute=0, tzinfo=TZ))
```

(`job_briefing` roda todo dia 19:00 e se auto-protege por `weekday()` — não usar `days=` do PTB.)

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/bot/test_main_wiring.py -q`
Expected: PASS.

- [ ] **Step 5: Run full suite**

Run: `python -m pytest -q`
Expected: tudo verde.

- [ ] **Step 6: Commit**

```bash
git add bot/main.py tests/bot/test_main_wiring.py
git commit -m "feat(bot): wiring job_alerts (10h) + job_briefing (19h)"
```

---

## Self-Review

**1. Spec coverage:**
- Detectores `hr_rising`/`acwr_risk` → Task 1 ✅
- Briefing builder (agrega + recomendação por zona) → Task 2 ✅
- `format_alert`/`format_briefing` → Task 3 ✅
- `job_alerts` (3 sinais, anti-spam por episódio, loga falhas, best-effort sync) → Task 4 ✅
- `job_briefing` (domingo auto-guard, 1x por data) → Task 5 ✅
- Wiring tz-aware (alertas 10h, briefing 19h) → Task 6 ✅
- Overreaching reusa `compute_readiness` via veredito de `daily_analysis` → Task 4 ✅
- Determinístico / FR55 / loga falhas → constraints aplicadas em cada job ✅

**2. Placeholder scan:** sem TBD/TODO; todo step tem código real. O helper `_FakeDate` da Task 5 é uma
função-fábrica única e limpa.

**3. Type consistency:** `hr_rising`/`acwr_risk` retornam `dict|None` consumidos por `job_alerts` e
`format_alert` pela chave `kind`; `build_weekly_briefing` retorna as 6 chaves que `format_briefing` lê;
`job_alerts` usa `context_from_metrics`/`core.daily_analysis` (veredito com `overreaching` do
sub-projeto 2); estados `alert_hr`/`alert_acwr`/`alert_over`/`briefing_date` consistentes. OK.
