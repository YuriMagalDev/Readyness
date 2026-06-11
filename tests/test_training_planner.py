import json
from unittest.mock import patch
from src.training_planner import TrainingPlanner

BASE_CONTEXT = {
    "resting_hr_avg_7d": 52.0,
    "morning_battery_avg": 65.0,
    "sleep_debt_hours": 0.0,
    "recent_activities": [],
    "strength_sessions_7d": 1,
    "run_sessions_7d": 2,
}

MOCK_PLAN = json.dumps([
    {"dia": "Segunda", "tipo": "corrida", "descricao": "Corrida leve 5km", "duracao": 40, "intensidade": "leve"},
    {"dia": "Terça", "tipo": "musculação", "descricao": "Peito e tríceps", "duracao": 60, "intensidade": "moderada"},
    {"dia": "Quarta", "tipo": "corrida", "descricao": "Corrida moderada 7km", "duracao": 50, "intensidade": "moderada"},
    {"dia": "Quinta", "tipo": "descanso", "descricao": "Recuperação ativa", "duracao": 0, "intensidade": "nenhuma"},
    {"dia": "Sexta", "tipo": "corrida", "descricao": "Corrida intervalada", "duracao": 45, "intensidade": "alta"},
    {"dia": "Sábado", "tipo": "musculação", "descricao": "Costas e bíceps", "duracao": 60, "intensidade": "moderada"},
    {"dia": "Domingo", "tipo": "descanso", "descricao": "Descanso total", "duracao": 0, "intensidade": "nenhuma"},
])

@patch("src.training_planner.ask_coach", return_value=MOCK_PLAN)
def test_plan_has_7_days(mock_ask):
    planner = TrainingPlanner()
    plan = planner.generate_weekly_plan(BASE_CONTEXT)
    assert len(plan) == 7

@patch("src.training_planner.ask_coach", return_value=MOCK_PLAN)
def test_plan_has_minimum_3_run_days(mock_ask):
    planner = TrainingPlanner()
    plan = planner.generate_weekly_plan(BASE_CONTEXT)
    run_days = [d for d in plan if d["tipo"] == "corrida"]
    assert len(run_days) >= 3

@patch("src.training_planner.ask_coach", return_value=MOCK_PLAN)
def test_plan_calls_sonnet(mock_ask):
    planner = TrainingPlanner()
    planner.generate_weekly_plan(BASE_CONTEXT)
    call_kwargs = mock_ask.call_args
    depth = call_kwargs[1].get("depth") or call_kwargs[0][2]
    assert depth == "deep"

@patch("src.training_planner.ask_coach", return_value=MOCK_PLAN)
def test_plan_items_have_required_fields(mock_ask):
    planner = TrainingPlanner()
    plan = planner.generate_weekly_plan(BASE_CONTEXT)
    for item in plan:
        assert "dia" in item
        assert "tipo" in item
        assert "descricao" in item
        assert "duracao" in item
        assert "intensidade" in item
