import pytest
from src.history_db import HistoryDB


@pytest.fixture
def db(tmp_path):
    return HistoryDB(db_path=str(tmp_path / "hist.db"))


def test_upsert_and_get_snapshot(db):
    db.upsert_snapshot({"date": "2026-06-10", "resting_hr": 52, "steps": 8000})
    rows = db.get_snapshots("2026-06-01", "2026-06-30")
    assert len(rows) == 1
    assert rows[0]["resting_hr"] == 52
    assert rows[0]["steps"] == 8000


def test_snapshot_upsert_is_idempotent(db):
    db.upsert_snapshot({"date": "2026-06-10", "resting_hr": 52})
    db.upsert_snapshot({"date": "2026-06-10", "resting_hr": 55})
    rows = db.get_snapshots("2026-06-01", "2026-06-30")
    assert len(rows) == 1
    assert rows[0]["resting_hr"] == 55


def test_get_snapshots_range_filters(db):
    db.upsert_snapshot({"date": "2026-05-01", "resting_hr": 50})
    db.upsert_snapshot({"date": "2026-06-10", "resting_hr": 52})
    rows = db.get_snapshots("2026-06-01", "2026-06-30")
    assert len(rows) == 1
    assert rows[0]["date"] == "2026-06-10"


def test_snapshots_sorted_ascending(db):
    db.upsert_snapshot({"date": "2026-06-10", "resting_hr": 52})
    db.upsert_snapshot({"date": "2026-06-05", "resting_hr": 50})
    rows = db.get_snapshots("2026-06-01", "2026-06-30")
    assert [r["date"] for r in rows] == ["2026-06-05", "2026-06-10"]


def test_upsert_and_get_activity(db):
    db.upsert_activity({"activity_id": 1, "date": "2026-06-10", "name": "Corrida",
                        "type": "running", "is_strength": 0, "distance_m": 5000})
    acts = db.get_activities("2026-06-01", "2026-06-30")
    assert len(acts) == 1
    assert acts[0]["name"] == "Corrida"


def test_activity_upsert_idempotent(db):
    db.upsert_activity({"activity_id": 1, "date": "2026-06-10", "name": "A", "type": "running"})
    db.upsert_activity({"activity_id": 1, "date": "2026-06-10", "name": "B", "type": "running"})
    acts = db.get_activities("2026-06-01", "2026-06-30")
    assert len(acts) == 1
    assert acts[0]["name"] == "B"


def test_get_single_activity(db):
    db.upsert_activity({"activity_id": 7, "date": "2026-06-10", "name": "X", "type": "running"})
    assert db.get_activity(7)["activity_id"] == 7
    assert db.get_activity(999) is None


def test_latest_snapshot_date(db):
    assert db.latest_snapshot_date() is None
    db.upsert_snapshot({"date": "2026-06-05", "resting_hr": 50})
    db.upsert_snapshot({"date": "2026-06-10", "resting_hr": 52})
    assert db.latest_snapshot_date() == "2026-06-10"


def test_ai_insight_set_get_roundtrip(tmp_path):
    from src.history_db import HistoryDB
    db = HistoryDB(db_path=str(tmp_path / "h.db"))
    assert db.get_insight("daily", "daily:2026-06-12") is None
    db.set_insight("daily", "daily:2026-06-12", "treine leve", "2026-06-12")
    assert db.get_insight("daily", "daily:2026-06-12") == "treine leve"


def test_ai_insight_stores_list_payload(tmp_path):
    from src.history_db import HistoryDB
    db = HistoryDB(db_path=str(tmp_path / "h.db"))
    db.set_insight("trend", "trend:30:2026-06-12", ["a", "b"], "2026-06-12")
    assert db.get_insight("trend", "trend:30:2026-06-12") == ["a", "b"]


def test_ai_insight_set_overwrites(tmp_path):
    from src.history_db import HistoryDB
    db = HistoryDB(db_path=str(tmp_path / "h.db"))
    db.set_insight("daily", "k", "v1", "2026-06-12")
    db.set_insight("daily", "k", "v2", "2026-06-12")
    assert db.get_insight("daily", "k") == "v2"


def test_ai_insight_delete(tmp_path):
    from src.history_db import HistoryDB
    db = HistoryDB(db_path=str(tmp_path / "h.db"))
    db.set_insight("daily", "k", "v", "2026-06-12")
    db.delete_insight("daily", "k")
    assert db.get_insight("daily", "k") is None
