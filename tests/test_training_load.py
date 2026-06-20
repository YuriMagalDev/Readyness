import math
import pytest
from src.training_load import session_trimp, estimate_hr_max, daily_load_series, RUN_TYPES, ewma


def test_trimp_com_fc_conhecida():
    act = {"duration_min": 30, "avg_hr": 150}
    carga, estimado = session_trimp(act, hr_rest=50, hr_max=190)
    assert carga == pytest.approx(54.05, abs=0.5)
    assert estimado is False


def test_trimp_clampa_hrr_acima_de_um():
    # avg_hr acima de hr_max não deve estourar (HRr clampa em 1.0)
    act = {"duration_min": 10, "avg_hr": 200}
    carga, estimado = session_trimp(act, hr_rest=50, hr_max=190)
    esperado = 10 * 1.0 * 0.64 * math.exp(1.92 * 1.0)
    assert carga == pytest.approx(esperado, abs=0.1)
    assert estimado is False


def test_trimp_sem_avg_hr_usa_duracao_estimado():
    act = {"duration_min": 40, "avg_hr": None}
    carga, estimado = session_trimp(act, hr_rest=50, hr_max=190)
    assert carga == 40.0
    assert estimado is True


def test_trimp_sem_duracao_zero_estimado():
    act = {"duration_min": None, "avg_hr": 150}
    carga, estimado = session_trimp(act, hr_rest=50, hr_max=190)
    assert carga == 0.0
    assert estimado is True


def test_hr_max_usa_observada_quando_maior():
    acts = [{"max_hr": 195}, {"max_hr": 188}, {"max_hr": None}]
    assert estimate_hr_max(acts, idade=25) == 195


def test_hr_max_usa_tanaka_quando_observada_menor():
    acts = [{"max_hr": 150}]
    assert estimate_hr_max(acts, idade=25) == 190  # 208 - 0.7*25 = 190.5 -> 190


def test_hr_max_sem_atividades_usa_tanaka():
    assert estimate_hr_max([], idade=25) == 190


def test_daily_load_agrupa_e_ignora_musculacao():
    acts = [
        {"date": "2026-06-20", "type": "running", "is_strength": 0,
         "duration_min": 30, "avg_hr": 150, "max_hr": 170},
        {"date": "2026-06-20", "type": "indoor_cardio", "is_strength": 1,
         "duration_min": 45, "avg_hr": 120, "max_hr": 140},
        {"date": "2026-06-19", "type": "treadmill_running", "is_strength": 0,
         "duration_min": 20, "avg_hr": None, "max_hr": None},
    ]
    series = daily_load_series(acts, {"2026-06-20": 50}, hr_max=190)
    assert set(series.keys()) == {"2026-06-20", "2026-06-19"}
    assert series["2026-06-20"] > 0          # só a corrida contou
    assert series["2026-06-19"] == 20.0      # fallback duração (sem FC)


def test_run_types_exclui_cardio():
    assert "running" in RUN_TYPES
    assert "indoor_cardio" not in RUN_TYPES


def test_ewma_serie_constante_retorna_constante():
    series = {"2026-06-18": 5.0, "2026-06-19": 5.0, "2026-06-20": 5.0}
    assert ewma(series, "2026-06-20", tau_days=1, span_days=3) == pytest.approx(5.0)


def test_ewma_preenche_faltantes_com_zero():
    # span 3 dias terminando em 06-20; só 06-20 tem 10; α=2/(1+1)=1.0
    # loads (antigo->novo) = [0, 0, 10]; α=1 => ewma = último = 10
    series = {"2026-06-20": 10.0}
    assert ewma(series, "2026-06-20", tau_days=1, span_days=3) == pytest.approx(10.0)


def test_ewma_alpha_meio():
    # α=2/(3+1)=0.5; loads=[0,0,10] -> 0; 0; 0.5*10+0.5*0=5.0
    series = {"2026-06-20": 10.0}
    assert ewma(series, "2026-06-20", tau_days=3, span_days=3) == pytest.approx(5.0)
