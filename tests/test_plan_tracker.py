import datetime
from src.plan_tracker import week_start_of, match_plan

PLAN = {
    "corrida": [
        {"dia": "Segunda", "descricao": "Corrida leve", "duracao": 40, "intensidade": "leve"},
        {"dia": "Quarta", "descricao": "Corrida longa", "duracao": 60, "intensidade": "moderada"},
    ],
    "musculacao": [
        {"dia": "Segunda", "descricao": "Peito", "duracao": 60, "intensidade": "moderada"},
    ],
}


def test_week_start_is_monday():
    # 2026-06-11 é quinta → segunda da semana = 2026-06-08
    assert week_start_of(datetime.date(2026, 6, 11)) == "2026-06-08"
    assert week_start_of(datetime.date(2026, 6, 8)) == "2026-06-08"
    assert week_start_of(datetime.date(2026, 6, 14)) == "2026-06-08"  # domingo


def test_match_marks_done_when_activity_exists():
    # segunda 2026-06-08: corrida feita
    acts = [{"date": "2026-06-08", "type": "running", "is_strength": 0}]
    today = datetime.date(2026, 6, 10)  # quarta
    res = match_plan(PLAN, acts, today, week_start="2026-06-08")
    seg_corrida = next(s for s in res["corrida"] if s["dia"] == "Segunda")
    assert seg_corrida["status"] == "feito"
    assert seg_corrida["date"] == "2026-06-08"


def test_match_marks_missed_when_past_and_no_activity():
    acts = []
    today = datetime.date(2026, 6, 10)  # quarta
    res = match_plan(PLAN, acts, today, week_start="2026-06-08")
    seg = next(s for s in res["corrida"] if s["dia"] == "Segunda")
    assert seg["status"] == "furou"  # segunda já passou, sem atividade


def test_match_marks_pending_when_future():
    acts = []
    today = datetime.date(2026, 6, 8)  # segunda
    res = match_plan(PLAN, acts, today, week_start="2026-06-08")
    qua = next(s for s in res["corrida"] if s["dia"] == "Quarta")
    assert qua["status"] == "pendente"  # quarta ainda no futuro


def test_match_strength_uses_is_strength_flag():
    acts = [{"date": "2026-06-08", "type": "indoor_cardio", "is_strength": 1}]
    today = datetime.date(2026, 6, 10)
    res = match_plan(PLAN, acts, today, week_start="2026-06-08")
    seg_musc = next(s for s in res["musculacao"] if s["dia"] == "Segunda")
    assert seg_musc["status"] == "feito"


def test_match_run_not_matched_by_strength_activity():
    # só musculação na segunda → corrida da segunda não conta
    acts = [{"date": "2026-06-08", "type": "indoor_cardio", "is_strength": 1}]
    today = datetime.date(2026, 6, 10)
    res = match_plan(PLAN, acts, today, week_start="2026-06-08")
    seg_corrida = next(s for s in res["corrida"] if s["dia"] == "Segunda")
    assert seg_corrida["status"] == "furou"


def test_match_today_counts_as_pending_if_no_activity():
    acts = []
    today = datetime.date(2026, 6, 8)  # segunda = hoje
    res = match_plan(PLAN, acts, today, week_start="2026-06-08")
    seg = next(s for s in res["corrida"] if s["dia"] == "Segunda")
    assert seg["status"] == "pendente"  # hoje ainda dá tempo
