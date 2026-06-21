import datetime as dt
import pytest
from unittest.mock import AsyncMock, MagicMock
from src.history_db import HistoryDB
from bot.config import Config
from bot import jobs

def _cfg():
    return Config(token="t", chat_id=99, checkin_hour=21,
                  morning_slots=((9, 30), (12, 0), (14, 0)), db_path=":memory:")

def _job_ctx(db, client):
    ctx = MagicMock()
    ctx.bot_data = {"cfg": _cfg(), "db": db, "client": client}
    ctx.bot.send_message = AsyncMock()
    return ctx

@pytest.mark.asyncio
async def test_job_morning_envia_uma_vez_quando_sono_sincronizou(tmp_path, monkeypatch):
    db = HistoryDB(db_path=str(tmp_path / "h.db"))
    client = MagicMock()
    client.get_sleep_day.return_value = {"dailySleepDTO": {"sleepEndTimestampLocal": 1781503920000}}
    monkeypatch.setattr(jobs.core, "load_context", lambda c: {
        "resting_hr_today": 55, "resting_hr_avg_7d": 60.9, "morning_battery_avg": 38,
        "sleep_debt_hours": 2.4, "run_sessions_7d": 3})
    monkeypatch.setattr(jobs.core, "daily_analysis", lambda db, day, force=False: {
        "veredito": {"status": "amarelo", "motivo": "x", "recomendacao": "y"}, "insights": []})
    monkeypatch.setattr(jobs, "Ingestor", lambda c, d: MagicMock(sync_today=lambda: None))
    monkeypatch.setattr(jobs, "_now_time", lambda: dt.time(9, 30))

    ctx = _job_ctx(db, client)
    await jobs.job_morning(ctx)
    assert ctx.bot.send_message.await_count == 1
    await jobs.job_morning(ctx)
    assert ctx.bot.send_message.await_count == 1  # não re-envia no mesmo dia


@pytest.mark.asyncio
async def test_job_morning_slot_cedo_sem_sync_nao_envia(tmp_path, monkeypatch):
    # slot 09:30, sono ainda não sincronizou (sem sleepEnd): espera o próximo slot
    db = HistoryDB(db_path=str(tmp_path / "h.db"))
    client = MagicMock()
    client.get_sleep_day.return_value = {"dailySleepDTO": {}}
    monkeypatch.setattr(jobs, "_now_time", lambda: dt.time(9, 30))
    ctx = _job_ctx(db, client)
    await jobs.job_morning(ctx)
    ctx.bot.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_job_morning_ultimo_slot_envia_mesmo_sem_sync(tmp_path, monkeypatch):
    # 14:00 (último slot) sem sleepEnd -> manda mesmo assim
    db = HistoryDB(db_path=str(tmp_path / "h.db"))
    client = MagicMock()
    client.get_sleep_day.return_value = {"dailySleepDTO": {}}
    monkeypatch.setattr(jobs.core, "load_context", lambda c: {
        "resting_hr_today": None, "resting_hr_avg_7d": None, "morning_battery_avg": None,
        "sleep_debt_hours": None, "run_sessions_7d": 0})
    monkeypatch.setattr(jobs.core, "daily_analysis", lambda db, day, force=False: {
        "veredito": {"status": "verde", "motivo": "x", "recomendacao": "y"}, "insights": []})
    monkeypatch.setattr(jobs, "Ingestor", lambda c, d: MagicMock(sync_today=lambda: None))
    monkeypatch.setattr(jobs, "_now_time", lambda: dt.time(14, 0))
    ctx = _job_ctx(db, client)
    await jobs.job_morning(ctx)
    assert ctx.bot.send_message.await_count == 1  # fallback do último slot


@pytest.mark.asyncio
async def test_job_alerts_anti_spam(tmp_path, monkeypatch):
    db = HistoryDB(db_path=str(tmp_path / "a.db"))
    client = MagicMock()
    monkeypatch.setattr(jobs, "Ingestor", lambda c, d: MagicMock(sync_today=lambda: None))
    # contexto com ACWR em risco; sem FC/baseline (só ACWR dispara)
    monkeypatch.setattr(jobs, "context_from_metrics", lambda db, day: {
        "acwr": 1.8, "resting_hr_baseline": None})
    monkeypatch.setattr(jobs.core, "daily_analysis", lambda db, day, force=False: {
        "veredito": {"overreaching": False}})
    ctx = _job_ctx(db, client)

    await jobs.job_alerts(ctx)
    assert ctx.bot.send_message.await_count == 1      # ACWR cruzou -> 1 alerta
    await jobs.job_alerts(ctx)
    assert ctx.bot.send_message.await_count == 1      # ainda risco -> não repete

    # ACWR normaliza -> reseta episódio
    monkeypatch.setattr(jobs, "context_from_metrics", lambda db, day: {
        "acwr": 1.0, "resting_hr_baseline": None})
    await jobs.job_alerts(ctx)
    assert ctx.bot.send_message.await_count == 1      # sem alerta
    assert db.get_state("alert_acwr") == "0"

    # volta a risco -> dispara de novo
    monkeypatch.setattr(jobs, "context_from_metrics", lambda db, day: {
        "acwr": 1.9, "resting_hr_baseline": None})
    await jobs.job_alerts(ctx)
    assert ctx.bot.send_message.await_count == 2


@pytest.mark.asyncio
async def test_job_morning_degrada_quando_garmin_falha(tmp_path, monkeypatch):
    # Garmin fora (load_context lança): manda o veredito do DB mesmo assim e marca enviado
    db = HistoryDB(db_path=str(tmp_path / "h.db"))
    client = MagicMock()
    client.get_sleep_day.return_value = {"dailySleepDTO": {"sleepEndTimestampLocal": 1781503920000}}

    def _boom(c):
        raise TypeError("garmin 429")

    monkeypatch.setattr(jobs.core, "load_context", _boom)
    monkeypatch.setattr(jobs.core, "daily_analysis", lambda db, day, force=False: {
        "veredito": {"status": "amarelo", "motivo": "m", "recomendacao": "r"}, "insights": []})
    monkeypatch.setattr(jobs, "Ingestor", lambda c, d: MagicMock(sync_today=lambda: None))
    monkeypatch.setattr(jobs, "_now_time", lambda: dt.time(9, 30))
    ctx = _job_ctx(db, client)
    await jobs.job_morning(ctx)
    assert ctx.bot.send_message.await_count == 1  # mandou degradado
    await jobs.job_morning(ctx)
    assert ctx.bot.send_message.await_count == 1  # não re-tenta no mesmo dia
