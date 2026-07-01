from src.nutrition.config import nutrition_config


def test_defaults_e_lbm():
    cfg = nutrition_config({"peso_kg": 108, "percentual_gordura": 30})
    assert round(cfg["lbm_kg"], 1) == 75.6
    assert cfg["neat_factor"] == 1.3
    assert cfg["protein_g"] == 180
    assert cfg["fat_g"] == 60
    assert cfg["ea_low"] == 25 and cfg["ea_ok"] == 30


def test_novos_defaults():
    cfg = nutrition_config({"peso_kg": 108, "percentual_gordura": 30})
    assert cfg["protein_g"] == 180
    assert cfg["carb_rest_g"] == 130
    assert cfg["carb_train_g"] == 200
    assert cfg["deficit_floor"] == 900
    assert cfg["bf_fat_frac"] == 0.85
    assert cfg["kcal_adjust"] == 0


def test_perfil_sobrescreve_defaults():
    cfg = nutrition_config({"peso_kg": 100, "percentual_gordura": 20,
                            "nutricao": {"carb_rest_g": 100, "protein_g": 200}})
    assert cfg["carb_rest_g"] == 100
    assert cfg["protein_g"] == 200
    assert cfg["fat_g"] == 60  # não sobrescrito → default
    assert round(cfg["lbm_kg"], 1) == 80.0


def test_ex_kcal_defaults_presentes():
    cfg = nutrition_config({"peso_kg": 108, "percentual_gordura": 30})
    assert cfg["ex_kcal_treino"] == 300
    assert cfg["ex_kcal_corrida"] == 400


def test_ex_kcal_sobrescreve():
    cfg = nutrition_config({"peso_kg": 100, "percentual_gordura": 20,
                            "nutricao": {"ex_kcal_treino": 250, "ex_kcal_corrida": 450}})
    assert cfg["ex_kcal_treino"] == 250
    assert cfg["ex_kcal_corrida"] == 450
