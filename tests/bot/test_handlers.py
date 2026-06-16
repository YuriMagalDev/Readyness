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
    update.effective_chat.id = 1
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
