from dataclasses import dataclass


@dataclass(frozen=True)
class MetricSpec:
    key: str
    label: str
    unidade: str
    dominio: str        # prontidao | recuperacao | atividade | corpo | checkin
    cadencia: str       # diaria | corpo | fitness | evento
    source_default: str = "garmin"


# Janela de frescor em dias. evento é tratado à parte (sempre fresco se existe).
CADENCE_WINDOW_DAYS = {"diaria": 0, "corpo": 7, "fitness": 14}

CATALOG = [
    # Prontidão / treino
    MetricSpec("training_readiness", "Training readiness", "", "prontidao", "diaria"),
    MetricSpec("vo2max", "VO2max", "", "prontidao", "fitness"),
    MetricSpec("endurance_score", "Endurance score", "", "prontidao", "fitness"),
    MetricSpec("training_status", "Training status", "", "prontidao", "diaria"),  # FR55: sem endpoint estável — fica ausente até confirmar
    MetricSpec("race_pred_5k", "Prova 5k", "time", "prontidao", "fitness", "estimado"),
    MetricSpec("race_pred_10k", "Prova 10k", "time", "prontidao", "fitness", "estimado"),
    MetricSpec("race_pred_21k", "Prova 21k", "time", "prontidao", "fitness", "estimado"),
    MetricSpec("race_pred_42k", "Prova 42k", "time", "prontidao", "fitness", "estimado"),
    # Recuperação / sono
    MetricSpec("sleep_hours", "Sono", " h", "recuperacao", "diaria"),
    MetricSpec("sleep_deep_h", "Sono profundo", " h", "recuperacao", "diaria"),
    MetricSpec("sleep_light_h", "Sono leve", " h", "recuperacao", "diaria"),
    MetricSpec("sleep_rem_h", "Sono REM", " h", "recuperacao", "diaria"),
    MetricSpec("resting_hr", "FC repouso", " bpm", "recuperacao", "diaria"),
    MetricSpec("hrv_overnight", "HRV noturno", " ms", "recuperacao", "diaria"),
    MetricSpec("body_battery_high", "Body Battery alta", "", "recuperacao", "diaria"),
    MetricSpec("body_battery_low", "Body Battery baixa", "", "recuperacao", "diaria"),
    MetricSpec("stress_avg", "Stress médio", "", "recuperacao", "diaria"),
    MetricSpec("stress_max", "Stress máx", "", "recuperacao", "diaria"),
    MetricSpec("respiration_avg", "Respiração", " rpm", "recuperacao", "diaria"),
    MetricSpec("spo2_avg", "SpO2", "%", "recuperacao", "diaria"),
    # Atividade diária
    MetricSpec("steps", "Passos", "", "atividade", "diaria"),
    MetricSpec("floors", "Andares", "", "atividade", "diaria"),
    MetricSpec("intensity_minutes", "Min. intensidade", " min", "atividade", "diaria"),
    MetricSpec("calories_total", "Calorias", " kcal", "atividade", "diaria"),
    # Corpo
    MetricSpec("weight_kg", "Peso", " kg", "corpo", "corpo"),
    MetricSpec("body_fat_pct", "% gordura", "%", "corpo", "corpo"),
    MetricSpec("lean_mass_kg", "Massa magra", " kg", "corpo", "corpo"),
    # Check-ins manuais (1-5)
    MetricSpec("hidratacao", "Hidratação", "", "checkin", "diaria", "manual"),
    MetricSpec("energia", "Energia/disposição", "", "checkin", "diaria", "manual"),
    MetricSpec("soreness", "Dor muscular", "", "checkin", "diaria", "manual"),
    MetricSpec("alimentacao", "Qualidade alimentação", "", "checkin", "diaria", "manual"),
    # Carga / tendência (computadas — sub-projeto 1)
    MetricSpec("acwr", "Carga aguda:crônica", "", "prontidao", "diaria", "computed"),
    MetricSpec("training_monotony", "Monotonia", "", "prontidao", "diaria", "computed"),
    MetricSpec("resting_hr_baseline", "FC repouso (base 30d)", " bpm", "recuperacao", "diaria", "computed"),
]

CATALOG_BY_KEY = {m.key: m for m in CATALOG}
DOMAIN_ORDER = ["prontidao", "recuperacao", "atividade", "corpo", "checkin"]


def by_domain(dominio: str) -> list:
    return [m for m in CATALOG if m.dominio == dominio]
