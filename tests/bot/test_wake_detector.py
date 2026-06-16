import datetime as dt
from bot.wake_detector import wake_time_local, woke_up_today

_TS = 1781503920000
_EXPECTED = dt.datetime.fromtimestamp(_TS / 1000, dt.timezone.utc).strftime("%H:%M")

def test_extrai_hora_de_acordar():
    assert wake_time_local({"dailySleepDTO": {"sleepEndTimestampLocal": _TS}}) == _EXPECTED

def test_sem_fim_de_sono_retorna_none():
    assert wake_time_local({"dailySleepDTO": {}}) is None
    assert wake_time_local({}) is None
    assert wake_time_local(None) is None

def test_woke_up_today():
    assert woke_up_today({"dailySleepDTO": {"sleepEndTimestampLocal": _TS}}) is True
    assert woke_up_today({}) is False
