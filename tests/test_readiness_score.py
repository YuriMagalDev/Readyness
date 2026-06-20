import pytest
from src.readiness_score import (
    _deduction_acwr, _deduction_hr, _deduction_soreness,
    _deduction_sleep, _deduction_energia, _deduction_battery,
    compute_readiness,
)


def test_acwr_so_penaliza_risco():
    assert _deduction_acwr(None) == (0, None)
    assert _deduction_acwr(1.0)[0] == 0          # zona otimo
    assert _deduction_acwr(0.5)[0] == 0          # zona baixo (fresco)
    d, fator = _deduction_acwr(1.8)              # zona risco
    assert d == 35 and fator["chave"] == "acwr" and fator["desconto"] == 35


def test_hr_por_desvio_da_baseline():
    assert _deduction_hr(None, 50) == (0, None)
    assert _deduction_hr(50, None) == (0, None)
    assert _deduction_hr(52, 50) == (0, None)    # desvio +2
    assert _deduction_hr(54, 50)[0] == 12        # desvio +4 (faixa 3..5)
    assert _deduction_hr(55, 50)[0] == 12        # desvio +5 (inclusivo)
    assert _deduction_hr(57, 50)[0] == 25        # desvio +7 (>5)


def test_soreness_faixas():
    assert _deduction_soreness(None) == (0, None)
    assert _deduction_soreness(2) == (0, None)
    assert _deduction_soreness(3)[0] == 10
    assert _deduction_soreness(4)[0] == 18
    assert _deduction_soreness(5)[0] == 25


def test_sleep_faixas():
    assert _deduction_sleep(1.5) == (0, None)
    assert _deduction_sleep(2.0)[0] == 10
    assert _deduction_sleep(4.0)[0] == 10
    assert _deduction_sleep(5.0)[0] == 20


def test_energia_faixas():
    assert _deduction_energia(None) == (0, None)
    assert _deduction_energia(5) == (0, None)
    assert _deduction_energia(3)[0] == 6
    assert _deduction_energia(2)[0] == 12
    assert _deduction_energia(1)[0] == 15


def test_battery_faixas():
    assert _deduction_battery(None) == (0, None)
    assert _deduction_battery(80) == (0, None)
    assert _deduction_battery(40)[0] == 8
    assert _deduction_battery(20)[0] == 15


def test_dia_perfeito_score_100_verde():
    out = compute_readiness({})
    assert out["score"] == 100
    assert out["status"] == "verde"
    assert out["motivo"] == "Métricas normais"
    assert out["fatores"] == []
    assert out["overreaching"] is False


def test_faixas_de_status():
    # soreness 3 (-10) -> 90 verde
    assert compute_readiness({"soreness": 3})["status"] == "verde"
    # descontos somando 31 -> 69 amarelo (soreness 5=25 + energia 3=6)
    out = compute_readiness({"soreness": 5, "energia": 3})
    assert out["score"] == 69 and out["status"] == "amarelo"
    # somando 61 -> 39 vermelho (acwr risco 35 + soreness 25 + ... ajuste)
    out = compute_readiness({"acwr": 1.8, "soreness": 5})  # 35+25=60 -> 40 amarelo
    assert out["score"] == 40 and out["status"] == "amarelo"
    out = compute_readiness({"acwr": 1.8, "soreness": 5, "energia": 3})  # 60+6=66 -> 34 vermelho
    assert out["score"] == 34 and out["status"] == "vermelho"


def test_clamp_nao_negativo():
    out = compute_readiness({
        "acwr": 1.8, "resting_hr_today": 70, "resting_hr_baseline": 50,
        "soreness": 5, "sleep_debt_hours": 6, "energia": 1, "morning_battery_avg": 10,
    })
    assert out["score"] == 0
    assert out["status"] == "vermelho"


def test_fatores_ordenados_e_motivo():
    out = compute_readiness({"soreness": 4, "sleep_debt_hours": 3, "energia": 3})
    # descontos: soreness 18, sleep 10, energia 6 -> ordenados desc
    descontos = [f["desconto"] for f in out["fatores"]]
    assert descontos == sorted(descontos, reverse=True)
    assert out["fatores"][0]["chave"] == "soreness"
    assert "dor muscular" in out["motivo"].lower()


def test_ausencia_nao_penaliza():
    # só FC ruim; resto None -> desconta só FC
    out = compute_readiness({"resting_hr_today": 60, "resting_hr_baseline": 50})
    assert len(out["fatores"]) == 1 and out["fatores"][0]["chave"] == "resting_hr"


def test_overreaching_crava_vermelho():
    ctx = {
        "resting_hr_today": 58, "resting_hr_baseline": 50,  # desvio +8 (>5)
        "acwr": 1.8,                                         # zona risco
        "soreness": 4,                                       # >=4
        "morning_battery_avg": 90, "energia": 5,             # resto ótimo
    }
    out = compute_readiness(ctx)
    assert out["overreaching"] is True
    assert out["status"] == "vermelho"
    assert "overreaching" in out["motivo"].lower()
