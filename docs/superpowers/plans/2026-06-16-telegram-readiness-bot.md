# Readiness Telegram Bot — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bot de Telegram pessoal que manda o "saldo do dia" ao detectar o despertar via Garmin, com comandos sob demanda, check-in noturno interativo e resumos semana/mês com gráfico.

**Architecture:** Processo único `python-telegram-bot` (long-polling, sem URL pública) com `JobQueue`. Reusa o cérebro em `src/` (garmin_client, daily_analysis, ingestor, history_db, analytics, insight_engine). Lógica de check-in/tendências migra de `api/services.py` para `src/services_core.py` pra desacoplar do FastAPI (que sai de escopo). LLM segue na Anthropic.

**Tech Stack:** Python 3.11+, python-telegram-bot v21 (async/JobQueue), matplotlib (PNG), SQLite, garminconnect, anthropic, pytest.

---

## File Structure

- `requirements.txt` — adiciona `python-telegram-bot>=21.6`, `matplotlib>=3.8`.
- `src/services_core.py` — **novo**: `save_checkin(db, payload, today)` e `build_trends(db, period, force)` movidos de `api/services.py`.
- `api/services.py` — re-exporta de `services_core` (back-compat até o `api/` ser aposentado).
- `src/history_db.py` — adiciona tabela `bot_state` + acessores `get_state/set_state`.
- `bot/config.py` — lê `.env` (token, chat id, horários, janela, DB_PATH).
- `bot/state.py` — dedup (datas de último saldo/checkin) sobre `bot_state`.
- `bot/wake_detector.py` — extrai hora de acordar do DTO de sono; decide "já acordou hoje?".
- `bot/messages.py` — formata texto do saldo e dos insights.
- `bot/charts.py` — render PNG do trio de recuperação (FC/Sono/Bateria).
- `bot/handlers.py` — CommandHandlers (`/start /saldo /insights /checkin /semana /mes`) + CallbackQueryHandler (botões 1–5) + guarda de chat.
- `bot/jobs.py` — `job_wake` (poll matinal) e `job_checkin` (21h).
- `bot/main.py` — monta `Application`, registra handlers/jobs, `run_polling()`.
- `bot/__init__.py` — vazio.
- `deploy/readiness-bot.service` — unit systemd.
- `iniciar_bot.bat` — sobe o bot localmente (dev).
- Testes em `tests/bot/` espelhando os módulos puros.

> Telegram e Garmin **sempre mockados** nos testes. Nada bate em rede real.

---

## Task 1: Dependências

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Adicionar libs**

Acrescente ao fim de `requirements.txt`:
```
python-telegram-bot>=21.6
matplotlib>=3.8
```

- [ ] **Step 2: Instalar**

Run: `pip install -r requirements.txt`
Expected: instala `python-telegram-bot` e `matplotlib` sem erro.

- [ ] **Step 3: Commit**

```bash
git add requirements.txt
git commit -m "build: add python-telegram-bot + matplotlib para o bot"
```

---

## Task 2: Tabela `bot_state` + acessores

**Files:**
- Modify: `src/history_db.py`
- Test: `tests/test_history_db_state.py`

- [ ] **Step 1: Escrever teste que falha**

```python
# tests/test_history_db_state.py
from src.history_db import HistoryDB

def test_state_roundtrip(tmp_path):
    db = HistoryDB(db_path=str(tmp_path / "h.db"))
    assert db.get_state("saldo_date") is None
    db.set_state("saldo_date", "2026-06-16")
    assert db.get_state("saldo_date") == "2026-06-16"
    # sobrescreve
    db.set_state("saldo_date", "2026-06-17")
    assert db.get_state("saldo_date") == "2026-06-17"
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/test_history_db_state.py -v`
Expected: FAIL (`AttributeError: 'HistoryDB' object has no attribute 'get_state'`).

- [ ] **Step 3: Implementar**

Em `src/history_db.py`, dentro de `_init_db`, depois do `CREATE TABLE ... metric_value (...)`:
```python
            conn.execute(
                "CREATE TABLE IF NOT EXISTS bot_state ("
                "key TEXT PRIMARY KEY, value TEXT)"
            )
```
E adicione os métodos (perto dos outros acessores):
```python
    def get_state(self, key: str):
        with self._connect() as conn:
            row = conn.execute(
                "SELECT value FROM bot_state WHERE key = ?", (key,)
            ).fetchone()
            return row["value"] if row else None

    def set_state(self, key: str, value: str):
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO bot_state (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value),
            )
```

- [ ] **Step 4: Rodar e ver passar**

Run: `pytest tests/test_history_db_state.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/history_db.py tests/test_history_db_state.py
git commit -m "feat(db): tabela bot_state + get_state/set_state"
```

---

## Task 3: Mover save_checkin/build_trends para src/services_core.py

**Files:**
- Create: `src/services_core.py`
- Modify: `api/services.py`
- Test: `tests/test_services_core.py`

- [ ] **Step 1: Teste que falha**

```python
# tests/test_services_core.py
import datetime as dt
import pytest
from src.history_db import HistoryDB
from src.services_core import save_checkin

def test_save_checkin_grava_1a5(tmp_path):
    db = HistoryDB(db_path=str(tmp_path / "h.db"))
    save_checkin(db, {"hidratacao": 4, "energia": 2}, today=dt.date(2026, 6, 16))
    rows = db.get_metrics_for_date("2026-06-16")  # ver Step 3 (helper de leitura)
    vals = {r["metric_key"]: r["value"] for r in rows}
    assert vals["hidratacao"] == 4 and vals["energia"] == 2

def test_save_checkin_rejeita_fora_de_faixa(tmp_path):
    db = HistoryDB(db_path=str(tmp_path / "h.db"))
    with pytest.raises(ValueError):
        save_checkin(db, {"hidratacao": 9}, today=dt.date(2026, 6, 16))
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/test_services_core.py -v`
Expected: FAIL (`ModuleNotFoundError: src.services_core`).

- [ ] **Step 3: Implementar services_core + helper de leitura**

Crie `src/services_core.py` movendo a lógica que hoje está em `api/services.py`:
```python
"""Lógica de domínio independente da camada FastAPI (usada pelo bot)."""
import datetime as _dt

from src.analytics import Analytics
from src.insight_engine import InsightEngine

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


def _period_range(period: int):
    end = _dt.date.today()
    start = end - _dt.timedelta(days=period - 1)
    return start.isoformat(), end.isoformat()


def build_trends(db, period: int = 30, force: bool = False) -> dict:
    start, end = _period_range(period)
    snaps = db.get_snapshots(start, end)
    metrics = Analytics().summary(snaps)
    insights = InsightEngine(db=db).trend_insights(metrics, period=period, force=force)
    return {"period": period, "metrics": metrics, "insights": insights}
```

Em `src/history_db.py`, adicione um leitor simples por data (usado nos testes e no check-in):
```python
    def get_metrics_for_date(self, day: str) -> list:
        with self._connect() as conn:
            return [dict(r) for r in conn.execute(
                "SELECT metric_key, value, measured_at, source FROM metric_value "
                "WHERE date = ?", (day,)
            )]
```

Em `api/services.py`, **remova** as definições locais de `save_checkin`, `build_trends`, `_period_range` e re-exporte:
```python
from src.services_core import save_checkin, build_trends, _period_range  # noqa: F401
```

- [ ] **Step 4: Rodar e ver passar (inclui suíte antiga)**

Run: `pytest tests/test_services_core.py -v && pytest -q`
Expected: PASS; nada quebrado em `api/`.

- [ ] **Step 5: Commit**

```bash
git add src/services_core.py src/history_db.py api/services.py tests/test_services_core.py
git commit -m "refactor: move save_checkin/build_trends para src/services_core (desacopla do FastAPI)"
```

---

## Task 4: Config do bot

**Files:**
- Create: `bot/__init__.py`, `bot/config.py`
- Test: `tests/bot/test_config.py`

- [ ] **Step 1: Teste que falha**

```python
# tests/bot/test_config.py
from bot.config import Config

def test_config_le_env(monkeypatch):
    monkeypatch.setenv("TELEGRAM_TOKEN", "tok")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123")
    monkeypatch.setenv("CHECKIN_HOUR", "21")
    monkeypatch.setenv("WAKE_WINDOW_START", "05:00")
    monkeypatch.setenv("WAKE_WINDOW_END", "11:00")
    c = Config.from_env()
    assert c.token == "tok"
    assert c.chat_id == 123
    assert c.checkin_hour == 21
    assert c.wake_start == (5, 0) and c.wake_end == (11, 0)

def test_config_exige_token(monkeypatch):
    monkeypatch.delenv("TELEGRAM_TOKEN", raising=False)
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "1")
    import pytest
    with pytest.raises(ValueError):
        Config.from_env()
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/bot/test_config.py -v`
Expected: FAIL (`ModuleNotFoundError: bot.config`).

- [ ] **Step 3: Implementar**

Crie `bot/__init__.py` vazio e `bot/config.py`:
```python
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


def _hm(s: str) -> tuple:
    h, m = s.split(":")
    return int(h), int(m)


@dataclass
class Config:
    token: str
    chat_id: int
    checkin_hour: int
    wake_start: tuple
    wake_end: tuple
    wake_poll_minutes: int
    db_path: str

    @classmethod
    def from_env(cls) -> "Config":
        token = os.getenv("TELEGRAM_TOKEN")
        chat = os.getenv("TELEGRAM_CHAT_ID")
        if not token or not chat:
            raise ValueError("TELEGRAM_TOKEN e TELEGRAM_CHAT_ID são obrigatórios")
        return cls(
            token=token,
            chat_id=int(chat),
            checkin_hour=int(os.getenv("CHECKIN_HOUR", "21")),
            wake_start=_hm(os.getenv("WAKE_WINDOW_START", "05:00")),
            wake_end=_hm(os.getenv("WAKE_WINDOW_END", "11:00")),
            wake_poll_minutes=int(os.getenv("WAKE_POLL_MINUTES", "15")),
            db_path=os.getenv("DB_PATH", "history.db"),
        )
```

- [ ] **Step 4: Rodar e ver passar**

Run: `pytest tests/bot/test_config.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add bot/__init__.py bot/config.py tests/bot/test_config.py
git commit -m "feat(bot): Config.from_env"
```

---

## Task 5: Detector de despertar

**Files:**
- Create: `bot/wake_detector.py`
- Test: `tests/bot/test_wake_detector.py`

Garmin `get_sleep_day(day)` devolve um dict com `dailySleepDTO`, contendo
`sleepEndTimestampLocal` (epoch ms) quando o sono já foi fechado/sincronizado.

- [ ] **Step 1: Teste que falha**

```python
# tests/bot/test_wake_detector.py
from bot.wake_detector import wake_time_local

def test_extrai_hora_de_acordar():
    # 2026-06-16 06:12 local -> epoch ms
    sleep = {"dailySleepDTO": {"sleepEndTimestampLocal": 1781503920000}}
    hhmm = wake_time_local(sleep)
    assert hhmm == "06:12"

def test_sem_fim_de_sono_retorna_none():
    assert wake_time_local({"dailySleepDTO": {}}) is None
    assert wake_time_local({}) is None
    assert wake_time_local(None) is None
```

> O epoch acima é ilustrativo; o teste valida formato `HH:MM`. Calcule o esperado com
> `datetime.utcfromtimestamp(1781503920000/1000).strftime("%H:%M")` ao escrever o teste e
> ajuste a string esperada pra casar com a conversão usada na implementação (UTC dos
> timestamps `*Local` do Garmin, que já vêm no fuso local como se fosse UTC).

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/bot/test_wake_detector.py -v`
Expected: FAIL (`ModuleNotFoundError: bot.wake_detector`).

- [ ] **Step 3: Implementar**

```python
# bot/wake_detector.py
import datetime as _dt


def wake_time_local(sleep_day: dict):
    """Hora de acordar 'HH:MM' a partir do DTO de sono, ou None se ainda não há.
    Os timestamps *Local do Garmin vêm em ms já no fuso local (tratar como UTC)."""
    if not sleep_day:
        return None
    dto = sleep_day.get("dailySleepDTO") or {}
    ts = dto.get("sleepEndTimestampLocal")
    if not ts:
        return None
    return _dt.datetime.utcfromtimestamp(ts / 1000).strftime("%H:%M")


def woke_up_today(sleep_day: dict) -> bool:
    return wake_time_local(sleep_day) is not None
```

- [ ] **Step 4: Rodar e ver passar**

Run: `pytest tests/bot/test_wake_detector.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add bot/wake_detector.py tests/bot/test_wake_detector.py
git commit -m "feat(bot): wake_detector (hora de acordar do DTO de sono)"
```

---

## Task 6: Estado/dedup do bot

**Files:**
- Create: `bot/state.py`
- Test: `tests/bot/test_state.py`

- [ ] **Step 1: Teste que falha**

```python
# tests/bot/test_state.py
from src.history_db import HistoryDB
from bot.state import already_sent_saldo, mark_saldo_sent

def test_dedup_saldo(tmp_path):
    db = HistoryDB(db_path=str(tmp_path / "h.db"))
    assert already_sent_saldo(db, "2026-06-16") is False
    mark_saldo_sent(db, "2026-06-16")
    assert already_sent_saldo(db, "2026-06-16") is True
    assert already_sent_saldo(db, "2026-06-17") is False
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/bot/test_state.py -v`
Expected: FAIL (`ModuleNotFoundError: bot.state`).

- [ ] **Step 3: Implementar**

```python
# bot/state.py
def already_sent_saldo(db, day: str) -> bool:
    return db.get_state("saldo_date") == day


def mark_saldo_sent(db, day: str):
    db.set_state("saldo_date", day)


def already_prompted_checkin(db, day: str) -> bool:
    return db.get_state("checkin_date") == day


def mark_checkin_prompted(db, day: str):
    db.set_state("checkin_date", day)
```

- [ ] **Step 4: Rodar e ver passar**

Run: `pytest tests/bot/test_state.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add bot/state.py tests/bot/test_state.py
git commit -m "feat(bot): dedup de saldo/checkin via bot_state"
```

---

## Task 7: Formatação das mensagens

**Files:**
- Create: `bot/messages.py`
- Test: `tests/bot/test_messages.py`

`DailyAnalysis.build` devolve `{"date","veredito":{"status","motivo","recomendacao"},"insights":[...]}`.
O saldo precisa das 4 métricas-chave; o bot passa um dict `metrics` (montado pelo job a partir
do `context`/snapshot) com as mesmas chaves do front: `resting_hr_today`, `resting_hr_avg_7d`,
`morning_battery_avg`, `sleep_debt_hours`, `run_sessions_7d`.

- [ ] **Step 1: Teste que falha**

```python
# tests/bot/test_messages.py
from bot.messages import format_saldo, format_insights

VER = {"status": "amarelo", "motivo": "Dívida de sono 2.4h", "recomendacao": "Durma cedo."}
MET = {"resting_hr_today": 55, "resting_hr_avg_7d": 60.9, "morning_battery_avg": 38,
       "sleep_debt_hours": 2.4, "run_sessions_7d": 3}

def test_saldo_tem_veredito_e_metricas():
    txt = format_saldo(VER, MET, wake="06:12")
    assert "06:12" in txt
    assert "🟡" in txt and "Durma cedo" in txt
    assert "55" in txt and "-5.9" in txt   # delta FC
    assert "2.4" in txt                      # dívida de sono
    assert "3" in txt                        # corridas

def test_insights_vazio():
    assert "indisponível" in format_insights([]).lower()

def test_insights_lista():
    ins = [{"texto": "FC alta + bateria baixa", "metricas_usadas": [
        {"label": "FC repouso", "valor": 55, "unidade": " bpm"}]}]
    txt = format_insights(ins)
    assert "FC alta" in txt and "FC repouso" in txt and "55" in txt
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/bot/test_messages.py -v`
Expected: FAIL (`ModuleNotFoundError: bot.messages`).

- [ ] **Step 3: Implementar**

```python
# bot/messages.py
_SEMAFORO = {"verde": "🟢", "amarelo": "🟡", "vermelho": "🔴"}


def format_saldo(veredito: dict, m: dict, wake: str = None) -> str:
    sem = _SEMAFORO.get(veredito.get("status"), "⚪")
    head = f"☀️ Bom dia — acordou {wake}" if wake else "☀️ Bom dia"
    delta = m["resting_hr_today"] - m["resting_hr_avg_7d"]
    delta_s = f"{'+' if delta > 0 else ''}{delta:.1f}"
    linhas = [
        head,
        f"{sem} {veredito.get('motivo', '')}",
        veredito.get("recomendacao", ""),
        "",
        f"FC repouso  {m['resting_hr_today']}  ({delta_s} vs 7d)",
        f"Body Battery {m['morning_battery_avg']}",
        f"Sono · dívida {m['sleep_debt_hours']}h",
        f"Corridas {m['run_sessions_7d']}/semana",
    ]
    return "\n".join(linhas)


def format_insights(insights: list) -> str:
    if not insights:
        return "IA indisponível — o veredito do dia segue válido."
    blocos = []
    for ins in insights:
        fontes = " · ".join(
            f"{s['label']} {s.get('valor', '')}{s.get('unidade', '')}".strip()
            for s in ins.get("metricas_usadas", [])
        )
        bloco = f"• {ins['texto']}"
        if fontes:
            bloco += f"\n   fontes: {fontes}"
        blocos.append(bloco)
    return "\n\n".join(blocos)
```

- [ ] **Step 4: Rodar e ver passar**

Run: `pytest tests/bot/test_messages.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add bot/messages.py tests/bot/test_messages.py
git commit -m "feat(bot): formatação de saldo e insights"
```

---

## Task 8: Gráfico semana/mês

**Files:**
- Create: `bot/charts.py`
- Test: `tests/bot/test_charts.py`

`build_trends` devolve `{"period","metrics": {key: {"series": [{"data","valor"}], "trend": {...}}},
"insights": [...]}`. O gráfico plota o trio: `resting_hr`, `sleep_hours`, `body_battery_high`.

- [ ] **Step 1: Teste que falha**

```python
# tests/bot/test_charts.py
import io
from bot.charts import recovery_chart_png

def test_gera_png():
    trends = {"period": 7, "metrics": {
        "resting_hr": {"series": [{"data": "2026-06-10", "valor": 58},
                                   {"data": "2026-06-11", "valor": 55}], "trend": {"direction": "descendo"}},
        "sleep_hours": {"series": [{"data": "2026-06-10", "valor": 6.2},
                                    {"data": "2026-06-11", "valor": 7.1}], "trend": {"direction": "subindo"}},
        "body_battery_high": {"series": [{"data": "2026-06-10", "valor": 70},
                                          {"data": "2026-06-11", "valor": 73}], "trend": {"direction": "estável"}},
    }, "insights": []}
    png = recovery_chart_png(trends, titulo="Semana")
    assert isinstance(png, (bytes, io.BytesIO))
    data = png.getvalue() if isinstance(png, io.BytesIO) else png
    assert data[:8] == b"\x89PNG\r\n\x1a\n"  # assinatura PNG
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/bot/test_charts.py -v`
Expected: FAIL (`ModuleNotFoundError: bot.charts`).

- [ ] **Step 3: Implementar**

```python
# bot/charts.py
import io
import matplotlib
matplotlib.use("Agg")  # backend sem display (servidor)
import matplotlib.pyplot as plt

_PANELS = [
    ("resting_hr", "FC repouso (bpm)"),
    ("sleep_hours", "Sono (h)"),
    ("body_battery_high", "Body Battery"),
]


def recovery_chart_png(trends: dict, titulo: str = "") -> io.BytesIO:
    metrics = trends.get("metrics", {})
    fig, axes = plt.subplots(3, 1, figsize=(7, 6), sharex=False)
    fig.suptitle(titulo)
    for ax, (key, label) in zip(axes, _PANELS):
        serie = (metrics.get(key) or {}).get("series", [])
        ys = [p["valor"] for p in serie if p.get("valor") is not None]
        xs = list(range(len(ys)))
        ax.plot(xs, ys, marker="o", linewidth=1.5)
        ax.set_title(label, loc="left", fontsize=10)
        ax.grid(True, alpha=0.2)
        if not ys:
            ax.text(0.5, 0.5, "sem dados", ha="center", va="center", transform=ax.transAxes)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120)
    plt.close(fig)
    buf.seek(0)
    return buf
```

- [ ] **Step 4: Rodar e ver passar**

Run: `pytest tests/bot/test_charts.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add bot/charts.py tests/bot/test_charts.py
git commit -m "feat(bot): gráfico PNG do trio de recuperação"
```

---

## Task 9: Definições do check-in + teclado inline

**Files:**
- Create: `bot/checkin.py`
- Test: `tests/bot/test_checkin.py`

- [ ] **Step 1: Teste que falha**

```python
# tests/bot/test_checkin.py
from bot.checkin import CHECKINS, scale_keyboard, parse_callback

def test_catalogo_tem_4():
    keys = [c["key"] for c in CHECKINS]
    assert keys == ["hidratacao", "energia", "soreness", "alimentacao"]

def test_keyboard_tem_5_botoes():
    kb = scale_keyboard("energia")
    botoes = kb.inline_keyboard[0]
    assert len(botoes) == 5
    assert botoes[0].callback_data == "ci:energia:1"
    assert botoes[4].callback_data == "ci:energia:5"

def test_parse_callback():
    assert parse_callback("ci:soreness:3") == ("soreness", 3)
    assert parse_callback("lixo") is None
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/bot/test_checkin.py -v`
Expected: FAIL (`ModuleNotFoundError: bot.checkin`).

- [ ] **Step 3: Implementar**

```python
# bot/checkin.py
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

CHECKINS = [
    {"key": "hidratacao", "label": "Hidratação", "low": "desidratado", "high": "bem hidratado"},
    {"key": "energia", "label": "Energia", "low": "esgotado", "high": "cheio de energia"},
    {"key": "soreness", "label": "Dor muscular", "low": "muito dolorido", "high": "sem dor"},
    {"key": "alimentacao", "label": "Alimentação", "low": "mal alimentado", "high": "bem alimentado"},
]
_BY_KEY = {c["key"]: c for c in CHECKINS}


def scale_keyboard(key: str) -> InlineKeyboardMarkup:
    row = [InlineKeyboardButton(str(n), callback_data=f"ci:{key}:{n}") for n in range(1, 6)]
    return InlineKeyboardMarkup([row])


def parse_callback(data: str):
    parts = (data or "").split(":")
    if len(parts) != 3 or parts[0] != "ci":
        return None
    try:
        return parts[1], int(parts[2])
    except ValueError:
        return None


def prompt_text(c: dict) -> str:
    return f"{c['label']}? (1 = {c['low']} · 5 = {c['high']})"
```

- [ ] **Step 4: Rodar e ver passar**

Run: `pytest tests/bot/test_checkin.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add bot/checkin.py tests/bot/test_checkin.py
git commit -m "feat(bot): catálogo de check-in + teclado inline 1-5"
```

---

## Task 10: Camada de domínio do bot (coleta do contexto/saldo)

**Files:**
- Create: `bot/core.py`
- Test: `tests/bot/test_core.py`

Junta o que o job/handler precisa: dado um `client` e `db`, monta `metrics` (4 chaves) e o
`veredito`/`insights` do dia. Reusa `DataProcessor.build_context_summary` (como `api/services.build_today`)
e `DailyAnalysis`.

- [ ] **Step 1: Teste que falha (com client/db mockados)**

```python
# tests/bot/test_core.py
import datetime as dt
from unittest.mock import MagicMock
from bot.core import collect_metrics

def test_collect_metrics_extrai_4_chaves():
    ctx = {"resting_hr_today": 55, "resting_hr_avg_7d": 60.9,
           "morning_battery_avg": 38, "sleep_debt_hours": 2.4, "run_sessions_7d": 3,
           "extra": "ignorado"}
    m = collect_metrics(ctx)
    assert set(m) == {"resting_hr_today", "resting_hr_avg_7d",
                      "morning_battery_avg", "sleep_debt_hours", "run_sessions_7d"}
    assert m["resting_hr_today"] == 55
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/bot/test_core.py -v`
Expected: FAIL (`ModuleNotFoundError: bot.core`).

- [ ] **Step 3: Implementar**

```python
# bot/core.py
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
```

- [ ] **Step 4: Rodar e ver passar**

Run: `pytest tests/bot/test_core.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add bot/core.py tests/bot/test_core.py
git commit -m "feat(bot): core (contexto, métricas-chave, análise do dia)"
```

---

## Task 11: Handlers (comandos + callbacks + guarda de chat)

**Files:**
- Create: `bot/handlers.py`
- Test: `tests/bot/test_handlers.py`

Usa `Application`/`ContextTypes` do python-telegram-bot. Os handlers leem dependências de
`context.bot_data` (`{"cfg": Config, "db": HistoryDB, "client": GarminClient}`). Guarda:
ignora updates cujo chat != `cfg.chat_id`.

- [ ] **Step 1: Teste que falha (guarda + callback de check-in)**

```python
# tests/bot/test_handlers.py
import datetime as dt
import pytest
from unittest.mock import AsyncMock, MagicMock
from src.history_db import HistoryDB
from bot.config import Config
from bot import handlers

def _cfg():
    return Config(token="t", chat_id=99, checkin_hour=21,
                  wake_start=(5, 0), wake_end=(11, 0), wake_poll_minutes=15, db_path=":memory:")

def _ctx(db):
    ctx = MagicMock()
    ctx.bot_data = {"cfg": _cfg(), "db": db, "client": MagicMock()}
    return ctx

@pytest.mark.asyncio
async def test_guarda_ignora_outro_chat():
    update = MagicMock()
    update.effective_chat.id = 1  # != 99
    update.message.reply_text = AsyncMock()
    await handlers.cmd_start(update, _ctx(MagicMock()))
    update.message.reply_text.assert_not_called()

@pytest.mark.asyncio
async def test_callback_checkin_grava(tmp_path):
    db = HistoryDB(db_path=str(tmp_path / "h.db"))
    update = MagicMock()
    update.effective_chat.id = 99
    update.callback_query.data = "ci:energia:4"
    update.callback_query.answer = AsyncMock()
    update.callback_query.edit_message_text = AsyncMock()
    await handlers.on_checkin_button(update, _ctx(db))
    rows = {r["metric_key"]: r["value"] for r in db.get_metrics_for_date(dt.date.today().isoformat())}
    assert rows["energia"] == 4
    update.callback_query.edit_message_text.assert_awaited()
```

> Requer `pytest-asyncio`. Adicione `pytest-asyncio>=0.23` ao `requirements.txt` neste task
> (e `asyncio_mode = auto` em `pytest.ini`), rodando `pip install -r requirements.txt` antes do Step 2.

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/bot/test_handlers.py -v`
Expected: FAIL (`ModuleNotFoundError: bot.handlers`).

- [ ] **Step 3: Implementar**

```python
# bot/handlers.py
import datetime as dt
from telegram import Update
from telegram.ext import ContextTypes

from bot import core, messages
from bot.checkin import CHECKINS, scale_keyboard, parse_callback, prompt_text
from bot.charts import recovery_chart_png
from src.services_core import save_checkin, build_trends


def _authorized(update: Update, context) -> bool:
    cfg = context.bot_data["cfg"]
    chat = update.effective_chat
    return chat is not None and chat.id == cfg.chat_id


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _authorized(update, context):
        return
    await update.message.reply_text(
        "Readiness bot. Comandos:\n"
        "/saldo — saldo do dia\n/insights — leitura da IA\n"
        "/checkin — responder hidratação/energia/dor/alimentação\n"
        "/semana — resumo 7d\n/mes — resumo 30d"
    )


async def cmd_saldo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _authorized(update, context):
        return
    db = context.bot_data["db"]
    client = context.bot_data["client"]
    day = dt.date.today().isoformat()
    try:
        ctx = core.load_context(client)
        analysis = core.daily_analysis(db, day)
        txt = messages.format_saldo(analysis["veredito"], core.collect_metrics(ctx))
    except Exception as e:  # noqa: BLE001
        txt = f"Não consegui montar o saldo agora ({e})."
    await update.message.reply_text(txt)


async def cmd_insights(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _authorized(update, context):
        return
    db = context.bot_data["db"]
    day = dt.date.today().isoformat()
    try:
        analysis = core.daily_analysis(db, day)
        txt = messages.format_insights(analysis["insights"])
    except Exception:  # noqa: BLE001
        txt = messages.format_insights([])
    await update.message.reply_text(txt)


async def cmd_checkin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _authorized(update, context):
        return
    for c in CHECKINS:
        await update.message.reply_text(prompt_text(c), reply_markup=scale_keyboard(c["key"]))


async def on_checkin_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _authorized(update, context):
        return
    q = update.callback_query
    parsed = parse_callback(q.data)
    if not parsed:
        await q.answer("inválido")
        return
    key, val = parsed
    save_checkin(context.bot_data["db"], {key: val})
    label = next((c["label"] for c in CHECKINS if c["key"] == key), key)
    await q.answer("anotado")
    await q.edit_message_text(f"{label}: {val} ✓")


async def _send_trends(update, context, period: int, titulo: str):
    db = context.bot_data["db"]
    trends = build_trends(db, period=period)
    png = recovery_chart_png(trends, titulo=titulo)
    legenda = messages.format_insights(
        [{"texto": t, "metricas_usadas": []} for t in trends.get("insights", [])]
    )
    await update.message.reply_photo(photo=png, caption=legenda[:1024] or titulo)


async def cmd_semana(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _authorized(update, context):
        return
    await _send_trends(update, context, 7, "Semana")


async def cmd_mes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _authorized(update, context):
        return
    await _send_trends(update, context, 30, "Mês")
```

Crie `pytest.ini` (se não existir):
```ini
[pytest]
asyncio_mode = auto
```
E adicione `pytest-asyncio>=0.23` ao `requirements.txt`; rode `pip install -r requirements.txt`.

- [ ] **Step 4: Rodar e ver passar**

Run: `pytest tests/bot/test_handlers.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add bot/handlers.py pytest.ini requirements.txt tests/bot/test_handlers.py
git commit -m "feat(bot): handlers de comandos + callback de check-in + guarda de chat"
```

---

## Task 12: Jobs (saldo matinal + check-in 21h)

**Files:**
- Create: `bot/jobs.py`
- Test: `tests/bot/test_jobs.py`

- [ ] **Step 1: Teste que falha (job_wake respeita dedup e janela)**

```python
# tests/bot/test_jobs.py
import datetime as dt
import pytest
from unittest.mock import AsyncMock, MagicMock
from src.history_db import HistoryDB
from bot.config import Config
from bot import jobs

def _cfg():
    return Config(token="t", chat_id=99, checkin_hour=21,
                  wake_start=(5, 0), wake_end=(11, 0), wake_poll_minutes=15, db_path=":memory:")

def _job_ctx(db, client):
    ctx = MagicMock()
    ctx.bot_data = {"cfg": _cfg(), "db": db, "client": client}
    ctx.bot.send_message = AsyncMock()
    return ctx

@pytest.mark.asyncio
async def test_job_wake_envia_uma_vez(tmp_path, monkeypatch):
    db = HistoryDB(db_path=str(tmp_path / "h.db"))
    client = MagicMock()
    client.get_sleep_day.return_value = {"dailySleepDTO": {"sleepEndTimestampLocal": 1781503920000}}
    # mocka coleta/análise pra não bater em rede
    monkeypatch.setattr(jobs.core, "load_context", lambda c: {
        "resting_hr_today": 55, "resting_hr_avg_7d": 60.9, "morning_battery_avg": 38,
        "sleep_debt_hours": 2.4, "run_sessions_7d": 3})
    monkeypatch.setattr(jobs.core, "daily_analysis", lambda db, day, force=False: {
        "veredito": {"status": "amarelo", "motivo": "x", "recomendacao": "y"}, "insights": []})
    monkeypatch.setattr(jobs, "Ingestor", lambda c, d: MagicMock(sync_today=lambda: None))

    ctx = _job_ctx(db, client)
    await jobs.job_wake(ctx)
    assert ctx.bot.send_message.await_count == 1
    # segunda vez no mesmo dia: não reenvia
    await jobs.job_wake(ctx)
    assert ctx.bot.send_message.await_count == 1
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/bot/test_jobs.py -v`
Expected: FAIL (`ModuleNotFoundError: bot.jobs`).

- [ ] **Step 3: Implementar**

```python
# bot/jobs.py
import datetime as dt
from telegram.ext import ContextTypes

from bot import core, messages
from bot.state import already_sent_saldo, mark_saldo_sent, already_prompted_checkin, mark_checkin_prompted
from bot.wake_detector import wake_time_local
from bot.checkin import CHECKINS, scale_keyboard, prompt_text
from src.ingestor import Ingestor


async def _send_saldo(context, day, wake):
    cfg = context.bot_data["cfg"]
    db = context.bot_data["db"]
    client = context.bot_data["client"]
    try:
        Ingestor(client, db).sync_today()
    except Exception:  # noqa: BLE001 — sem sync ainda dá pra mandar do cache
        pass
    ctx = core.load_context(client)
    analysis = core.daily_analysis(db, day)
    txt = messages.format_saldo(analysis["veredito"], core.collect_metrics(ctx), wake=wake)
    await context.bot.send_message(chat_id=cfg.chat_id, text=txt)
    mark_saldo_sent(db, day)


async def job_wake(context: ContextTypes.DEFAULT_TYPE):
    """Roda a cada N min na janela matinal. Envia o saldo 1x ao detectar acordar."""
    cfg = context.bot_data["cfg"]
    db = context.bot_data["db"]
    client = context.bot_data["client"]
    day = dt.date.today().isoformat()
    if already_sent_saldo(db, day):
        return
    try:
        sleep_day = client.get_sleep_day(day)
    except Exception:  # noqa: BLE001
        sleep_day = None
    wake = wake_time_local(sleep_day)
    now = dt.datetime.now().time()
    end = dt.time(*cfg.wake_end)
    if wake:
        await _send_saldo(context, day, wake)
    elif now >= end:  # fallback: fim da janela, manda com o que tiver
        await _send_saldo(context, day, None)


async def job_checkin(context: ContextTypes.DEFAULT_TYPE):
    cfg = context.bot_data["cfg"]
    db = context.bot_data["db"]
    day = dt.date.today().isoformat()
    if already_prompted_checkin(db, day):
        return
    for c in CHECKINS:
        await context.bot.send_message(
            chat_id=cfg.chat_id, text=prompt_text(c), reply_markup=scale_keyboard(c["key"])
        )
    mark_checkin_prompted(db, day)
```

- [ ] **Step 4: Rodar e ver passar**

Run: `pytest tests/bot/test_jobs.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add bot/jobs.py tests/bot/test_jobs.py
git commit -m "feat(bot): jobs de saldo matinal (wake) e check-in 21h"
```

---

## Task 13: main.py — montar Application, registrar handlers + jobs

**Files:**
- Create: `bot/main.py`
- Test: manual (subir o bot) — sem teste automatizado (wiring de runtime).

- [ ] **Step 1: Implementar**

```python
# bot/main.py
import datetime as dt
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
)

from bot.config import Config
from bot import handlers, jobs
from src.history_db import HistoryDB
from src.garmin_client import GarminClient


def build_app() -> Application:
    cfg = Config.from_env()
    app = Application.builder().token(cfg.token).build()
    app.bot_data["cfg"] = cfg
    app.bot_data["db"] = HistoryDB(db_path=cfg.db_path)
    app.bot_data["client"] = GarminClient()

    app.add_handler(CommandHandler("start", handlers.cmd_start))
    app.add_handler(CommandHandler("saldo", handlers.cmd_saldo))
    app.add_handler(CommandHandler("insights", handlers.cmd_insights))
    app.add_handler(CommandHandler("checkin", handlers.cmd_checkin))
    app.add_handler(CommandHandler("semana", handlers.cmd_semana))
    app.add_handler(CommandHandler("mes", handlers.cmd_mes))
    app.add_handler(CallbackQueryHandler(handlers.on_checkin_button, pattern=r"^ci:"))

    jq = app.job_queue
    jq.run_repeating(
        jobs.job_wake,
        interval=cfg.wake_poll_minutes * 60,
        first=10,
    )
    jq.run_daily(
        jobs.job_checkin,
        time=dt.time(hour=cfg.checkin_hour, minute=0),
    )
    return app


def main():
    app = build_app()
    app.run_polling()


if __name__ == "__main__":
    main()
```

> `job_wake` roda o tempo todo mas sai cedo fora da janela (dedup + checagem de horário no
> próprio job; a guarda de janela inferior pode ser adicionada checando `now >= wake_start`
> antes de consultar o Garmin — opcional, economiza chamadas).

- [ ] **Step 2: Smoke manual**

Run (com `.env` preenchido): `python -m bot.main`
Expected: loga "Application started"; manda `/start` no chat e recebe a ajuda.

- [ ] **Step 3: Commit**

```bash
git add bot/main.py
git commit -m "feat(bot): main — Application, handlers e jobs"
```

---

## Task 14: Otimizar janela matinal (evita chamar Garmin fora do horário)

**Files:**
- Modify: `bot/jobs.py:job_wake`
- Test: `tests/bot/test_jobs.py` (adiciona caso)

- [ ] **Step 1: Teste que falha**

```python
# acrescente em tests/bot/test_jobs.py
@pytest.mark.asyncio
async def test_job_wake_nao_consulta_fora_da_janela(tmp_path, monkeypatch):
    db = HistoryDB(db_path=str(tmp_path / "h.db"))
    client = MagicMock()
    ctx = _job_ctx(db, client)
    # força "agora" antes da janela (04:00)
    monkeypatch.setattr(jobs, "_now_time", lambda: dt.time(4, 0))
    await jobs.job_wake(ctx)
    client.get_sleep_day.assert_not_called()
    ctx.bot.send_message.assert_not_awaited()
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/bot/test_jobs.py::test_job_wake_nao_consulta_fora_da_janela -v`
Expected: FAIL (sem `_now_time`; ou `get_sleep_day` foi chamado).

- [ ] **Step 3: Implementar**

Em `bot/jobs.py`, adicione helper e use no início de `job_wake`:
```python
def _now_time():
    return dt.datetime.now().time()
```
No começo de `job_wake`, após calcular `day` e o dedup:
```python
    start = dt.time(*cfg.wake_start)
    end = dt.time(*cfg.wake_end)
    now = _now_time()
    if now < start or now > end:
        return
```
E troque o `now = dt.datetime.now().time()` interno por reuso de `now`/`_now_time()`.

- [ ] **Step 4: Rodar e ver passar (suíte do módulo)**

Run: `pytest tests/bot/test_jobs.py -v`
Expected: PASS (todos).

- [ ] **Step 5: Commit**

```bash
git add bot/jobs.py tests/bot/test_jobs.py
git commit -m "perf(bot): job_wake só consulta Garmin dentro da janela matinal"
```

---

## Task 15: Deploy — systemd + dev launcher + .env.example

**Files:**
- Create: `deploy/readiness-bot.service`, `iniciar_bot.bat`, `.env.example`

- [ ] **Step 1: Unit systemd**

`deploy/readiness-bot.service`:
```ini
[Unit]
Description=Readiness Telegram Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/readiness
Environment=TZ=America/Sao_Paulo
EnvironmentFile=/home/ubuntu/readiness/.env
ExecStart=/home/ubuntu/readiness/.venv/bin/python -m bot.main
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 2: Dev launcher (Windows)**

`iniciar_bot.bat`:
```bat
@echo off
cd /d %~dp0
python -m bot.main
```

- [ ] **Step 3: .env.example**

```
TELEGRAM_TOKEN=
TELEGRAM_CHAT_ID=
GARMIN_EMAIL=
GARMIN_PASSWORD=
ANTHROPIC_API_KEY=
TZ=America/Sao_Paulo
WAKE_WINDOW_START=05:00
WAKE_WINDOW_END=11:00
WAKE_POLL_MINUTES=15
CHECKIN_HOUR=21
DB_PATH=history.db
```

- [ ] **Step 4: Commit**

```bash
git add deploy/readiness-bot.service iniciar_bot.bat .env.example
git commit -m "chore(deploy): systemd unit + dev launcher + .env.example"
```

> Provisionamento da VM Oracle (manual, documentado no commit ou README):
> instalar Python, `git clone`, `python -m venv .venv`, `pip install -r requirements.txt`,
> preencher `.env`, `cp deploy/readiness-bot.service /etc/systemd/system/`,
> `systemctl enable --now readiness-bot`. Primeiro login Garmin gera o token garth (persistido
> no home da VM).

---

## Task 16: Arquivar front-end + podar do master

**Files:**
- Delete: `web/`
- Modify: `api/main.py` (remove mount de SPA)

- [ ] **Step 1: Salvar o front numa branch**

```bash
git branch legacy/frontend
git push -u origin legacy/frontend
```
Expected: branch `legacy/frontend` preservando todo o front atual.

- [ ] **Step 2: Remover o mount de SPA**

Em `api/main.py`, remova o bloco final:
```python
# Serve build React em prod, se existir ...
_dist = Path("web/dist")
if _dist.exists():
    app.mount("/", StaticFiles(directory=str(_dist), html=True), name="static")
```
(e o import `from fastapi.staticfiles import StaticFiles` se ficar sem uso).

- [ ] **Step 3: Remover o front**

```bash
git rm -r web
```

- [ ] **Step 4: Garantir suíte verde sem o front**

Run: `pytest -q`
Expected: PASS (backend intacto; `api/services` re-exporta de `services_core`).

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "chore: arquiva front-end em legacy/frontend e remove do master (pivot p/ bot)"
```

---

## Self-Review (cobertura da spec)

- Saldo matinal por wake → Tasks 5, 10, 12, 13. ✓
- `/saldo` `/insights` `/checkin` `/start` → Task 11. ✓
- Check-in 21h + botões 1–5 → Tasks 9, 11, 12. ✓
- `/semana` `/mes` + gráfico → Tasks 8, 11. ✓
- Dedup/estado → Tasks 2, 6, 12. ✓
- Erros graciosos (Garmin/IA) → Tasks 11 (`try`), 12 (`try` no sync). ✓
- Guarda de chat único → Task 11. ✓
- Config/env → Tasks 4, 15. ✓
- Deploy Oracle/systemd, SQLite persistente → Task 15. ✓
- Arquivar front + cortar planos → Task 16 (planos: simplesmente não usados pelo bot). ✓
- LLM segue Anthropic → reuso de `DailyAnalysis`/`InsightEngine` sem mudança. ✓

Sem placeholders; nomes consistentes (`ci:<key>:<n>`, chaves de métrica, `bot_data`).
