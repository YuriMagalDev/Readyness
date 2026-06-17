from unittest.mock import patch, MagicMock


def test_build_app_registra_atividades_e_job_runs(monkeypatch):
    monkeypatch.setenv("TELEGRAM_TOKEN", "tok")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "99")
    monkeypatch.setenv("DB_PATH", ":memory:")
    with patch("bot.main.GarminClient", return_value=MagicMock()):
        from bot.main import build_app
        app = build_app()
    cmds = set()
    for grupo in app.handlers.values():
        for h in grupo:
            cmds |= set(getattr(h, "commands", []) or [])
    assert "atividades" in cmds
    nomes = {j.name for j in app.job_queue.jobs()}
    assert any("job_runs" in n for n in nomes)
