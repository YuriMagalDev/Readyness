from src.alerts import hr_rising, acwr_risk


def _rows(*vals):
    return [{"date": f"2026-06-{10+i:02d}", "value": v} for i, v in enumerate(vals)]


def test_hr_rising_dispara_3_dias_acima():
    # baseline 50, margin 3 -> limiar 53; últimos 3 todos >=53
    out = hr_rising(_rows(52, 54, 55, 56), baseline=50)
    assert out is not None and out["kind"] == "hr_rising"
    assert out["valores"] == [54, 55, 56] and out["dias"] == 3


def test_hr_rising_um_dia_abaixo_nao_dispara():
    assert hr_rising(_rows(54, 52, 56), baseline=50) is None   # 52 < 53


def test_hr_rising_sem_baseline_ou_poucos_dias():
    assert hr_rising(_rows(54, 55, 56), baseline=None) is None
    assert hr_rising(_rows(54, 55), baseline=50) is None       # só 2 dias


def test_acwr_risk():
    assert acwr_risk(1.8)["kind"] == "acwr_risk"               # zona risco (>1.5)
    assert acwr_risk(1.8)["acwr"] == 1.8
    assert acwr_risk(1.0) is None                              # ótimo
    assert acwr_risk(0.5) is None                              # baixo
    assert acwr_risk(None) is None
