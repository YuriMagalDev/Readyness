import datetime
from src.metric_catalog import CADENCE_WINDOW_DAYS


def compute_status(cadencia: str, source: str, measured_at, today: datetime.date) -> str:
    """Calcula o badge de confiança de uma métrica na leitura.
    Retorna: estimado | ausente | fresco | velho."""
    if source == "estimado":
        return "estimado"
    if measured_at is None:
        return "ausente"
    if cadencia == "evento":
        return "fresco"
    measured_date = datetime.date.fromisoformat(measured_at[:10])
    age_days = (today - measured_date).days
    window = CADENCE_WINDOW_DAYS[cadencia]
    return "fresco" if age_days <= window else "velho"
