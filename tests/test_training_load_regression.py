import datetime
from src.history_db import HistoryDB
from src.metric_reader import context_from_metrics, read_metrics


def test_context_inclui_metricas_de_carga(tmp_path):
    """Sub-projeto 2: agora o context EXPÕE acwr/soreness/energia/baseline pro veredito."""
    db = HistoryDB(str(tmp_path / "r.db"))
    db.upsert_metric("2026-06-20", "acwr", 1.8, "2026-06-20T10:00:00", "computed")
    db.upsert_metric("2026-06-20", "resting_hr", 55, "2026-06-20T08:00:00", "garmin")
    ctx = context_from_metrics(db, "2026-06-20", today=datetime.date(2026, 6, 20))
    assert ctx["acwr"] == 1.8
    assert set(ctx.keys()) == {
        "resting_hr_today", "resting_hr_avg_7d", "sleep_debt_hours",
        "morning_battery_avg", "run_sessions_7d",
        "acwr", "soreness", "energia", "resting_hr_baseline",
    }


def test_read_metrics_expoe_acwr(tmp_path):
    db = HistoryDB(str(tmp_path / "r2.db"))
    db.upsert_metric("2026-06-20", "acwr", 1.2, "2026-06-20T10:00:00", "computed")
    out = read_metrics(db, "2026-06-20", today=datetime.date(2026, 6, 20))
    cells = {c["key"]: c for c in out["dominios"]["prontidao"]}
    assert cells["acwr"]["value"] == 1.2
    assert cells["acwr"]["status"] == "fresco"
