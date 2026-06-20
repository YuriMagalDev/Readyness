import math
import datetime as _dt


def session_trimp(activity: dict, hr_rest: float, hr_max: float) -> tuple[float, bool]:
    """Carga TRIMP (Banister, homem). Retorna (carga, estimado).
    Sem avg_hr ou hr_max<=hr_rest: fallback duração (estimado=True)."""
    duration = activity.get("duration_min")
    if duration is None:
        return 0.0, True
    avg_hr = activity.get("avg_hr")
    if avg_hr is None or hr_max <= hr_rest:
        return float(duration), True
    hrr = (avg_hr - hr_rest) / (hr_max - hr_rest)
    hrr = max(0.0, min(1.0, hrr))
    trimp = duration * hrr * 0.64 * math.exp(1.92 * hrr)
    return trimp, False


def estimate_hr_max(activities: list, idade: int) -> int:
    """Estima FC máxima: maior observada se ≥ Tanaka, senão Tanaka."""
    tanaka = round(208 - 0.7 * idade)
    observados = [a.get("max_hr") for a in activities if a.get("max_hr")]
    if observados:
        return max(max(observados), tanaka)
    return tanaka


RUN_TYPES = {"running", "trail_running", "treadmill_running"}


def daily_load_series(activities: list, hr_rest_by_date: dict,
                      hr_max: float, default_rest: float = 60.0) -> dict:
    series: dict = {}
    for a in activities:
        if a.get("is_strength") or a.get("type") not in RUN_TYPES:
            continue
        d = a.get("date")
        if not d:
            continue
        hr_rest = hr_rest_by_date.get(d, default_rest)
        carga, _ = session_trimp(a, hr_rest, hr_max)
        series[d] = series.get(d, 0.0) + carga
    return series


def ewma(series_by_date: dict, end_date: str, tau_days: int, span_days: int) -> float:
    end = _dt.date.fromisoformat(end_date)
    alpha = 2.0 / (tau_days + 1)
    loads = []
    for i in range(span_days - 1, -1, -1):  # antigo -> novo
        d = (end - _dt.timedelta(days=i)).isoformat()
        loads.append(series_by_date.get(d, 0.0))
    val = loads[0]
    for x in loads[1:]:
        val = alpha * x + (1 - alpha) * val
    return val


def acwr_zone(ratio) -> str:
    if ratio is None:
        return "ausente"
    if ratio < 0.8:
        return "baixo"
    if ratio <= 1.5:
        return "otimo"
    return "risco"


def acwr(series_by_date: dict, end_date: str) -> tuple:
    agudo = ewma(series_by_date, end_date, tau_days=7, span_days=7)
    cronico = ewma(series_by_date, end_date, tau_days=28, span_days=28)
    if cronico == 0:
        return None, "ausente"
    ratio = agudo / cronico
    return ratio, acwr_zone(ratio)
