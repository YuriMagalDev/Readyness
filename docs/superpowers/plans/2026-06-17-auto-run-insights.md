# Insight automático de corrida + /atividades — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Detectar corrida nova no Garmin (polling 15min), mandar insight no Telegram, e expor `/atividades` pra pedir insight de uma corrida recente sob demanda.

**Architecture:** Job recorrente puxa atividades recentes, filtra corridas (running/treadmill/trail, exclui indoor_cardio), dedup por `notified_activity`, e usa o `InsightEngine.activity_insight` que já existe. `/atividades` lista corridas com botões inline e reusa o mesmo motor. Tudo single-user, com guarda de `chat_id`.

**Tech Stack:** python-telegram-bot v22, SQLite (history.db), garminconnect, Anthropic via InsightEngine. pytest (asyncio_mode=auto).

---

### Task 1: `bot/runs.py` — filtro de corridas

**Files:**
- Create: `bot/runs.py`
- Test: `tests/bot/test_runs.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/bot/test_runs.py
from bot.runs import RUN_TYPES, is_run, filter_runs

def test_run_types_sao_os_tres():
    assert RUN_TYPES == {"running", "treadmill_running", "trail_running"}

def test_is_run_aceita_raw_garmin_e_db_row():
    assert is_run({"activityType": {"typeKey": "running"}})        # raw garmin
    assert is_run({"type": "treadmill_running"})                   # db row
    assert is_run({"type": "trail_running"})

def test_is_run_recusa_musculacao_e_cardio():
    assert not is_run({"type": "indoor_cardio"})                   # musculação
    assert not is_run({"activityType": {"typeKey": "strength_training"}})
    assert not is_run({"type": "lap_swimming"})
    assert not is_run({})

def test_filter_runs_preserva_ordem_e_so_corridas():
    acts = [
        {"activityId": 1, "type": "running"},
        {"activityId": 2, "type": "indoor_cardio"},
        {"activityId": 3, "activityType": {"typeKey": "trail_running"}},
    ]
    out = filter_runs(acts)
    assert [a.get("activityId") for a in out] == [1, 3]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/bot/test_runs.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'bot.runs'`

- [ ] **Step 3: Write minimal implementation**

```python
# bot/runs.py
RUN_TYPES = {"running", "treadmill_running", "trail_running"}


def _type_of(act: dict) -> str:
    """typeKey, aceitando tanto o raw do Garmin quanto a row do DB (snake_case)."""
    return act.get("type") or (act.get("activityType") or {}).get("typeKey") or ""


def is_run(act: dict) -> bool:
    return _type_of(act) in RUN_TYPES


def filter_runs(activities: list) -> list:
    """Só corridas, preservando a ordem de entrada (Garmin já vem da mais recente)."""
    return [a for a in (activities or []) if is_run(a)]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/bot/test_runs.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add bot/runs.py tests/bot/test_runs.py
git commit -m "feat(bot): filtro de corridas (is_run/filter_runs)"
```

---

### Task 2: `history_db` — dedup de atividades notificadas

**Files:**
- Modify: `src/history_db.py` (adiciona tabela `notified_activity` no `_init_db` + métodos)
- Test: `tests/test_history_db_notified.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_history_db_notified.py
from src.history_db import HistoryDB

def test_is_notified_falso_ate_marcar(tmp_path):
    db = HistoryDB(db_path=str(tmp_path / "h.db"))
    assert db.is_notified(111) is False
    db.mark_notified(111)
    assert db.is_notified(111) is True

def test_mark_notified_idempotente(tmp_path):
    db = HistoryDB(db_path=str(tmp_path / "h.db"))
    db.mark_notified(222)
    db.mark_notified(222)  # PK evita duplicar / não pode lançar
    assert db.is_notified(222) is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_history_db_notified.py -v`
Expected: FAIL — `AttributeError: 'HistoryDB' object has no attribute 'is_notified'`

- [ ] **Step 3: Write minimal implementation**

No `_init_db`, logo após o bloco que cria `bot_state` (`src/history_db.py:71-74`), adicionar:

```python
            conn.execute(
                "CREATE TABLE IF NOT EXISTS notified_activity ("
                "activity_id INTEGER PRIMARY KEY, sent_at TEXT)"
            )
```

E adicionar os métodos na classe (perto de `get_activity`, `src/history_db.py:121`):

```python
    def is_notified(self, activity_id: int) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM notified_activity WHERE activity_id = ?", (activity_id,)
            ).fetchone()
        return row is not None

    def mark_notified(self, activity_id: int):
        import datetime as _dt
        with self._connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO notified_activity (activity_id, sent_at) VALUES (?, ?)",
                (activity_id, _dt.datetime.now().isoformat(timespec="seconds")),
            )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_history_db_notified.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/history_db.py tests/test_history_db_notified.py
git commit -m "feat(db): tabela notified_activity + is_notified/mark_notified"
```

---

### Task 3: `services_core.build_run_detail` (fonte única do detalhe)

**Files:**
- Modify: `src/services_core.py` (nova função + imports)
- Modify: `api/services.py` (`build_activity_detail` delega pra cá)
- Test: `tests/test_build_run_detail.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_build_run_detail.py
import json
from unittest.mock import MagicMock
from src.history_db import HistoryDB
from src.services_core import build_run_detail

def _db(tmp_path):
    db = HistoryDB(db_path=str(tmp_path / "h.db"))
    db.upsert_activity({"activity_id": 9, "date": "2026-06-17", "name": "Corrida",
                        "type": "running", "is_strength": 0, "distance_m": 5000})
    return db

def test_usa_splits_do_cache_sem_chamar_garmin(tmp_path, monkeypatch):
    db = _db(tmp_path)
    # injeta splits_json no row
    row = db.get_activity(9); row["splits_json"] = json.dumps([{"km": 1}]); db.upsert_activity(row)
    client = MagicMock()
    monkeypatch.setattr("src.services_core.InsightEngine",
                        lambda db: MagicMock(activity_insight=lambda a, s, force=False: "ok"))
    out = build_run_detail(db, client, 9)
    assert out["splits"] == [{"km": 1}]
    assert out["insight"] == "ok"
    client.get_activity_splits.assert_not_called()   # veio do cache

def test_busca_splits_no_garmin_quando_falta(tmp_path, monkeypatch):
    db = _db(tmp_path)
    client = MagicMock()
    client.get_activity_splits.return_value = {"raw": True}
    monkeypatch.setattr("src.services_core.splits_from_garmin", lambda raw: [{"km": 2}])
    monkeypatch.setattr("src.services_core.InsightEngine",
                        lambda db: MagicMock(activity_insight=lambda a, s, force=False: "ins"))
    out = build_run_detail(db, client, 9)
    assert out["splits"] == [{"km": 2}]
    client.get_activity_splits.assert_called_once_with(9)
    # persistiu o splits_json
    assert json.loads(db.get_activity(9)["splits_json"]) == [{"km": 2}]

def test_atividade_inexistente_lanca(tmp_path):
    db = HistoryDB(db_path=str(tmp_path / "h.db"))
    import pytest
    with pytest.raises(ValueError):
        build_run_detail(db, MagicMock(), 404)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_build_run_detail.py -v`
Expected: FAIL — `ImportError: cannot import name 'build_run_detail'`

- [ ] **Step 3: Write minimal implementation**

Topo de `src/services_core.py`, junto dos imports existentes (`from src.insight_engine import InsightEngine` já existe):

```python
import json as _json
from src.extractors import splits_from_garmin
```

Adicionar a função:

```python
def build_run_detail(db, client, activity_id: int) -> dict:
    """Detalhe de uma corrida: splits (cache ou Garmin) + insight da IA. Fonte única."""
    act = db.get_activity(activity_id)
    if act is None:
        raise ValueError(f"Atividade {activity_id} não encontrada")
    if act.get("splits_json"):
        splits = _json.loads(act["splits_json"])
    else:
        splits = splits_from_garmin(client.get_activity_splits(activity_id))
        act["splits_json"] = _json.dumps(splits)
        db.upsert_activity(act)
    insight = InsightEngine(db=db).activity_insight(act, splits)
    return {"activity": act, "splits": splits, "insight": insight}
```

Em `api/services.py`, trocar o corpo de `build_activity_detail` (linhas 214-226) por delegação. Garantir o import no topo de `api/services.py`:

```python
from src.services_core import build_run_detail
```

E o corpo:

```python
def build_activity_detail(db, client, activity_id: int) -> dict:
    return build_run_detail(db, client, activity_id)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_build_run_detail.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Run a suíte de services pra garantir que a delegação não quebrou**

Run: `python -m pytest tests/ -k "service or activity_detail" -q`
Expected: PASS (sem erros de import/contrato)

- [ ] **Step 6: Commit**

```bash
git add src/services_core.py api/services.py tests/test_build_run_detail.py
git commit -m "refactor(services): build_run_detail como fonte unica do detalhe de corrida"
```

---

### Task 4: `messages.format_activity`

**Files:**
- Modify: `bot/messages.py` (helpers `_fmt_clock`, `_fmt_pace` + `format_activity`)
- Test: `tests/bot/test_messages_activity.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/bot/test_messages_activity.py
from bot import messages

def test_format_activity_cabecalho_e_insight():
    act = {"name": "Corrida matinal", "distance_m": 5230, "duration_min": 28.5,
           "pace_min_km": 5.45, "avg_hr": 152.3}
    txt = messages.format_activity(act, "Ritmo firme, FC controlada.")
    assert "<b>Corrida matinal</b>" in txt
    assert "5.23 km" in txt
    assert "28:30" in txt          # 28.5 min -> 28:30
    assert "5:27 /km" in txt       # 5.45 min/km -> 5:27
    assert "152 bpm" in txt
    assert "Ritmo firme" in txt

def test_format_activity_tolera_none():
    act = {"name": None, "distance_m": None, "duration_min": None,
           "pace_min_km": None, "avg_hr": None}
    txt = messages.format_activity(act, "ok")
    assert "—" in txt              # campos ausentes viram em-dash
    assert "ok" in txt             # insight ainda sai
    assert "Corrida" in txt        # nome default
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/bot/test_messages_activity.py -v`
Expected: FAIL — `AttributeError: module 'bot.messages' has no attribute 'format_activity'`

- [ ] **Step 3: Write minimal implementation**

Adicionar ao final de `bot/messages.py`:

```python
def _fmt_clock(minutes) -> str:
    """Minutos decimais -> 'M:SS' ou 'H:MM:SS'. None -> '—'."""
    if minutes is None:
        return "—"
    total = round(minutes * 60)
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def _fmt_pace(min_per_km) -> str:
    """Min/km decimal -> 'M:SS'. None -> '—'."""
    if min_per_km is None:
        return "—"
    total = round(min_per_km * 60)
    return f"{total // 60}:{total % 60:02d}"


def format_activity(activity: dict, insight: str) -> str:
    """Cabeçalho (nome · distância · tempo · pace · FC) + insight da IA. HTML."""
    nome = _e(activity.get("name") or "Corrida")
    dist = activity.get("distance_m")
    km = f"{dist / 1000:.2f} km" if dist else "—"
    tempo = _fmt_clock(activity.get("duration_min"))
    pace = activity.get("pace_min_km")
    pace_s = f"{_fmt_pace(pace)} /km" if pace else "—"
    hr = activity.get("avg_hr")
    hr_s = f"{round(hr)} bpm" if hr else "—"
    head = f"🏃 <b>{nome}</b>\n{km} · {tempo} · {pace_s} · ❤️ {hr_s}"
    return f"{head}\n{_RULE}\n{_e(insight)}"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/bot/test_messages_activity.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add bot/messages.py tests/bot/test_messages_activity.py
git commit -m "feat(bot): format_activity (cabecalho + insight de corrida)"
```

---

### Task 5: `jobs.job_runs` — detecção + seed + envio

**Files:**
- Modify: `bot/jobs.py` (imports + `job_runs`)
- Test: `tests/bot/test_job_runs.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/bot/test_job_runs.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from src.history_db import HistoryDB
from bot.config import Config
from bot import jobs

def _cfg():
    return Config(token="t", chat_id=99, checkin_hour=21,
                  morning_slots=((9, 30),), db_path=":memory:")

def _ctx(db, client):
    ctx = MagicMock()
    ctx.bot_data = {"cfg": _cfg(), "db": db, "client": client}
    ctx.bot.send_message = AsyncMock()
    return ctx

def _raw_run(aid):
    return {"activityId": aid, "activityName": "Corrida", "startTimeLocal": "2026-06-17 07:00:00",
            "activityType": {"typeKey": "running"}, "distance": 5000, "duration": 1700,
            "averageSpeed": 3.0, "averageHR": 150}

@pytest.fixture(autouse=True)
def _stub_detail(monkeypatch):
    monkeypatch.setattr(jobs, "build_run_detail",
                        lambda db, client, aid: {"activity": {"name": "Corrida"}, "splits": [], "insight": "ok"})

@pytest.mark.asyncio
async def test_primeiro_ciclo_seeda_sem_enviar(tmp_path):
    db = HistoryDB(db_path=str(tmp_path / "h.db"))
    client = MagicMock(); client.get_activities.return_value = [_raw_run(1), _raw_run(2)]
    ctx = _ctx(db, client)
    await jobs.job_runs(ctx)
    ctx.bot.send_message.assert_not_awaited()       # seed: nada enviado
    assert db.is_notified(1) and db.is_notified(2)  # mas marcadas

@pytest.mark.asyncio
async def test_corrida_nova_apos_seed_envia_uma_vez(tmp_path):
    db = HistoryDB(db_path=str(tmp_path / "h.db"))
    client = MagicMock()
    client.get_activities.return_value = [_raw_run(1)]
    ctx = _ctx(db, client)
    await jobs.job_runs(ctx)                          # seed com a corrida 1
    client.get_activities.return_value = [_raw_run(2), _raw_run(1)]  # 2 é nova
    await jobs.job_runs(ctx)
    assert ctx.bot.send_message.await_count == 1
    assert db.is_notified(2)
    await jobs.job_runs(ctx)                          # não reenvia
    assert ctx.bot.send_message.await_count == 1

@pytest.mark.asyncio
async def test_musculacao_nunca_dispara(tmp_path):
    db = HistoryDB(db_path=str(tmp_path / "h.db"))
    client = MagicMock()
    client.get_activities.return_value = []           # seed vazio
    ctx = _ctx(db, client)
    await jobs.job_runs(ctx)
    musc = {"activityId": 7, "activityType": {"typeKey": "indoor_cardio"},
            "startTimeLocal": "2026-06-17 18:00:00"}
    client.get_activities.return_value = [musc]
    await jobs.job_runs(ctx)
    ctx.bot.send_message.assert_not_awaited()
    assert db.is_notified(7) is False

@pytest.mark.asyncio
async def test_garmin_falha_nao_quebra(tmp_path):
    db = HistoryDB(db_path=str(tmp_path / "h.db"))
    client = MagicMock(); client.get_activities.side_effect = RuntimeError("429")
    ctx = _ctx(db, client)
    await jobs.job_runs(ctx)                           # não pode propagar
    ctx.bot.send_message.assert_not_awaited()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/bot/test_job_runs.py -v`
Expected: FAIL — `AttributeError: module 'bot.jobs' has no attribute 'job_runs'`

- [ ] **Step 3: Write minimal implementation**

No topo de `bot/jobs.py`, somar aos imports existentes:

```python
from bot.runs import filter_runs
from bot.state import already_sent_saldo  # já importado; manter
from src.services_core import build_run_detail
from src.extractors import activity_from_garmin
from bot import messages
```

(`messages` já está importado no arquivo — não duplicar. Adicionar só `filter_runs`, `build_run_detail`, `activity_from_garmin`.)

Adicionar a função:

```python
_RUNS_SEEDED = "runs_seeded"


async def job_runs(context: ContextTypes.DEFAULT_TYPE):
    """A cada 15min: detecta corrida nova no Garmin e manda o insight. 1ª passada seeda
    o histórico (marca como visto sem enviar) pra não spammar corridas antigas no deploy."""
    cfg = context.bot_data["cfg"]
    db = context.bot_data["db"]
    client = context.bot_data["client"]
    try:
        runs = filter_runs(client.get_activities(2))  # ~últimas 48h
    except Exception:  # noqa: BLE001 — Garmin 429/fora: tenta no próximo ciclo
        return
    seeded = db.get_state(_RUNS_SEEDED) == "1"
    for raw in runs:
        aid = raw.get("activityId")
        if aid is None or db.is_notified(aid):
            continue
        if not seeded:
            db.mark_notified(aid)          # seed silencioso
            continue
        db.upsert_activity(activity_from_garmin(raw))  # garante row pro build_run_detail
        try:
            detail = build_run_detail(db, client, aid)
        except Exception:  # noqa: BLE001 — splits/IA falhou: tenta depois, não marca
            continue
        await context.bot.send_message(
            chat_id=cfg.chat_id, text=messages.format_activity(detail["activity"], detail["insight"]),
            parse_mode=messages.PARSE_MODE,
        )
        db.mark_notified(aid)
    if not seeded:
        db.set_state(_RUNS_SEEDED, "1")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/bot/test_job_runs.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add bot/jobs.py tests/bot/test_job_runs.py
git commit -m "feat(bot): job_runs detecta corrida nova e manda insight (com seed anti-spam)"
```

---

### Task 6: `/atividades` + botão de insight

**Files:**
- Modify: `bot/handlers.py` (imports + `cmd_atividades` + `on_activity_button`)
- Test: `tests/bot/test_handlers_atividades.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/bot/test_handlers_atividades.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from src.history_db import HistoryDB
from bot.config import Config
from bot import handlers

def _cfg():
    return Config(token="t", chat_id=99, checkin_hour=21,
                  morning_slots=((9, 30),), db_path=":memory:")

def _ctx(db, client):
    ctx = MagicMock()
    ctx.bot_data = {"cfg": _cfg(), "db": db, "client": client}
    return ctx

def _raw_run(aid, nome):
    return {"activityId": aid, "activityName": nome, "startTimeLocal": "2026-06-17 07:00:00",
            "activityType": {"typeKey": "running"}, "distance": 5000, "duration": 1700,
            "averageSpeed": 3.0, "averageHR": 150}

@pytest.mark.asyncio
async def test_atividades_monta_teclado_so_corridas(tmp_path):
    db = HistoryDB(db_path=str(tmp_path / "h.db"))
    client = MagicMock()
    client.get_activities.return_value = [
        _raw_run(1, "Corrida A"),
        {"activityId": 2, "activityType": {"typeKey": "indoor_cardio"},
         "startTimeLocal": "2026-06-17 18:00:00", "activityName": "Musc"},
    ]
    update = MagicMock(); update.effective_chat.id = 99
    update.message.reply_text = AsyncMock()
    await handlers.cmd_atividades(update, _ctx(db, client))
    kb = update.message.reply_text.await_args.kwargs["reply_markup"]
    botoes = [b for linha in kb.inline_keyboard for b in linha]
    assert len(botoes) == 1                          # só a corrida
    assert botoes[0].callback_data == "act:1"

@pytest.mark.asyncio
async def test_atividades_vazio_avisa(tmp_path):
    db = HistoryDB(db_path=str(tmp_path / "h.db"))
    client = MagicMock(); client.get_activities.return_value = []
    update = MagicMock(); update.effective_chat.id = 99
    update.message.reply_text = AsyncMock()
    await handlers.cmd_atividades(update, _ctx(db, client))
    assert "Nenhuma corrida" in update.message.reply_text.await_args.args[0]

@pytest.mark.asyncio
async def test_botao_atividade_responde_insight(tmp_path, monkeypatch):
    db = HistoryDB(db_path=str(tmp_path / "h.db"))
    monkeypatch.setattr(handlers, "build_run_detail",
                        lambda db, client, aid: {"activity": {"name": "Corrida A", "distance_m": 5000,
                        "duration_min": 28.0, "pace_min_km": 5.5, "avg_hr": 150}, "splits": [], "insight": "ok"})
    update = MagicMock(); update.effective_chat.id = 99
    update.callback_query.data = "act:1"
    update.callback_query.answer = AsyncMock()
    update.callback_query.edit_message_text = AsyncMock()
    await handlers.on_activity_button(update, _ctx(db, MagicMock()))
    update.callback_query.edit_message_text.assert_awaited()
    enviado = update.callback_query.edit_message_text.await_args.args[0]
    assert "Corrida A" in enviado and "ok" in enviado

@pytest.mark.asyncio
async def test_botao_chat_alheio_ignora(tmp_path):
    db = HistoryDB(db_path=str(tmp_path / "h.db"))
    update = MagicMock(); update.effective_chat.id = 1   # não autorizado
    update.callback_query.answer = AsyncMock()
    update.callback_query.edit_message_text = AsyncMock()
    await handlers.on_activity_button(update, _ctx(db, MagicMock()))
    update.callback_query.edit_message_text.assert_not_awaited()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/bot/test_handlers_atividades.py -v`
Expected: FAIL — `AttributeError: module 'bot.handlers' has no attribute 'cmd_atividades'`

- [ ] **Step 3: Write minimal implementation**

No topo de `bot/handlers.py`, somar aos imports:

```python
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from bot.runs import filter_runs
from src.services_core import build_run_detail
```

Adicionar os handlers:

```python
def _run_button_label(raw: dict) -> str:
    data = (raw.get("startTimeLocal") or "")[:10]
    nome = raw.get("activityName") or "Corrida"
    dist = raw.get("distance")
    km = f"{dist / 1000:.1f}km" if dist else "—"
    return f"{data} · {nome} · {km}"


async def cmd_atividades(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _authorized(update, context):
        return
    client = context.bot_data["client"]
    try:
        runs = filter_runs(client.get_activities(7))[:8]   # últimas 8 corridas
    except Exception:  # noqa: BLE001
        await update.message.reply_text("Não consegui buscar suas atividades agora.")
        return
    if not runs:
        await update.message.reply_text("Nenhuma corrida recente encontrada.")
        return
    teclado = [
        [InlineKeyboardButton(_run_button_label(r), callback_data=f"act:{r['activityId']}")]
        for r in runs
    ]
    await update.message.reply_text(
        "Escolha uma corrida pra ver o insight:", reply_markup=InlineKeyboardMarkup(teclado)
    )


async def on_activity_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _authorized(update, context):
        return
    q = update.callback_query
    await q.answer()
    try:
        aid = int(q.data.split(":", 1)[1])
    except (ValueError, IndexError):
        await q.edit_message_text("Atividade inválida.")
        return
    db = context.bot_data["db"]
    client = context.bot_data["client"]
    try:
        detail = build_run_detail(db, client, aid)
    except Exception:  # noqa: BLE001
        await q.edit_message_text("Não consegui analisar essa corrida agora.")
        return
    await q.edit_message_text(
        messages.format_activity(detail["activity"], detail["insight"]),
        parse_mode=messages.PARSE_MODE,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/bot/test_handlers_atividades.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add bot/handlers.py tests/bot/test_handlers_atividades.py
git commit -m "feat(bot): /atividades lista corridas + botao de insight sob demanda"
```

---

### Task 7: Ligar no `main.py` (handlers + job 15min)

**Files:**
- Modify: `bot/main.py`
- Test: `tests/bot/test_main_wiring.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/bot/test_main_wiring.py
import os
from unittest.mock import patch, MagicMock

def test_build_app_registra_atividades_e_job_runs(monkeypatch):
    monkeypatch.setenv("TELEGRAM_TOKEN", "tok")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "99")
    monkeypatch.setenv("DB_PATH", ":memory:")
    with patch("bot.main.GarminClient", return_value=MagicMock()):
        from bot.main import build_app
        app = build_app()
    # comando /atividades registrado
    cmds = set()
    for grupo in app.handlers.values():
        for h in grupo:
            cmds |= set(getattr(h, "commands", []) or [])
    assert "atividades" in cmds
    # job_runs agendado (run_repeating)
    nomes = {j.name for j in app.job_queue.jobs()}
    assert any("job_runs" in n for n in nomes)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/bot/test_main_wiring.py -v`
Expected: FAIL — `assert 'atividades' in cmds` (ou job_runs ausente)

- [ ] **Step 3: Write minimal implementation**

Em `bot/main.py`, na seção de handlers (depois do `CommandHandler("mes", ...)`):

```python
    app.add_handler(CommandHandler("atividades", handlers.cmd_atividades))
    app.add_handler(CallbackQueryHandler(handlers.on_activity_button, pattern=r"^act:"))
```

E na seção do job_queue (depois do loop de `morning_slots`, antes/depois do `job_checkin`):

```python
    jq.run_repeating(jobs.job_runs, interval=15 * 60, first=30)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/bot/test_main_wiring.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Suíte completa**

Run: `python -m pytest tests/ -q`
Expected: PASS (tudo verde)

- [ ] **Step 6: Commit**

```bash
git add bot/main.py tests/bot/test_main_wiring.py
git commit -m "feat(bot): liga /atividades e job_runs (15min) no app"
```

---

### Task 8: Deploy na VM + smoke

**Files:** nenhum (operacional)

- [ ] **Step 1: Copiar arquivos alterados pra VM**

```bash
scp -i /tmp/vmkey bot/runs.py bot/jobs.py bot/handlers.py bot/main.py bot/messages.py \
  ubuntu@136.248.77.150:~/readiness/bot/
scp -i /tmp/vmkey src/history_db.py src/services_core.py ubuntu@136.248.77.150:~/readiness/src/
scp -i /tmp/vmkey api/services.py ubuntu@136.248.77.150:~/readiness/api/
```

- [ ] **Step 2: Validar import + restart**

```bash
ssh -i /tmp/vmkey ubuntu@136.248.77.150 "cd ~/readiness && .venv/bin/python -c 'from bot.main import build_app; print(\"build OK\")' && sudo systemctl restart readiness-bot && sleep 4 && systemctl is-active readiness-bot"
```
Expected: `build OK` + `active`

- [ ] **Step 3: Smoke do /atividades ao vivo**

Mandar `/atividades` no Telegram. Esperado: lista de corridas recentes com botões; clicar → cabeçalho + insight. (1ª passada do job_runs vai seedar silenciosamente — sem spam de histórico.)

---

## Self-Review

**Spec coverage:**
- Detecção 15min → Task 5 (`job_runs`) + Task 7 (`run_repeating 15*60`). ✓
- Só corridas / exclui indoor_cardio → Task 1 (`RUN_TYPES`, `is_run`) usado em job e handler. ✓
- Dedup + seed anti-spam → Task 2 (`notified_activity`) + Task 5 (`runs_seeded`). ✓
- `/atividades` lista 8 corridas + botões → Task 6. ✓
- Mensagem cabeçalho + insight → Task 4 (`format_activity`) usada em Task 5 e 6. ✓
- Reaproveita InsightEngine + fonte única → Task 3 (`build_run_detail`, delegação de `api/services`). ✓
- Guard chat_id + degradação Garmin → Task 5 (try/except, return) e Task 6 (`_authorized`, mensagens de falha). ✓

**Placeholder scan:** sem TBD/TODO; todo passo tem código real. ✓

**Type consistency:** `build_run_detail(db, client, activity_id)` idêntico em Tasks 3/5/6. `format_activity(activity, insight)` idêntico em 4/5/6. `filter_runs(list)` em 1/5/6. `is_notified/mark_notified/get_state/set_state` conforme Task 2 e history_db existente. `client.get_activities(days)` (assinatura real, retorna raw Garmin). ✓
