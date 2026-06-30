from src.nutrition.config import nutrition_config
from src.nutrition.targets import (
    tdee_base, day_target, energy_availability,
    resolve_exercise_kcal, day_balance,
)

CFG = nutrition_config({"peso_kg": 108, "percentual_gordura": 30})


def test_tdee_base():
    # bmr = 370 + 21.6*75.6 = 2002.96 ; *1.3 = 2603.8
    assert round(tdee_base(CFG)) == 2604


def test_dia_descanso():
    t = day_target(CFG, training=False)
    assert round(t["kcal"]) == 2104          # 2603.8 - 500
    assert t["protein_g"] == 165
    assert t["fat_g"] == 60
    # carb = (2104 - 165*4 - 60*9)/4 = (2104 - 660 - 540)/4 = 226
    assert round(t["carb_g"]) == 226


def test_dia_treino_soma_exercicio():
    t = day_target(CFG, training=True, exercise_kcal=400)
    assert round(t["kcal"]) == 2504          # descanso + 400
    assert round(t["carb_g"]) == 326         # +100g carbo


def test_energia_faixas():
    # (3004-400)/75.6 = 34.4 -> verde
    assert energy_availability(CFG, intake_kcal=3004, exercise_kcal=400)["faixa"] == "verde"
    # (2000-400)/75.6 = 21.2 -> vermelho
    assert energy_availability(CFG, intake_kcal=2000, exercise_kcal=400)["faixa"] == "vermelho"
    # (2300-400)/75.6 = 25.1 -> amarelo
    assert energy_availability(CFG, intake_kcal=2300, exercise_kcal=400)["faixa"] == "amarelo"


# ── resolve_exercise_kcal ──────────────────────────────────────────────────────

def test_resolve_usa_garmin_quando_presente():
    kcal = resolve_exercise_kcal(CFG, vai_treinar=True, vai_correr=True,
                                 garmin_active_kcal=550)
    assert kcal == 550.0


def test_resolve_ignora_garmin_zero():
    kcal = resolve_exercise_kcal(CFG, vai_treinar=True, vai_correr=True,
                                 garmin_active_kcal=0)
    assert kcal == 700.0  # 300 + 400


def test_resolve_sem_garmin_treino_e_corrida():
    kcal = resolve_exercise_kcal(CFG, vai_treinar=True, vai_correr=True)
    assert kcal == 700.0


def test_resolve_sem_garmin_so_treino():
    kcal = resolve_exercise_kcal(CFG, vai_treinar=True, vai_correr=False)
    assert kcal == 300.0


def test_resolve_descanso():
    kcal = resolve_exercise_kcal(CFG, vai_treinar=False, vai_correr=False)
    assert kcal == 0.0


# ── day_balance ────────────────────────────────────────────────────────────────

def test_day_balance_com_burn():
    b = day_balance(2500, 2800)
    assert b["saldo"] == -300.0
    assert b["eaten"] == 2500
    assert b["burn"] == 2800


def test_day_balance_sem_snapshot():
    b = day_balance(2000, None)
    assert b["saldo"] is None
    assert b["burn"] is None
    assert b["eaten"] == 2000
