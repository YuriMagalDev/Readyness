import math
import pytest
from src.training_load import session_trimp


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
