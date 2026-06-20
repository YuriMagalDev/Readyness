from src.training_load import acwr_zone

# Descontos (pontos tirados de 100). ACWR é o mais pesado.
ACWR_RISK_DED = 35
HR_MID_DED, HR_HIGH_DED = 12, 25          # desvio +3..+5 / >+5 bpm
SOR_DED = {3: 10, 4: 18, 5: 25}
SLEEP_MID_DED, SLEEP_HIGH_DED = 10, 20    # 2..4h / >4h
EN_DED = {3: 6, 2: 12, 1: 15}
BAT_MID_DED, BAT_HIGH_DED = 8, 15         # 25..49 / <25


def _fator(chave, label, valor, desconto):
    return {"chave": chave, "label": label, "valor": valor, "desconto": desconto}


def _deduction_acwr(acwr):
    if acwr is None:
        return 0, None
    if acwr_zone(acwr) == "risco":
        return ACWR_RISK_DED, _fator("acwr", "Carga (ACWR)", round(acwr, 2), ACWR_RISK_DED)
    return 0, None


def _deduction_hr(today, baseline):
    if today is None or baseline is None:
        return 0, None
    desvio = today - baseline
    if desvio > 5:
        d = HR_HIGH_DED
    elif desvio >= 3:
        d = HR_MID_DED
    else:
        return 0, None
    return d, _fator("resting_hr", "FC repouso", today, d)


def _deduction_soreness(v):
    if v is None or v not in SOR_DED:
        return 0, None
    return SOR_DED[v], _fator("soreness", "Dor muscular", v, SOR_DED[v])


def _deduction_sleep(debt):
    if debt is None:
        return 0, None
    if debt > 4:
        d = SLEEP_HIGH_DED
    elif debt >= 2:
        d = SLEEP_MID_DED
    else:
        return 0, None
    return d, _fator("sleep_debt", "Dívida de sono", f"{debt}h", d)


def _deduction_energia(v):
    if v is None or v not in EN_DED:
        return 0, None
    return EN_DED[v], _fator("energia", "Energia", v, EN_DED[v])


def _deduction_battery(b):
    if b is None:
        return 0, None
    if b < 25:
        d = BAT_HIGH_DED
    elif b < 50:
        d = BAT_MID_DED
    else:
        return 0, None
    return d, _fator("body_battery", "Body Battery", b, d)
