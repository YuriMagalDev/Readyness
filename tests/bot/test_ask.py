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
