_DEFAULTS = {
    "neat_factor": 1.3,
    "deficit_kcal": 500,
    "protein_g": 165,
    "fat_g": 60,
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
