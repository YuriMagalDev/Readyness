import datetime as dt
import pytest
from src.history_db import HistoryDB
from src.services_core import save_checkin

def test_save_checkin_grava_1a5(tmp_path):
    db = HistoryDB(db_path=str(tmp_path / "h.db"))
    save_checkin(db, {"hidratacao": 4, "energia": 2}, today=dt.date(2026, 6, 16))
    rows = db.get_metrics_for_date("2026-06-16")
    vals = {r["metric_key"]: r["value"] for r in rows}
    assert vals["hidratacao"] == 4 and vals["energia"] == 2

def test_save_checkin_rejeita_fora_de_faixa(tmp_path):
    db = HistoryDB(db_path=str(tmp_path / "h.db"))
    with pytest.raises(ValueError):
        save_checkin(db, {"hidratacao": 9}, today=dt.date(2026, 6, 16))
