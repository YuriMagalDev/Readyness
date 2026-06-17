from src.history_db import HistoryDB


def test_is_notified_falso_ate_marcar(tmp_path):
    db = HistoryDB(db_path=str(tmp_path / "h.db"))
    assert db.is_notified(111) is False
    db.mark_notified(111)
    assert db.is_notified(111) is True


def test_mark_notified_idempotente(tmp_path):
    db = HistoryDB(db_path=str(tmp_path / "h.db"))
    db.mark_notified(222)
    db.mark_notified(222)  # PK evita duplicar / não pode lançar
    assert db.is_notified(222) is True
