import datetime as dt
import pytest
from unittest.mock import AsyncMock, MagicMock
from src.history_db import HistoryDB
from bot.config import Config
from bot import jobs

def _cfg():
    return Config(token="t", chat_id=99, checkin_hour=21,
                  wake_start=(5, 0), wake_end=(11, 0), wake_poll_minutes=15, db_path=":memory:")

def _job_ctx(db, client):
    ctx = MagicMock()
    ctx.bot_data = {"cfg": _cfg(), "db": db, "client": client}
    ctx.bot.send_message = AsyncMock()
    return ctx

@pytest.mark.asyncio
async def test_job_wake_envia_uma_vez(tmp_path, monkeypatch):
    db = HistoryDB(db_path=str(tmp_path / "h.db"))
    client = MagicMock()
    client.get_sleep_day.return_value = {"dailySleepDTO": {"sleepEndTimestampLocal": 1781503920000}}
    monkeypatch.setattr(jobs.core, "load_context", lambda c: {
        "resting_hr_today": 55, "resting_hr_avg_7d": 60.9, "morning_battery_avg": 38,
        "sleep_debt_hours": 2.4, "run_sessions_7d": 3})
    monkeypatch.setattr(jobs.core, "daily_analysis", lambda db, day, force=False: {
        "veredito": {"status": "amarelo", "motivo": "x", "recomendacao": "y"}, "insights": []})
    monkeypatch.setattr(jobs, "Ingestor", lambda c, d: MagicMock(sync_today=lambda: None))
    # garante que "agora" está dentro da janela matinal pro teste ser determinístico
    monkeypatch.setattr(jobs, "_now_time", lambda: dt.time(6, 0))

    ctx = _job_ctx(db, client)
    await jobs.job_wake(ctx)
    assert ctx.bot.send_message.await_count == 1
    await jobs.job_wake(ctx)
    assert ctx.bot.send_message.await_count == 1


@pytest.mark.asyncio
async def test_job_wake_nao_consulta_fora_da_janela(tmp_path, monkeypatch):
    db = HistoryDB(db_path=str(tmp_path / "h.db"))
    client = MagicMock()
    ctx = _job_ctx(db, client)
    monkeypatch.setattr(jobs, "_now_time", lambda: dt.time(4, 0))
    await jobs.job_wake(ctx)
    client.get_sleep_day.assert_not_called()
    ctx.bot.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_job_wake_fallback_fim_da_janela_sem_acordar(tmp_path, monkeypatch):
    # fim da janela (11:00), sem hora de acordar no DTO -> manda mesmo assim
    db = HistoryDB(db_path=str(tmp_path / "h.db"))
    client = MagicMock()
    client.get_sleep_day.return_value = {"dailySleepDTO": {}}  # sem sleepEnd
    monkeypatch.setattr(jobs.core, "load_context", lambda c: {
        "resting_hr_today": None, "resting_hr_avg_7d": None, "morning_battery_avg": None,
        "sleep_debt_hours": None, "run_sessions_7d": 0})
    monkeypatch.setattr(jobs.core, "daily_analysis", lambda db, day, force=False: {
        "veredito": {"status": "verde", "motivo": "x", "recomendacao": "y"}, "insights": []})
    monkeypatch.setattr(jobs, "Ingestor", lambda c, d: MagicMock(sync_today=lambda: None))
    monkeypatch.setattr(jobs, "_now_time", lambda: dt.time(11, 0))
    ctx = _job_ctx(db, client)
    await jobs.job_wake(ctx)
    assert ctx.bot.send_message.await_count == 1  # fallback disparou
