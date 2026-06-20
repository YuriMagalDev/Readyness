# Veredito Inteligente Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Substituir a cascata first-match do veredito por um score de prontidão 0-100 determinístico que soma os sinais da camada de carga + check-ins, deriva o semáforo de faixas e cita os fatores.

**Architecture:** Módulo puro `src/readiness_score.py` (6 funções de desconto + `compute_readiness`). `context_from_metrics` ganha as chaves novas (acwr/soreness/energia/baseline). `HealthMonitor.verdict` passa a delegar pro score. `format_saldo` mostra score + chips de fator.

**Tech Stack:** Python 3.11+, pytest. Reusa `acwr_zone` de `src/training_load.py`.

## Global Constraints

- **Determinístico, sem LLM** no caminho do veredito.
- **Veredito por regra**: o semáforo nunca depende da IA.
- **Bom com metade vazia (FR55)**: sinal ausente (None) desconta **0** — só penaliza com evidência.
- **Rastreável**: o veredito cita as métricas que o geraram (`fatores`).
- Faixas: **score ≥70 → verde · 40-69 → amarelo · <40 → vermelho**.
- ACWR é o sinal de maior peso (−35 na zona risco).
- **Overreaching** é o único override: `desvio_fc>+5` E zona ACWR `risco` E `soreness>=4` → crava vermelho ignorando o score.
- Tabela de descontos (verbatim): ACWR risco −35 · FC desvio +3..+5 −12, >+5 −25 · soreness 3 −10, 4 −18, 5 −25 · dívida sono 2..4h −10, >4h −20 · energia 3 −6, 2 −12, 1 −15 · battery 25..49 −8, <25 −15.
- pt-BR em motivos/labels.

---

### Task 1: Funções de desconto puras

**Files:**
- Create: `src/readiness_score.py`
- Test: `tests/test_readiness_score.py`

**Interfaces:**
- Consumes: `acwr_zone(acwr) -> str` de `src/training_load.py` (zonas: "baixo"|"otimo"|"risco"|"ausente").
- Produces: constantes de limiar/desconto + 6 funções `_deduction_*(...) -> tuple[int, dict|None]`. O dict de fator é `{"chave": str, "label": str, "valor": Any, "desconto": int}`. None quando não há desconto.

- [ ] **Step 1: Write the failing test**

```python
import pytest
from src.readiness_score import (
    _deduction_acwr, _deduction_hr, _deduction_soreness,
    _deduction_sleep, _deduction_energia, _deduction_battery,
)


def test_acwr_so_penaliza_risco():
    assert _deduction_acwr(None) == (0, None)
    assert _deduction_acwr(1.0)[0] == 0          # zona otimo
    assert _deduction_acwr(0.5)[0] == 0          # zona baixo (fresco)
    d, fator = _deduction_acwr(1.8)              # zona risco
    assert d == 35 and fator["chave"] == "acwr" and fator["desconto"] == 35


def test_hr_por_desvio_da_baseline():
    assert _deduction_hr(None, 50) == (0, None)
    assert _deduction_hr(50, None) == (0, None)
    assert _deduction_hr(52, 50) == (0, None)    # desvio +2
    assert _deduction_hr(54, 50)[0] == 12        # desvio +4 (faixa 3..5)
    assert _deduction_hr(55, 50)[0] == 12        # desvio +5 (inclusivo)
    assert _deduction_hr(57, 50)[0] == 25        # desvio +7 (>5)


def test_soreness_faixas():
    assert _deduction_soreness(None) == (0, None)
    assert _deduction_soreness(2) == (0, None)
    assert _deduction_soreness(3)[0] == 10
    assert _deduction_soreness(4)[0] == 18
    assert _deduction_soreness(5)[0] == 25


def test_sleep_faixas():
    assert _deduction_sleep(1.5) == (0, None)
    assert _deduction_sleep(2.0)[0] == 10
    assert _deduction_sleep(4.0)[0] == 10
    assert _deduction_sleep(5.0)[0] == 20


def test_energia_faixas():
    assert _deduction_energia(None) == (0, None)
    assert _deduction_energia(5) == (0, None)
    assert _deduction_energia(3)[0] == 6
    assert _deduction_energia(2)[0] == 12
    assert _deduction_energia(1)[0] == 15


def test_battery_faixas():
    assert _deduction_battery(None) == (0, None)
    assert _deduction_battery(80) == (0, None)
    assert _deduction_battery(40)[0] == 8
    assert _deduction_battery(20)[0] == 15
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_readiness_score.py -q`
Expected: FAIL — `ImportError: cannot import name '_deduction_acwr'`.

- [ ] **Step 3: Write minimal implementation**

```python
from src.training_load import acwr_zone

# Descontos (pontos tirados de 100). ACWR é o mais pesado.
ACWR_RISK_DED = 35
HR_MID_DED, HR_HIGH_DED = 12, 25          # desvio +3..+5 / >+5 bpm
SOR_DED = {3: 10, 4: 18, 5: 25}
SLEEP_MID_DED, SLEEP_HIGH_DED = 10, 20    # 2..4h / >4h
EN_DED = {3: 6, 2: 12, 1: 15}
BAT_MID_DED, BAT_HIGH_DED = 8, 15         # 25..49 / <25


def _fator(chave, label, valor, desconto):
    return {"chave": chave, "label": label, "valor": valor, "desconto": desconto}


def _deduction_acwr(acwr):
    if acwr is None:
        return 0, None
    if acwr_zone(acwr) == "risco":
        return ACWR_RISK_DED, _fator("acwr", "Carga (ACWR)", round(acwr, 2), ACWR_RISK_DED)
    return 0, None


def _deduction_hr(today, baseline):
    if today is None or baseline is None:
        return 0, None
    desvio = today - baseline
    if desvio > 5:
        d = HR_HIGH_DED
    elif desvio >= 3:
        d = HR_MID_DED
    else:
        return 0, None
    return d, _fator("resting_hr", "FC repouso", today, d)


def _deduction_soreness(v):
    if v is None or v not in SOR_DED:
        return 0, None
    return SOR_DED[v], _fator("soreness", "Dor muscular", v, SOR_DED[v])


def _deduction_sleep(debt):
    if debt is None:
        return 0, None
    if debt > 4:
        d = SLEEP_HIGH_DED
    elif debt >= 2:
        d = SLEEP_MID_DED
    else:
        return 0, None
    return d, _fator("sleep_debt", "Dívida de sono", f"{debt}h", d)


def _deduction_energia(v):
    if v is None or v not in EN_DED:
        return 0, None
    return EN_DED[v], _fator("energia", "Energia", v, EN_DED[v])


def _deduction_battery(b):
    if b is None:
        return 0, None
    if b < 25:
        d = BAT_HIGH_DED
    elif b < 50:
        d = BAT_MID_DED
    else:
        return 0, None
    return d, _fator("body_battery", "Body Battery", b, d)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_readiness_score.py -q`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git add src/readiness_score.py tests/test_readiness_score.py
git commit -m "feat(score): funcoes de desconto por sinal (puras)"
```

---

### Task 2: `compute_readiness`

**Files:**
- Modify: `src/readiness_score.py`
- Test: `tests/test_readiness_score.py`

**Interfaces:**
- Consumes: as 6 `_deduction_*` da Task 1.
- Produces: `compute_readiness(context: dict) -> dict` com chaves `status`, `score`, `motivo`, `recomendacao`, `overreaching`, `fatores` (lista ordenada por desconto desc, só >0). Lê do context: `acwr`, `resting_hr_today`, `resting_hr_baseline`, `soreness`, `sleep_debt_hours`, `energia`, `morning_battery_avg`.

- [ ] **Step 1: Write the failing test**

```python
from src.readiness_score import compute_readiness


def test_dia_perfeito_score_100_verde():
    out = compute_readiness({})
    assert out["score"] == 100
    assert out["status"] == "verde"
    assert out["motivo"] == "Métricas normais"
    assert out["fatores"] == []
    assert out["overreaching"] is False


def test_faixas_de_status():
    # soreness 3 (-10) -> 90 verde
    assert compute_readiness({"soreness": 3})["status"] == "verde"
    # descontos somando 31 -> 69 amarelo (soreness 5=25 + energia 3=6)
    out = compute_readiness({"soreness": 5, "energia": 3})
    assert out["score"] == 69 and out["status"] == "amarelo"
    # somando 61 -> 39 vermelho (acwr risco 35 + soreness 25 + ... ajuste)
    out = compute_readiness({"acwr": 1.8, "soreness": 5})  # 35+25=60 -> 40 amarelo
    assert out["score"] == 40 and out["status"] == "amarelo"
    out = compute_readiness({"acwr": 1.8, "soreness": 5, "energia": 3})  # 60+6=66 -> 34 vermelho
    assert out["score"] == 34 and out["status"] == "vermelho"


def test_clamp_nao_negativo():
    out = compute_readiness({
        "acwr": 1.8, "resting_hr_today": 70, "resting_hr_baseline": 50,
        "soreness": 5, "sleep_debt_hours": 6, "energia": 1, "morning_battery_avg": 10,
    })
    assert out["score"] == 0
    assert out["status"] == "vermelho"


def test_fatores_ordenados_e_motivo():
    out = compute_readiness({"soreness": 4, "sleep_debt_hours": 3, "energia": 3})
    # descontos: soreness 18, sleep 10, energia 6 -> ordenados desc
    descontos = [f["desconto"] for f in out["fatores"]]
    assert descontos == sorted(descontos, reverse=True)
    assert out["fatores"][0]["chave"] == "soreness"
    assert "dor muscular" in out["motivo"].lower()


def test_ausencia_nao_penaliza():
    # só FC ruim; resto None -> desconta só FC
    out = compute_readiness({"resting_hr_today": 60, "resting_hr_baseline": 50})
    assert len(out["fatores"]) == 1 and out["fatores"][0]["chave"] == "resting_hr"


def test_overreaching_crava_vermelho():
    ctx = {
        "resting_hr_today": 58, "resting_hr_baseline": 50,  # desvio +8 (>5)
        "acwr": 1.8,                                         # zona risco
        "soreness": 4,                                       # >=4
        "morning_battery_avg": 90, "energia": 5,             # resto ótimo
    }
    out = compute_readiness(ctx)
    assert out["overreaching"] is True
    assert out["status"] == "vermelho"
    assert "overreaching" in out["motivo"].lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_readiness_score.py -k "compute or faixas or clamp or fatores or ausencia or overreaching or perfeito" -q`
Expected: FAIL — `ImportError: cannot import name 'compute_readiness'`.

- [ ] **Step 3: Write minimal implementation**

Adicionar em `src/readiness_score.py`:

```python
VERDE_MIN, AMARELO_MIN = 70, 40

_RECOMENDACAO = {
    "verde": "Pode treinar conforme planejado.",
    "amarelo": "Treino leve ou moderado; evite intensidade alta.",
    "vermelho": "Priorize recuperação. Evite treino intenso.",
}


def _status_por_score(score):
    if score >= VERDE_MIN:
        return "verde"
    if score >= AMARELO_MIN:
        return "amarelo"
    return "vermelho"


def _is_overreaching(context):
    today = context.get("resting_hr_today")
    baseline = context.get("resting_hr_baseline")
    soreness = context.get("soreness")
    acwr = context.get("acwr")
    if today is None or baseline is None or soreness is None or acwr is None:
        return False
    return (today - baseline) > 5 and acwr_zone(acwr) == "risco" and soreness >= 4


def compute_readiness(context: dict) -> dict:
    """Veredito determinístico por score 0-100 + fatores citados."""
    pares = [
        _deduction_acwr(context.get("acwr")),
        _deduction_hr(context.get("resting_hr_today"), context.get("resting_hr_baseline")),
        _deduction_soreness(context.get("soreness")),
        _deduction_sleep(context.get("sleep_debt_hours", 0)),
        _deduction_energia(context.get("energia")),
        _deduction_battery(context.get("morning_battery_avg")),
    ]
    fatores = [f for d, f in pares if f is not None]
    fatores.sort(key=lambda f: f["desconto"], reverse=True)
    total = sum(d for d, _ in pares)
    score = max(0, min(100, 100 - total))
    status = _status_por_score(score)

    if not fatores:
        motivo = "Métricas normais"
    else:
        motivo = "; ".join(f"{f['label'].lower()} {f['valor']}" for f in fatores[:3])

    recomendacao = _RECOMENDACAO[status]
    overreaching = _is_overreaching(context)
    if overreaching:
        status = "vermelho"
        motivo = "possível overreaching: FC acima da base, carga em risco e dor alta"
        recomendacao = "Descanso. 3 sinais de sobrecarga juntos."

    return {
        "status": status,
        "score": score,
        "motivo": motivo,
        "recomendacao": recomendacao,
        "overreaching": overreaching,
        "fatores": fatores,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_readiness_score.py -q`
Expected: PASS (all).

- [ ] **Step 5: Commit**

```bash
git add src/readiness_score.py tests/test_readiness_score.py
git commit -m "feat(score): compute_readiness (score, faixas, fatores, overreaching)"
```

---

### Task 3: Estender `context_from_metrics`

**Files:**
- Modify: `src/metric_reader.py:40-66` (função `context_from_metrics`)
- Test: `tests/test_metric_reader.py`
- Modify (regressão da fundação): `tests/test_training_load_regression.py`

**Interfaces:**
- Consumes: `db.get_metrics(date) -> list[dict]` (rows com `metric_key`, `value`).
- Produces: `context_from_metrics` agora inclui `acwr`, `soreness`, `energia`, `resting_hr_baseline` (None quando ausentes), além das 5 chaves existentes.

- [ ] **Step 1: Write the failing test**

Adicionar em `tests/test_metric_reader.py`:

```python
def test_context_inclui_sinais_novos(tmp_path):
    import datetime
    from src.history_db import HistoryDB
    from src.metric_reader import context_from_metrics
    db = HistoryDB(str(tmp_path / "c.db"))
    db.upsert_metric("2026-06-20", "acwr", 1.4, "2026-06-20T10:00:00", "computed")
    db.upsert_metric("2026-06-20", "soreness", 3, "2026-06-20T07:00:00", "manual")
    db.upsert_metric("2026-06-20", "resting_hr_baseline", 51.0, "2026-06-20T08:00:00", "computed")
    ctx = context_from_metrics(db, "2026-06-20", today=datetime.date(2026, 6, 20))
    assert ctx["acwr"] == 1.4
    assert ctx["soreness"] == 3
    assert ctx["resting_hr_baseline"] == 51.0
    assert ctx["energia"] is None        # ausente -> None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_metric_reader.py -k inclui_sinais_novos -q`
Expected: FAIL — `KeyError: 'acwr'`.

- [ ] **Step 3: Write minimal implementation**

Em `src/metric_reader.py`, no fim de `context_from_metrics`, antes do `return`, ler o dia e ampliar o dict retornado:

```python
    day_metrics = {r["metric_key"]: r["value"] for r in db.get_metrics(date)}

    return {
        "resting_hr_today": hr_today,
        "resting_hr_avg_7d": hr_avg,
        "sleep_debt_hours": round(debt, 1),
        "morning_battery_avg": battery,
        "run_sessions_7d": runs,
        "acwr": day_metrics.get("acwr"),
        "soreness": day_metrics.get("soreness"),
        "energia": day_metrics.get("energia"),
        "resting_hr_baseline": day_metrics.get("resting_hr_baseline"),
    }
```

(Substitui o `return {...}` antigo de 5 chaves pelo de 9 chaves acima.)

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_metric_reader.py -q`
Expected: PASS.

- [ ] **Step 5: Atualizar o lock de regressão da fundação**

O teste `test_context_ignora_metricas_de_carga` em `tests/test_training_load_regression.py` trava o context nas 5 chaves antigas (era o lock do dual-track durante o sub-projeto 1). Agora cruzamos de propósito. Substituir o corpo do teste por:

```python
def test_context_inclui_metricas_de_carga(tmp_path):
    """Sub-projeto 2: agora o context EXPÕE acwr/soreness/energia/baseline pro veredito."""
    db = HistoryDB(str(tmp_path / "r.db"))
    db.upsert_metric("2026-06-20", "acwr", 1.8, "2026-06-20T10:00:00", "computed")
    db.upsert_metric("2026-06-20", "resting_hr", 55, "2026-06-20T08:00:00", "garmin")
    ctx = context_from_metrics(db, "2026-06-20", today=datetime.date(2026, 6, 20))
    assert ctx["acwr"] == 1.8
    assert set(ctx.keys()) == {
        "resting_hr_today", "resting_hr_avg_7d", "sleep_debt_hours",
        "morning_battery_avg", "run_sessions_7d",
        "acwr", "soreness", "energia", "resting_hr_baseline",
    }
```

(Renomeia o teste e inverte a asserção: era "ignora", agora "inclui". O segundo teste do arquivo, `test_read_metrics_expoe_acwr`, fica inalterado.)

- [ ] **Step 6: Run tests to verify both pass**

Run: `python -m pytest tests/test_metric_reader.py tests/test_training_load_regression.py -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/metric_reader.py tests/test_metric_reader.py tests/test_training_load_regression.py
git commit -m "feat(context): expoe acwr/soreness/energia/baseline pro veredito"
```

---

### Task 4: `HealthMonitor.verdict` delega pro score

**Files:**
- Modify: `src/health_monitor.py:39-41` (método `verdict`)
- Test: `tests/test_health_monitor.py:50-63` (os 2 testes de `verdict`)

**Interfaces:**
- Consumes: `compute_readiness(context)` da Task 2.
- Produces: `HealthMonitor().verdict(context)` retorna o dict de `compute_readiness` (com `score`/`fatores`). `_evaluate_rules` e `check()` ficam inalterados (usados como preliminar do `check`).

- [ ] **Step 1: Write the failing test**

Substituir os 2 testes de `verdict` (atualmente em `tests/test_health_monitor.py`, ~linhas 50-63) por:

```python
def test_verdict_usa_score_e_cita_fatores():
    ctx = {"resting_hr_today": 60, "resting_hr_baseline": 50,  # desvio +10 -> -25
           "morning_battery_avg": 90}
    out = HealthMonitor().verdict(ctx)
    assert out["score"] == 75 and out["status"] == "verde"
    assert out["fatores"][0]["chave"] == "resting_hr"


def test_verdict_dia_bom_verde_score_alto():
    ctx = {"resting_hr_today": 50, "resting_hr_baseline": 50, "morning_battery_avg": 90}
    out = HealthMonitor().verdict(ctx)
    assert out["status"] == "verde" and out["score"] == 100
```

(Os testes de `_evaluate_rules` no mesmo arquivo — FC alta/bateria/sono — ficam como estão; `_evaluate_rules` não muda.)

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_health_monitor.py -k "usa_score or dia_bom" -q`
Expected: FAIL — `KeyError: 'score'` (verdict ainda usa a cascata).

- [ ] **Step 3: Write minimal implementation**

Em `src/health_monitor.py`: adicionar import no topo e trocar o corpo de `verdict`:

```python
from src.readiness_score import compute_readiness
```

```python
    def verdict(self, context: dict) -> dict:
        """Veredito determinístico por score 0-100 (sem LLM)."""
        return compute_readiness(context)
```

(Manter `_evaluate_rules` e `check` como estão.)

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_health_monitor.py -q`
Expected: PASS (testes de verdict novos + os de `_evaluate_rules` intactos).

- [ ] **Step 5: Commit**

```bash
git add src/health_monitor.py tests/test_health_monitor.py
git commit -m "feat(verdict): HealthMonitor.verdict delega pro readiness score"
```

---

### Task 5: `format_saldo` mostra score + fatores

**Files:**
- Modify: `bot/messages.py:70-96` (função `format_saldo`)
- Test: `tests/bot/test_messages.py`

**Interfaces:**
- Consumes: o veredito de `compute_readiness` (chaves `score`, `fatores`).
- Produces: a mensagem do `/saldo` inclui `· prontidão N/100` na linha do semáforo e uma linha de chips de fator quando houver; degrada (só semáforo) quando `score`/`fatores` ausentes.

- [ ] **Step 1: Write the failing test**

Adicionar em `tests/bot/test_messages.py`:

```python
def test_saldo_mostra_score_e_fatores():
    from bot import messages
    veredito = {
        "status": "amarelo", "score": 58, "motivo": "dor muscular 4",
        "recomendacao": "Treino leve.",
        "fatores": [{"chave": "soreness", "label": "Dor muscular", "valor": 4, "desconto": 18}],
    }
    txt = messages.format_saldo(veredito, MET)
    assert "58/100" in txt
    assert "Dor muscular" in txt


def test_saldo_sem_score_degrada():
    from bot import messages
    veredito = {"status": "verde", "motivo": "Métricas normais", "recomendacao": "Pode treinar."}
    txt = messages.format_saldo(veredito, MET)   # sem 'score'/'fatores'
    assert "/100" not in txt                       # não quebra, só omite
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/bot/test_messages.py -k "score_e_fatores or sem_score" -q`
Expected: FAIL — `assert "58/100" in txt`.

- [ ] **Step 3: Write minimal implementation**

Em `bot/messages.py`, dentro de `format_saldo`, trocar o bloco que monta a linha do semáforo/motivo (linhas ~77-83) por:

```python
    score = veredito.get("score")
    titulo = f"{sem} <b>{word}</b>"
    if score is not None:
        titulo += f"  ·  prontidão {score}/100"
    linhas.append(titulo)
    motivo = veredito.get("motivo")
    if motivo:
        linhas.append(f"<i>{_e(motivo)}</i>")
    fatores = veredito.get("fatores") or []
    if fatores:
        chips = " · ".join(f"{_e(f['label'])} {_e(f['valor'])}" for f in fatores[:3])
        linhas.append(f"⚠️ {chips}")
    rec = veredito.get("recomendacao")
    if rec:
        linhas.append(f"→ {_e(rec)}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/bot/test_messages.py -q`
Expected: PASS.

- [ ] **Step 5: Run full suite**

Run: `python -m pytest -q`
Expected: tudo verde (sem regressões em jobs/handlers/api que consomem o veredito).

- [ ] **Step 6: Commit**

```bash
git add bot/messages.py tests/bot/test_messages.py
git commit -m "feat(bot): /saldo mostra prontidao N/100 + chips de fator"
```

---

## Self-Review

**1. Spec coverage:**
- Modelo de score (6 sinais, descontos, clamp) → Task 1 + 2 ✅
- Faixas de status → Task 2 ✅
- Overreaching override → Task 2 ✅
- Rastreabilidade (fatores citados) → Task 2 (fatores) + Task 5 (chips) ✅
- `readiness_score.py` puro → Task 1/2 ✅
- Estender `context_from_metrics` + cross-track (atualizar regressão da fundação) → Task 3 ✅
- `HealthMonitor.verdict` delega → Task 4 ✅
- `format_saldo` mostra score+fatores → Task 5 ✅
- Verificação e2e (suite verde, IA fora → veredito segue) → Task 5 Step 5 (suite) + arquitetura (verdict não chama LLM) ✅

**2. Placeholder scan:** sem TBD/TODO; todo step tem código real.

**3. Type consistency:** `_deduction_*` retornam `(int, dict|None)` consumidos por `compute_readiness`; fator dict `{chave,label,valor,desconto}` usado consistentemente em Task 2 (ordenação por `desconto`) e Task 5 (`label`/`valor`); `compute_readiness` retorna `status/score/motivo/recomendacao/overreaching/fatores`, e Task 4/5 leem exatamente essas chaves; `context_from_metrics` produz `acwr/soreness/energia/resting_hr_baseline` que `compute_readiness` lê pelos mesmos nomes. OK.
