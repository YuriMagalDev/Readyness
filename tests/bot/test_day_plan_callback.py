from bot.handlers import parse_day_plan_callback


def test_mapeia_callbacks():
    assert parse_day_plan_callback("dp:treino") == (1, 0)
    assert parse_day_plan_callback("dp:corrida") == (0, 1)
    assert parse_day_plan_callback("dp:ambos") == (1, 1)
    assert parse_day_plan_callback("dp:descanso") == (0, 0)
