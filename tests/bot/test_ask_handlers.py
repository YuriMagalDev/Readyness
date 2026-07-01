import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import bot.handlers as handlers
import bot.ask as ask


def _ctx(anthropic="client"):
    c = MagicMock()
    c.bot_data = {"anthropic": anthropic, "db": MagicMock(), "db_path": "h.db",
                  "client": MagicMock(), "cfg": MagicMock(chat_id=1)}
    c.user_data = {}
    return c


def _update(chat_id=1):
    u = MagicMock()
    u.effective_chat.id = chat_id
    u.message.reply_text = AsyncMock()
    return u


def test_cmd_ask_sem_api_key_avisa():
    u, c = _update(), _ctx(anthropic=None)
    asyncio.run(handlers.cmd_ask(u, c))
    txt = u.message.reply_text.call_args[0][0]
    assert "indispon" in txt.lower()
    assert ask.is_active(c.user_data) is False


def test_cmd_ask_com_api_mostra_botoes():
    u, c = _update(), _ctx()
    asyncio.run(handlers.cmd_ask(u, c))
    kb = u.message.reply_text.call_args[1]["reply_markup"]
    datas = [b.callback_data for row in kb.inline_keyboard for b in row]
    assert "ask:run" in datas and "ask:geral" in datas


def test_on_ask_geral_abre_thread():
    c = _ctx()
    q = MagicMock()
    q.data = "ask:geral"
    q.answer = AsyncMock()
    q.edit_message_text = AsyncMock()
    u = MagicMock(callback_query=q)
    u.effective_chat.id = 1
    with patch("bot.handlers.ask_build_general", return_value={"readiness": {}}):
        asyncio.run(handlers.on_ask_button(u, c))
    assert ask.is_active(c.user_data) is True
    assert ask.get_context(c.user_data) == {"readiness": {}}


def test_on_ask_fim_fecha_thread():
    c = _ctx()
    ask.open_thread(c.user_data, mode="geral", run_id=None, context={})
    q = MagicMock()
    q.data = "ask:fim"
    q.answer = AsyncMock()
    q.edit_message_text = AsyncMock()
    u = MagicMock(callback_query=q)
    u.effective_chat.id = 1
    asyncio.run(handlers.on_ask_button(u, c))
    assert ask.is_active(c.user_data) is False


def test_text_thread_ativa_chama_coach():
    c = _ctx()
    ask.open_thread(c.user_data, mode="geral", run_id=None, context={"readiness": {}})
    u = _update()
    u.message.text = "é certo desacelerar no fim?"
    with patch("bot.handlers.ask_coach", return_value="depende do objetivo") as m:
        asyncio.run(handlers.on_text_macros(u, c))
    # histórico acumulou pergunta + resposta
    assert ask.history(c.user_data)[-2:] == [
        {"role": "user", "content": "é certo desacelerar no fim?"},
        {"role": "assistant", "content": "depende do objetivo"},
    ]
    # resposta enviada com botão finalizar
    kb = u.message.reply_text.call_args[1]["reply_markup"]
    assert kb.inline_keyboard[0][0].callback_data == "ask:fim"
    assert m.call_args[1]["depth"] == "deep"


def test_text_sem_thread_nao_chama_coach():
    c = _ctx()
    u = _update()
    u.message.text = "qualquer coisa"
    with patch("bot.handlers.ask_coach") as m:
        asyncio.run(handlers.on_text_macros(u, c))
    m.assert_not_called()


def test_text_thread_coach_falha_mantem_thread():
    c = _ctx()
    ask.open_thread(c.user_data, mode="geral", run_id=None, context={})
    u = _update()
    u.message.text = "pergunta"
    with patch("bot.handlers.ask_coach", side_effect=RuntimeError("timeout")):
        asyncio.run(handlers.on_text_macros(u, c))
    assert ask.is_active(c.user_data) is True   # thread segue aberta
    txt = u.message.reply_text.call_args[0][0]
    assert "tenta de novo" in txt.lower()
