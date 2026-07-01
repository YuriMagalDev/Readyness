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
    asyncio.run(handlers.on_ask_button(u, c))
    assert ask.is_active(c.user_data) is False
