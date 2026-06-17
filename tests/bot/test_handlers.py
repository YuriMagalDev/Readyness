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
async def test_callback_checkin_grava_no_dia_do_checkin(tmp_path):
    # responde após a meia-noite mas o callback carrega o dia do check-in (ontem)
    db = HistoryDB(db_path=str(tmp_path / "h.db"))
    dia_checkin = "2026-06-15"
    update = MagicMock()
    update.effective_chat.id = 99
    update.callback_query.data = f"ci:energia:4:{dia_checkin}"
    update.callback_query.answer = AsyncMock()
    update.callback_query.edit_message_text = AsyncMock()
    await handlers.on_checkin_button(update, _ctx(db))
    rows = {r["metric_key"]: r["value"] for r in db.get_metrics_for_date(dia_checkin)}
    assert rows["energia"] == 4                       # gravou no dia do check-in
    assert db.get_metrics_for_date(dt.date.today().isoformat()) == []  # não no dia do clique
    update.callback_query.edit_message_text.assert_awaited()
