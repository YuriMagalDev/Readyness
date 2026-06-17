from bot.config import Config

def test_config_le_env(monkeypatch):
    monkeypatch.setenv("TELEGRAM_TOKEN", "tok")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123")
    monkeypatch.setenv("CHECKIN_HOUR", "21")
    monkeypatch.setenv("MORNING_SLOTS", "09:30,12:00,14:00")
    c = Config.from_env()
    assert c.token == "tok"
    assert c.chat_id == 123
    assert c.checkin_hour == 21
    assert c.morning_slots == ((9, 30), (12, 0), (14, 0))

def test_config_morning_slots_default(monkeypatch):
    monkeypatch.setenv("TELEGRAM_TOKEN", "tok")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "1")
    monkeypatch.delenv("MORNING_SLOTS", raising=False)
    assert Config.from_env().morning_slots == ((9, 30), (12, 0), (14, 0))

def test_config_exige_token(monkeypatch):
    monkeypatch.delenv("TELEGRAM_TOKEN", raising=False)
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "1")
    import pytest
    with pytest.raises(ValueError):
        Config.from_env()
