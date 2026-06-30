def tdee_base(cfg: dict) -> float:
    bmr = 370 + 21.6 * cfg["lbm_kg"]
    return bmr * cfg["neat_factor"]


def day_target(cfg: dict, *, training: bool, exercise_kcal: float = 0.0) -> dict:
    kcal = tdee_base(cfg) - cfg["deficit_kcal"]
    if training:
        kcal += exercise_kcal
    protein_g = cfg["protein_g"]
    fat_g = cfg["fat_g"]
    carb_g = max(0.0, (kcal - protein_g * 4 - fat_g * 9) / 4)
    return {"kcal": kcal, "protein_g": protein_g, "fat_g": fat_g, "carb_g": carb_g}


def energy_availability(cfg: dict, intake_kcal: float, exercise_kcal: float) -> dict:
    lbm = cfg["lbm_kg"]
    ea = (intake_kcal - exercise_kcal) / lbm if lbm else 0.0
    if ea >= cfg["ea_ok"]:
        faixa = "verde"
    elif ea >= cfg["ea_low"]:
        faixa = "amarelo"
    else:
        faixa = "vermelho"
    return {"ea": ea, "faixa": faixa}
