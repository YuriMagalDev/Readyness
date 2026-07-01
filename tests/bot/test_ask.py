import bot.ask as ask


def test_open_and_active():
    ud = {}
    assert ask.is_active(ud) is False
    ask.open_thread(ud, mode="geral", run_id=None, context={"x": 1})
    assert ask.is_active(ud) is True
    assert ask.get_context(ud) == {"x": 1}
    assert ask.history(ud) == []


def test_append_roundtrip():
    ud = {}
    ask.open_thread(ud, mode="run", run_id=42, context={})
    ask.append_user(ud, "pergunta")
    ask.append_assistant(ud, "resposta")
    ask.append_user(ud, "de novo")
    assert ask.history(ud) == [
        {"role": "user", "content": "pergunta"},
        {"role": "assistant", "content": "resposta"},
        {"role": "user", "content": "de novo"},
    ]


def test_close():
    ud = {}
    ask.open_thread(ud, mode="geral", run_id=None, context={})
    ask.close_thread(ud)
    assert ask.is_active(ud) is False
    assert ask.history(ud) == []


def test_append_without_thread_noop():
    ud = {}
    ask.append_user(ud, "x")   # sem thread aberta: não quebra
    assert ask.is_active(ud) is False


from unittest.mock import MagicMock, patch


def test_build_run_context_ok():
    db = MagicMock()
    client = MagicMock()
    detail = {"activity": {"activity_id": 7, "name": "Corrida"},
              "splits": [{"km": 1}], "insight": "bom ritmo"}
    with patch("bot.ask.build_run_detail", return_value=detail):
        ctx = ask.build_run_context(db, client, 7)
    assert ctx["activity"]["activity_id"] == 7
    assert ctx["splits"] == [{"km": 1}]
    assert ctx["insight"] == "bom ritmo"


def test_build_run_context_degrada_sem_splits():
    db = MagicMock()
    db.get_activity.return_value = {"activity_id": 9, "name": "Corrida"}
    client = MagicMock()
    with patch("bot.ask.build_run_detail", side_effect=RuntimeError("429")):
        ctx = ask.build_run_context(db, client, 9)
    assert ctx["activity"]["activity_id"] == 9
    assert ctx["splits"] == []
    assert ctx["insight"] is None


def test_build_general_context():
    db = MagicMock()
    db.get_snapshots.return_value = [{"date": "2026-07-01", "resting_hr": 52}]
    panel = {"today": {"totals": {"kcal": 500}, "target": {"kcal": 1780}}}
    with patch("bot.ask.today_panel", return_value=panel):
        ctx = ask.build_general_context(db, "h.db", {"nome": "Yuri"}, "2026-07-01")
    assert ctx["readiness"]["resting_hr"] == 52
    assert ctx["nutricao"]["totals"]["kcal"] == 500


def test_build_general_context_sem_snapshot():
    db = MagicMock()
    db.get_snapshots.return_value = []
    with patch("bot.ask.today_panel", return_value={"today": {}}):
        ctx = ask.build_general_context(db, "h.db", {}, "2026-07-01")
    assert ctx["readiness"] == {}
    assert ctx["nutricao"] == {}


def test_pop_last_remove_ultimo():
    ud = {}
    ask.open_thread(ud, mode="geral", run_id=None, context={})
    ask.append_user(ud, "pergunta")
    ask.append_assistant(ud, "resposta")
    ask.pop_last(ud)
    assert ask.history(ud) == [{"role": "user", "content": "pergunta"}]


def test_pop_last_sem_thread_noop():
    ud = {}
    ask.pop_last(ud)  # sem thread: não quebra
    assert ask.is_active(ud) is False


def test_pop_last_thread_vazia_noop():
    ud = {}
    ask.open_thread(ud, mode="geral", run_id=None, context={})
    ask.pop_last(ud)  # history vazio: não quebra
    assert ask.history(ud) == []
