from src.nutrition.config import nutrition_config
from src.nutrition.targets import (
    tdee_base, day_target, energy_availability,
    resolve_exercise_kcal, day_balance,
)

CFG = nutrition_config({"peso_kg": 108, "percentual_gordura": 30})


def test_tdee_base():
    # bmr = 370 + 21.6*75.6 = 2002.96 ; *1.3 = 2603.8
    assert round(tdee_base(CFG)) == 2604


def test_descanso_carbo_baixo():
    t = day_target(CFG, training=False)
    assert t["protein_g"] == 180
    assert t["fat_g"] == 60
    assert round(t["carb_g"]) == 130
    # intake = 180*4 + 60*9 + 130*4 = 720 + 540 + 520 = 1780
    assert round(t["kcal"]) == 1780


def test_treino_carbo_200_sem_piso():
    # só treino: gasto 2604+300=2904 ; intake carbo200 = 2060 ; deficit 844 < 900 -> fica 200
    t = day_target(CFG, training=True, exercise_kcal=300)
    assert round(t["carb_g"]) == 200
    assert round(t["kcal"]) == 2060


def test_piso_libera_carbo_dia_pesado():
    # treino+corrida: gasto 2604+700=3304 ; carbo200 daria deficit 1244 > 900
    # piso: intake alvo = 3304-900 = 2404 ; carbo = (2404-1260)/4 = 286
    t = day_target(CFG, training=True, exercise_kcal=700)
    assert round(t["carb_g"]) == 286
    assert round(t["kcal"]) == 2404


def test_kcal_adjust_desloca_carbo():
    cfg = nutrition_config({"peso_kg": 108, "percentual_gordura": 30})
    cfg["kcal_adjust"] = -100
    t = day_target(cfg, training=False)
    # 1780 - 100 = 1680 ; carbo 130 - 25 = 105
    assert round(t["kcal"]) == 1680
    assert round(t["carb_g"]) == 105


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
