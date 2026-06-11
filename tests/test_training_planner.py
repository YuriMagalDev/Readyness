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

MOCK_PLAN = json.dumps({
    "corrida": [
        {"dia": "Segunda", "descricao": "Corrida leve 5km", "duracao": 40, "intensidade": "leve"},
        {"dia": "Quarta", "descricao": "Corrida moderada 7km", "duracao": 50, "intensidade": "moderada"},
        {"dia": "Sexta", "descricao": "Corrida intervalada", "duracao": 45, "intensidade": "alta"},
    ],
    "musculacao": [
        {"dia": "Segunda", "descricao": "Peito e tríceps", "duracao": 60, "intensidade": "moderada"},
        {"dia": "Quinta", "descricao": "Costas e bíceps", "duracao": 60, "intensidade": "moderada"},
    ],
})

@patch("src.training_planner.ask_coach", return_value=MOCK_PLAN)
def test_plan_returns_two_grids(mock_ask):
    plan = TrainingPlanner().generate_weekly_plan(BASE_CONTEXT)
    assert "corrida" in plan
    assert "musculacao" in plan

@patch("src.training_planner.ask_coach", return_value=MOCK_PLAN)
def test_plan_minimum_3_run_days(mock_ask):
    plan = TrainingPlanner().generate_weekly_plan(BASE_CONTEXT)
    assert len(plan["corrida"]) >= 3

@patch("src.training_planner.ask_coach", return_value=MOCK_PLAN)
def test_plan_calls_sonnet(mock_ask):
    TrainingPlanner().generate_weekly_plan(BASE_CONTEXT)
    call = mock_ask.call_args
    depth = call[1].get("depth") or call[0][2]
    assert depth == "deep"

@patch("src.training_planner.ask_coach", return_value=MOCK_PLAN)
def test_plan_items_have_required_fields(mock_ask):
    plan = TrainingPlanner().generate_weekly_plan(BASE_CONTEXT)
    for item in plan["corrida"] + plan["musculacao"]:
        assert "dia" in item
        assert "descricao" in item
        assert "duracao" in item
        assert "intensidade" in item

@patch("src.training_planner.ask_coach", return_value=MOCK_PLAN)
def test_same_day_run_and_strength_allowed(mock_ask):
    plan = TrainingPlanner().generate_weekly_plan(BASE_CONTEXT)
    run_days = {d["dia"] for d in plan["corrida"]}
    gym_days = {d["dia"] for d in plan["musculacao"]}
    assert "Segunda" in run_days
    assert "Segunda" in gym_days

@patch("src.training_planner.ask_coach", return_value=json.dumps({
    "corrida": [{"dia": "Segunda", "descricao": "x", "duracao": 30, "intensidade": "leve"}],
    "musculacao": [],
}))
def test_plan_raises_when_under_3_runs(mock_ask):
    import pytest
    with pytest.raises(ValueError):
        TrainingPlanner().generate_weekly_plan(BASE_CONTEXT)
