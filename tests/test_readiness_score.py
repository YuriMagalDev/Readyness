import pytest
from src.readiness_score import (
    _deduction_acwr, _deduction_hr, _deduction_soreness,
    _deduction_sleep, _deduction_energia, _deduction_battery,
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
