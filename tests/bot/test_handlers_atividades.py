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
    assert len(botoes) == 1
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
    update = MagicMock(); update.effective_chat.id = 1
    update.callback_query.answer = AsyncMock()
    update.callback_query.edit_message_text = AsyncMock()
    await handlers.on_activity_button(update, _ctx(db, MagicMock()))
    update.callback_query.edit_message_text.assert_not_awaited()

@pytest.mark.asyncio
async def test_atividades_persiste_corridas_no_db(tmp_path):
    db = HistoryDB(db_path=str(tmp_path / "h.db"))
    client = MagicMock()
    client.get_activities.return_value = [_raw_run(1, "Corrida A")]
    update = MagicMock(); update.effective_chat.id = 99
    update.message.reply_text = AsyncMock()
    await handlers.cmd_atividades(update, _ctx(db, client))
    assert db.get_activity(1) is not None      # corrida listada foi ingerida
