"""Cruza o plano semanal gerado com as atividades reais do history.db.
Cada sessão do plano vira feito / pendente / furou."""
import datetime

RUN_TYPES = {"running", "trail_running", "treadmill_running"}

# Mapa dia (primeiras 3 letras, sem acento) → offset a partir de segunda
_DIA_OFFSET = {
    "seg": 0, "ter": 1, "qua": 2, "qui": 3, "sex": 4, "sab": 5, "dom": 6,
}


def _dia_key(dia: str) -> str:
    base = dia.strip().lower()[:3]
    # normaliza acentos comuns (terça, sábado)
    return (base.replace("ç", "c").replace("á", "a").replace("â", "a"))


def week_start_of(day: datetime.date) -> str:
    """Segunda-feira da semana de `day` (ISO weekday: segunda=1)."""
    monday = day - datetime.timedelta(days=day.isoweekday() - 1)
    return monday.isoformat()


def _session_date(week_start: str, dia: str) -> str:
    start = datetime.date.fromisoformat(week_start)
    offset = _DIA_OFFSET.get(_dia_key(dia), 0)
    return (start + datetime.timedelta(days=offset)).isoformat()


def _has_activity(acts: list, date_str: str, strength: bool) -> bool:
    for a in acts:
        if a.get("date") != date_str:
            continue
        is_strength = bool(a.get("is_strength"))
        if strength and is_strength:
            return True
        if not strength and not is_strength and a.get("type") in RUN_TYPES:
            return True
    return False


def _status(date_str: str, today: datetime.date, done: bool) -> str:
    if done:
        return "feito"
    if datetime.date.fromisoformat(date_str) < today:
        return "furou"
    return "pendente"


def match_plan(plan: dict, activities: list, today: datetime.date, week_start: str) -> dict:
    out = {}
    for grade, strength in (("corrida", False), ("musculacao", True)):
        sessoes = []
        for s in plan.get(grade, []):
            date_str = _session_date(week_start, s.get("dia", "Segunda"))
            done = _has_activity(activities, date_str, strength)
            sessoes.append({**s, "date": date_str, "status": _status(date_str, today, done)})
        out[grade] = sessoes
    return out
