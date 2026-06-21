# Registro & Tracking do Plano (Treinus) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Comando `/plano` no bot: registra a semana (corridas do prof + musculação) colando texto, e mostra a grade com feito/furou + prontidão do dia.

**Architecture:** Parser puro (`src/plan_parser.py`) → persistência REUSA `db.upsert_plan`/`db.get_plan` (já existem) → tracking REUSA `plan_tracker.match_plan` (já existe) → formatador `bot/messages.format_plan` → handler `cmd_plano`. Sem LLM.

**Tech Stack:** Python 3.11+, python-telegram-bot v22, pytest. Reusa `plan_tracker`, `readiness_score`, `metric_reader`.

## Global Constraints

- **Determinístico, sem LLM.** Parse + tracking por regra.
- **Robustez**: linha inválida ignorada; status desconhecido → "•"; sem plano → instrução, nunca erro/crash.
- **Persistência já existe**: `db.upsert_plan(week_start, plan, created_at)` e `db.get_plan(week_start) -> {"plan": dict, "created_at": str} | None`. NÃO criar tabela nova.
- **Tracking já existe**: `plan_tracker.match_plan(plan, activities, today, week_start)` → marca `feito|pendente|furou`; `plan_tracker.week_start_of(today) -> str` (segunda ISO). NÃO reimplementar.
- Modelo de dados (igual ao futuro scraper): `{"corrida": [{"dia","descricao"}], "musculacao": [...]}`.
- pt-BR. Reusa `_e`, `_dash`, `_RULE`, `PARSE_MODE` de `bot/messages.py`.
- Guard de chat já é aplicado por `_authorized` em `bot/handlers.py`.

---

### Task 1: `src/plan_parser.py` — parse leniente

**Files:**
- Create: `src/plan_parser.py`
- Test: `tests/test_plan_parser.py`

**Interfaces:**
- Produces: `parse_plan(text: str) -> dict` → `{"corrida": [{"dia": str, "descricao": str}], "musculacao": [...]}`.

- [ ] **Step 1: Write the failing test**

```python
from src.plan_parser import parse_plan


def test_parse_separa_corrida_e_musculacao():
    txt = "/plano\nseg corrida intervalado 6x800\nter musculacao superior\nsex corrida longao 12km"
    out = parse_plan(txt)
    assert [s["dia"] for s in out["corrida"]] == ["seg", "sex"]
    assert out["corrida"][0]["descricao"] == "intervalado 6x800"
    assert [s["dia"] for s in out["musculacao"]] == ["ter"]


def test_parse_aceita_variacoes_de_tipo_e_acento():
    out = parse_plan("qua força inferior\nterça corrida leve 40min")
    assert out["musculacao"][0]["dia"] == "qua"
    assert out["corrida"][0]["dia"] == "terça"     # dia original preservado


def test_parse_ignora_linha_invalida_e_vazia():
    out = parse_plan("/plano\n\nblah\nseg corrida x\nzzz musculacao y")
    assert len(out["corrida"]) == 1 and out["corrida"][0]["dia"] == "seg"
    assert out["musculacao"] == []                 # 'zzz' não é dia válido


def test_parse_texto_vazio():
    assert parse_plan("") == {"corrida": [], "musculacao": []}
    assert parse_plan("/plano") == {"corrida": [], "musculacao": []}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_plan_parser.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.plan_parser'`.

- [ ] **Step 3: Write minimal implementation**

```python
_DIAS = {"seg", "ter", "qua", "qui", "sex", "sab", "dom"}
_ACENTOS = str.maketrans("áâãàéêíóôõúç", "aaaaeeiooouc")


def _norm_dia(tok: str) -> str:
    return tok.strip().lower().translate(_ACENTOS)[:3]


def _tipo(tok: str):
    t = tok.strip().lower().translate(_ACENTOS)
    if t.startswith("cor"):
        return "corrida"
    if t.startswith("mus") or t.startswith("for"):
        return "musculacao"
    return None


def parse_plan(text: str) -> dict:
    """Parseia a semana colada (1 treino por linha: 'dia tipo descrição').
    Linha sem dia/tipo reconhecível é ignorada. A linha do comando /plano é ignorada."""
    corrida, musculacao = [], []
    for line in (text or "").splitlines():
        parts = line.split()
        if parts and parts[0].lower().startswith("/plano"):
            parts = parts[1:]
        if len(parts) < 2:
            continue
        if _norm_dia(parts[0]) not in _DIAS:
            continue
        tipo = _tipo(parts[1])
        if tipo is None:
            continue
        item = {"dia": parts[0], "descricao": " ".join(parts[2:]).strip()}
        (corrida if tipo == "corrida" else musculacao).append(item)
    return {"corrida": corrida, "musculacao": musculacao}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_plan_parser.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add src/plan_parser.py tests/test_plan_parser.py
git commit -m "feat(plan): parse_plan leniente (corrida/musculacao por linha)"
```

---

### Task 2: `bot/messages.py` — `format_plan`

**Files:**
- Modify: `bot/messages.py` (adicionar no fim)
- Test: `tests/bot/test_messages.py`

**Interfaces:**
- Consumes: `_e`, `_dash`, `_RULE` (já no módulo). `matched` = saída de `match_plan` (`{"corrida":[{dia,descricao,status,...}], "musculacao":[...]}`).
- Produces: `format_plan(matched: dict, score=None, acwr=None) -> str`.

- [ ] **Step 1: Write the failing test**

```python
def test_format_plan_grade_e_status():
    from bot import messages
    matched = {
        "corrida": [
            {"dia": "seg", "descricao": "intervalado", "status": "feito"},
            {"dia": "sex", "descricao": "longao", "status": "pendente"},
        ],
        "musculacao": [{"dia": "ter", "descricao": "superior", "status": "furou"}],
    }
    txt = messages.format_plan(matched, score=72, acwr=1.2)
    assert "Plano da semana" in txt
    assert "72/100" in txt and "1.2" in txt
    assert "✅" in txt and "⏳" in txt and "❌" in txt
    assert "intervalado" in txt and "superior" in txt


def test_format_plan_sem_score_em_dash():
    from bot import messages
    txt = messages.format_plan({"corrida": [], "musculacao": []})
    assert "—/100" in txt          # score None vira em-dash
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/bot/test_messages.py -k format_plan -q`
Expected: FAIL — `AttributeError: module 'bot.messages' has no attribute 'format_plan'`.

- [ ] **Step 3: Write minimal implementation**

Adicionar no fim de `bot/messages.py`:

```python
_PLAN_ICON = {"feito": "✅", "furou": "❌", "pendente": "⏳"}


def format_plan(matched: dict, score=None, acwr=None) -> str:
    linhas = [
        "🗓 <b>Plano da semana</b>", _RULE,
        f"prontidão {_dash(score)}/100 · ACWR {_dash(acwr)}", _RULE,
    ]
    for grade, titulo in (("corrida", "🏃 Corrida"), ("musculacao", "🏋 Musculação")):
        sessoes = matched.get(grade) or []
        if not sessoes:
            continue
        linhas.append(f"<b>{titulo}</b>")
        for s in sessoes:
            icon = _PLAN_ICON.get(s.get("status"), "•")
            linhas.append(f"{icon} {_e(s.get('dia', ''))} — {_e(s.get('descricao', ''))}")
    return "\n".join(linhas)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/bot/test_messages.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add bot/messages.py tests/bot/test_messages.py
git commit -m "feat(bot): format_plan (grade da semana + status + prontidao)"
```

---

### Task 3: `bot/handlers.py` — `cmd_plano` (mostra/registra)

**Files:**
- Modify: `bot/handlers.py` (imports + função `cmd_plano`)
- Test: `tests/bot/test_handlers.py`

**Interfaces:**
- Consumes: `parse_plan` (Task 1); `format_plan` (Task 2); `db.upsert_plan`/`db.get_plan`/`db.get_activities`; `plan_tracker.match_plan`/`week_start_of`; `compute_readiness`; `context_from_metrics`.
- Produces: `async def cmd_plano(update, context)`.

- [ ] **Step 1: Write the failing test**

```python
@pytest.mark.asyncio
async def test_cmd_plano_registra_e_mostra(tmp_path):
    db = HistoryDB(db_path=str(tmp_path / "p.db"))
    update = MagicMock()
    update.effective_chat.id = 99
    update.message.text = "/plano\nseg corrida intervalado\nter musculacao superior"
    update.message.reply_text = AsyncMock()
    await handlers.cmd_plano(update, _ctx(db))
    # 1ª reply = confirmação, 2ª = grade
    assert update.message.reply_text.await_count == 2
    assert "salvo" in update.message.reply_text.await_args_list[0].args[0].lower()
    # persistiu
    from src.plan_tracker import week_start_of
    import datetime
    ws = week_start_of(datetime.date.today())
    assert db.get_plan(ws) is not None


@pytest.mark.asyncio
async def test_cmd_plano_sem_plano_instrui(tmp_path):
    db = HistoryDB(db_path=str(tmp_path / "p2.db"))
    update = MagicMock()
    update.effective_chat.id = 99
    update.message.text = "/plano"
    update.message.reply_text = AsyncMock()
    await handlers.cmd_plano(update, _ctx(db))
    assert update.message.reply_text.await_count == 1
    assert "registre" in update.message.reply_text.await_args.args[0].lower()


@pytest.mark.asyncio
async def test_cmd_plano_formato_invalido_nao_salva(tmp_path):
    db = HistoryDB(db_path=str(tmp_path / "p3.db"))
    update = MagicMock()
    update.effective_chat.id = 99
    update.message.text = "/plano\nblah blah nada aqui"
    update.message.reply_text = AsyncMock()
    await handlers.cmd_plano(update, _ctx(db))
    assert "inválido" in update.message.reply_text.await_args.args[0].lower()
    from src.plan_tracker import week_start_of
    import datetime
    assert db.get_plan(week_start_of(datetime.date.today())) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/bot/test_handlers.py -k cmd_plano -q`
Expected: FAIL — `AttributeError: module 'bot.handlers' has no attribute 'cmd_plano'`.

- [ ] **Step 3: Write minimal implementation**

Em `bot/handlers.py`, adicionar imports (junto dos existentes):

```python
from src.plan_parser import parse_plan
from src.plan_tracker import match_plan, week_start_of
from src.readiness_score import compute_readiness
from src.metric_reader import context_from_metrics
```

E a função:

```python
async def cmd_plano(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _authorized(update, context):
        return
    db = context.bot_data["db"]
    today = dt.date.today()
    week_start = week_start_of(today)
    texto = update.message.text or ""
    corpo = "\n".join(texto.splitlines()[1:]).strip()  # linhas após o /plano

    if corpo:
        plan = parse_plan(texto)
        if not plan["corrida"] and not plan["musculacao"]:
            await update.message.reply_text(
                "Formato inválido. Ex:\n/plano\nseg corrida 40min\nter musculacao superior")
            return
        db.upsert_plan(week_start, plan, dt.datetime.now().isoformat(timespec="seconds"))
        await update.message.reply_text(
            f"Plano salvo: {len(plan['corrida'])} corridas, {len(plan['musculacao'])} musculações.")

    stored = db.get_plan(week_start)
    if stored is None:
        await update.message.reply_text(
            "Nenhum plano esta semana. Registre colando:\n"
            "/plano\nseg corrida 40min\nter musculacao superior")
        return

    plan = stored["plan"]
    acts = db.get_activities(week_start, today.isoformat())
    matched = match_plan(plan, acts, today, week_start)
    try:
        ctx = context_from_metrics(db, today.isoformat())
        score, acwr = compute_readiness(ctx)["score"], ctx.get("acwr")
    except Exception:  # noqa: BLE001 — prontidão é enfeite do cabeçalho; plano sai mesmo sem ela
        score, acwr = None, None
    await update.message.reply_text(
        messages.format_plan(matched, score, acwr), parse_mode=messages.PARSE_MODE)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/bot/test_handlers.py -k cmd_plano -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add bot/handlers.py tests/bot/test_handlers.py
git commit -m "feat(bot): cmd_plano (registra colando / mostra grade + prontidao)"
```

---

### Task 4: Wiring + comando no /start

**Files:**
- Modify: `bot/main.py` (registrar handler)
- Modify: `bot/handlers.py:cmd_start` (citar /plano no menu)
- Test: `tests/bot/test_main_wiring.py`

**Interfaces:**
- Consumes: `handlers.cmd_plano`.
- Produces: `CommandHandler("plano", handlers.cmd_plano)` registrado.

- [ ] **Step 1: Write the failing test**

Adicionar em `tests/bot/test_main_wiring.py` (seguir o padrão de setup já usado no arquivo):

```python
def test_handler_plano_registrado(monkeypatch):
    monkeypatch.setenv("TELEGRAM_TOKEN", "x")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "1")
    monkeypatch.setattr("bot.main.HistoryDB", lambda db_path: object())
    monkeypatch.setattr("bot.main.GarminClient", lambda: object())
    from bot import main, handlers
    app = main.build_app()
    cmds = set()
    for h in app.handlers[0]:
        cb = getattr(h, "callback", None)
        if cb is not None:
            cmds.add(cb)
    assert handlers.cmd_plano in cmds
```

(Se o arquivo já tiver um helper que constrói o app/inspeciona handlers, reusar; o ponto é confirmar
que `handlers.cmd_plano` está registrado como handler de comando.)

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/bot/test_main_wiring.py -k plano -q`
Expected: FAIL — `cmd_plano` não está nos handlers.

- [ ] **Step 3: Write minimal implementation**

Em `bot/main.py`, junto dos outros `CommandHandler` (após o de `atividades`):

```python
    app.add_handler(CommandHandler("plano", handlers.cmd_plano))
```

Em `bot/handlers.py`, na string de `cmd_start`, adicionar uma linha ao menu:

```python
        "/plano — registrar/ver o plano da semana\n"
```

(inserir junto das outras linhas de comando do texto de ajuda.)

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/bot/test_main_wiring.py -q`
Expected: PASS.

- [ ] **Step 5: Run full suite**

Run: `python -m pytest -q`
Expected: tudo verde.

- [ ] **Step 6: Commit**

```bash
git add bot/main.py bot/handlers.py tests/bot/test_main_wiring.py
git commit -m "feat(bot): wiring do /plano + menu no /start"
```

---

## Self-Review

**1. Spec coverage:**
- `parse_plan` (linhas, tipos, acento, inválida) → Task 1 ✅
- Persistência → REUSA `db.upsert_plan`/`get_plan` (já existem) — Task 3 usa ✅
- Tracking feito/furou → REUSA `match_plan` — Task 3 usa ✅
- `format_plan` (grade + status + prontidão) → Task 2 ✅
- `cmd_plano` mostra/registra/instrui/inválido → Task 3 ✅
- Cruzamento carga/prontidão no cabeçalho → Task 3 (compute_readiness) + Task 2 (render) ✅
- Wiring → Task 4 ✅
- Determinístico / sem LLM → nenhuma task chama LLM ✅

**2. Placeholder scan:** sem TBD/TODO; todo step tem código real.

**3. Type consistency:** `parse_plan` retorna `{"corrida","musculacao"}` com itens `{dia,descricao}` — exatamente o que `match_plan` consome e `db.upsert_plan` serializa; `match_plan` adiciona `status` que `format_plan` lê; `db.get_plan` retorna `{"plan",...}` e Task 3 lê `stored["plan"]`; `compute_readiness(ctx)["score"]` + `ctx["acwr"]` passados a `format_plan(matched, score, acwr)`. OK.
