import json
from pathlib import Path
from unittest.mock import patch, MagicMock
import src.ai_coach as ai_coach


def _fake_profile(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    Path("athlete_profile.json").write_text(
        json.dumps({"nome": "Yuri", "objetivo_principal": "x"}), encoding="utf-8")


def test_ask_coach_system_is_block_list_with_cache_control(tmp_path, monkeypatch):
    _fake_profile(tmp_path, monkeypatch)
    fake_msg = MagicMock()
    fake_msg.content = [MagicMock(text="resp")]
    fake_client = MagicMock()
    fake_client.messages.create.return_value = fake_msg
    with patch("src.ai_coach.anthropic.Anthropic", return_value=fake_client):
        out = ai_coach.ask_coach("oi", {"hr": 50}, depth="quick")
    assert out == "resp"
    system = fake_client.messages.create.call_args[1]["system"]
    assert isinstance(system, list) and len(system) == 2
    assert system[0]["cache_control"] == {"type": "ephemeral"}
    assert "PERFIL" in system[0]["text"]
    assert "cache_control" not in system[1]
    assert "CONTEXTO" in system[1]["text"]


def test_ask_coach_accepts_message_history(tmp_path, monkeypatch):
    _fake_profile(tmp_path, monkeypatch)
    fake_msg = MagicMock()
    fake_msg.content = [MagicMock(text="resp2")]
    fake_client = MagicMock()
    fake_client.messages.create.return_value = fake_msg
    history = [
        {"role": "user", "content": "primeira"},
        {"role": "assistant", "content": "ok"},
        {"role": "user", "content": "segunda"},
    ]
    with patch("src.ai_coach.anthropic.Anthropic", return_value=fake_client):
        out = ai_coach.ask_coach(history, {"hr": 50}, depth="deep")
    assert out == "resp2"
    sent = fake_client.messages.create.call_args[1]["messages"]
    assert sent == history
    assert fake_client.messages.create.call_args[1]["model"] == "claude-sonnet-5"


def test_ask_coach_string_still_works(tmp_path, monkeypatch):
    _fake_profile(tmp_path, monkeypatch)
    fake_msg = MagicMock()
    fake_msg.content = [MagicMock(text="r")]
    fake_client = MagicMock()
    fake_client.messages.create.return_value = fake_msg
    with patch("src.ai_coach.anthropic.Anthropic", return_value=fake_client):
        ai_coach.ask_coach("oi", {}, depth="quick")
    sent = fake_client.messages.create.call_args[1]["messages"]
    assert sent == [{"role": "user", "content": "oi"}]
