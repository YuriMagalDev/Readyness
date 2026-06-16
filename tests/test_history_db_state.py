from src.history_db import HistoryDB

def test_state_roundtrip(tmp_path):
    db = HistoryDB(db_path=str(tmp_path / "h.db"))
    assert db.get_state("saldo_date") is None
    db.set_state("saldo_date", "2026-06-16")
    assert db.get_state("saldo_date") == "2026-06-16"
    db.set_state("saldo_date", "2026-06-17")
    assert db.get_state("saldo_date") == "2026-06-17"
