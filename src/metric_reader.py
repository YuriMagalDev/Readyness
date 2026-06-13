import datetime as _dt
from src.metric_catalog import CATALOG, DOMAIN_ORDER
from src.metric_status import compute_status


def read_metrics(db, date: str, today: _dt.date = None) -> dict:
    today = today or _dt.date.today()
    rows_today = {r["metric_key"]: r for r in db.get_metrics(date)}

    dominios = {d: [] for d in DOMAIN_ORDER}
    for spec in CATALOG:
        row = rows_today.get(spec.key)
        if row is None and spec.cadencia in ("corpo", "fitness"):
            row = _latest_on_or_before(db, spec.key, date)

        if row is None:
            value, measured_at, source = None, None, spec.source_default
        else:
            value, measured_at, source = row["value"], row["measured_at"], row["source"]

        status = compute_status(spec.cadencia, source, measured_at, today)
        dominios[spec.dominio].append({
            "key": spec.key, "label": spec.label, "value": value,
            "unidade": spec.unidade, "measured_at": measured_at,
            "status": status, "source": source,
        })
    return {"date": date, "dominios": dominios}


def _latest_on_or_before(db, metric_key: str, date: str):
    start = (_dt.date.fromisoformat(date) - _dt.timedelta(days=60)).isoformat()
    series = db.get_metric_series(metric_key, start, date)
    return series[-1] if series else None
