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
    ctx.bot.send_message.assert_not_awaited()
    assert db.is_notified(1) and db.is_notified(2)

@pytest.mark.asyncio
async def test_corrida_nova_apos_seed_envia_uma_vez(tmp_path):
    db = HistoryDB(db_path=str(tmp_path / "h.db"))
    client = MagicMock()
    client.get_activities.return_value = [_raw_run(1)]
    ctx = _ctx(db, client)
    await jobs.job_runs(ctx)
    client.get_activities.return_value = [_raw_run(2), _raw_run(1)]
    await jobs.job_runs(ctx)
    assert ctx.bot.send_message.await_count == 1
    assert db.is_notified(2)
    await jobs.job_runs(ctx)
    assert ctx.bot.send_message.await_count == 1

@pytest.mark.asyncio
async def test_musculacao_nunca_dispara(tmp_path):
    db = HistoryDB(db_path=str(tmp_path / "h.db"))
    client = MagicMock()
    client.get_activities.return_value = []
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
    await jobs.job_runs(ctx)
    ctx.bot.send_message.assert_not_awaited()
