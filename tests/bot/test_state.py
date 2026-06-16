from src.history_db import HistoryDB
from bot.state import already_sent_saldo, mark_saldo_sent

def test_dedup_saldo(tmp_path):
    db = HistoryDB(db_path=str(tmp_path / "h.db"))
    assert already_sent_saldo(db, "2026-06-16") is False
    mark_saldo_sent(db, "2026-06-16")
    assert already_sent_saldo(db, "2026-06-16") is True
    assert already_sent_saldo(db, "2026-06-17") is False
