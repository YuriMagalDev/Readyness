from src.training_load import acwr_zone


def hr_rising(hr_rows, baseline, days: int = 3, margin: int = 3):
    """Alerta se os últimos `days` dias de FC repouso ficaram cada um >= baseline+margin."""
    if baseline is None:
        return None
    vals = [r.get("value") for r in hr_rows if r.get("value") is not None]
    if len(vals) < days:
        return None
    ultimos = vals[-days:]
    if all(v >= baseline + margin for v in ultimos):
        return {"kind": "hr_rising", "dias": days,
                "baseline": round(baseline, 1), "valores": ultimos}
    return None


def acwr_risk(acwr):
    """Alerta quando a carga aguda:crônica entra na zona de risco (>1.5)."""
    if acwr is None:
        return None
    if acwr_zone(acwr) == "risco":
        return {"kind": "acwr_risk", "acwr": round(acwr, 2)}
    return None
