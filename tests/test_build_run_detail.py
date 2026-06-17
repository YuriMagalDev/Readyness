import json
from unittest.mock import MagicMock
from src.history_db import HistoryDB
from src.services_core import build_run_detail

def _db(tmp_path):
    db = HistoryDB(db_path=str(tmp_path / "h.db"))
    db.upsert_activity({"activity_id": 9, "date": "2026-06-17", "name": "Corrida",
                        "type": "running", "is_strength": 0, "distance_m": 5000})
    return db

def test_usa_splits_do_cache_sem_chamar_garmin(tmp_path, monkeypatch):
    db = _db(tmp_path)
    row = db.get_activity(9); row["splits_json"] = json.dumps([{"km": 1}]); db.upsert_activity(row)
    client = MagicMock()
    monkeypatch.setattr("src.services_core.InsightEngine",
                        lambda db: MagicMock(activity_insight=lambda a, s, force=False: "ok"))
    out = build_run_detail(db, client, 9)
    assert out["splits"] == [{"km": 1}]
    assert out["insight"] == "ok"
    client.get_activity_splits.assert_not_called()

def test_busca_splits_no_garmin_quando_falta(tmp_path, monkeypatch):
    db = _db(tmp_path)
    client = MagicMock()
    client.get_activity_splits.return_value = {"raw": True}
    monkeypatch.setattr("src.services_core.splits_from_garmin", lambda raw: [{"km": 2}])
    monkeypatch.setattr("src.services_core.InsightEngine",
                        lambda db: MagicMock(activity_insight=lambda a, s, force=False: "ins"))
    out = build_run_detail(db, client, 9)
    assert out["splits"] == [{"km": 2}]
    client.get_activity_splits.assert_called_once_with(9)
    assert json.loads(db.get_activity(9)["splits_json"]) == [{"km": 2}]

def test_atividade_inexistente_lanca(tmp_path):
    db = HistoryDB(db_path=str(tmp_path / "h.db"))
    import pytest
    with pytest.raises(ValueError):
        build_run_detail(db, MagicMock(), 404)
