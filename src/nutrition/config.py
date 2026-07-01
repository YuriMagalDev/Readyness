_DEFAULTS = {
    "neat_factor": 1.3,
    "protein_g": 180,
    "fat_g": 60,
    "carb_rest_g": 130,
    "carb_train_g": 200,
    "deficit_floor": 900,
    "target_rate_low": -0.4,   # %/sem — ritmo alvo (perde mais)
    "target_rate_high": -0.3,  # %/sem — ritmo alvo (perde menos); acima disso = travado
    "fast_rate": -0.7,         # %/sem — abaixo disso = rápido demais
    "bf_fat_frac": 0.85,       # fração da perda que é gordura
    "kcal_adjust": 0,          # ajuste aplicado (proposto+confirmado)
    "ea_low": 25,
    "ea_ok": 30,
    "ex_kcal_treino": 300,
    "ex_kcal_corrida": 400,
}


def nutrition_config(profile: dict) -> dict:
    peso = float(profile.get("peso_kg") or 0)
    bf = float(profile.get("percentual_gordura") or 0)
    over = dict(profile.get("nutricao") or {})
    cfg = {**_DEFAULTS, **over}
    cfg["peso_kg"] = peso
    cfg["percentual_gordura"] = bf
    cfg["lbm_kg"] = peso * (1 - bf / 100)
    return cfg
