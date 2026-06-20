import math


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
