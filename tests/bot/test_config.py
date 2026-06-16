from bot.config import Config

def test_config_le_env(monkeypatch):
    monkeypatch.setenv("TELEGRAM_TOKEN", "tok")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123")
    monkeypatch.setenv("CHECKIN_HOUR", "21")
    monkeypatch.setenv("WAKE_WINDOW_START", "05:00")
    monkeypatch.setenv("WAKE_WINDOW_END", "11:00")
    c = Config.from_env()
    assert c.token == "tok"
    assert c.chat_id == 123
    assert c.checkin_hour == 21
    assert c.wake_start == (5, 0) and c.wake_end == (11, 0)

def test_config_exige_token(monkeypatch):
    monkeypatch.delenv("TELEGRAM_TOKEN", raising=False)
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "1")
    import pytest
    with pytest.raises(ValueError):
        Config.from_env()
