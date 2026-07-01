from src.nutrition.adaptive import (
    trend_kg, weekly_rate_pct, derive_bf,
    is_adherent_day, week_adherence_ok, propose_adjustment,
)
from src.nutrition.config import nutrition_config

CFG = nutrition_config({"peso_kg": 108, "percentual_gordura": 30})


# ── tendência / ritmo ──────────────────────────────────────────────────────────

def test_trend_media_ultimos():
    assert trend_kg([108.0, 107.4, 107.1], window=3) == round((108.0+107.4+107.1)/3, 2)
    assert trend_kg([109, 108, 107.4, 107.1], window=3) == round((108+107.4+107.1)/3, 2)


def test_trend_poucos_pontos():
    assert trend_kg([]) is None
    assert trend_kg([107.4]) == 107.4


def test_rate_none_com_um_ponto():
    assert weekly_rate_pct([107.4]) is None


def test_rate_perda_negativa():
    r = weekly_rate_pct([108.0, 107.5, 107.0, 106.5])
    assert r is not None and -0.6 < r < -0.4


def test_rate_estavel_zero():
    assert abs(weekly_rate_pct([107.0, 107.0, 107.0])) < 0.05


# ── BF derivado ─────────────────────────────────────────────────────────────────

def test_derive_bf_perda_maioria_gordura():
    bf = derive_bf(108.0, 30.0, 107.0)
    assert round(bf, 2) == 29.49


def test_derive_bf_ganho_peso():
    bf = derive_bf(108.0, 30.0, 109.0)
    assert bf > 30.0


# ── aderência ───────────────────────────────────────────────────────────────────

def test_dia_aderente():
    target = {"protein_g": 180, "kcal": 1780}
    assert is_adherent_day({"p": 170, "kcal": 1800}, target) is True
    assert is_adherent_day({"p": 150, "kcal": 1800}, target) is False
    assert is_adherent_day({"p": 170, "kcal": 2100}, target) is False


def test_semana_aderente_5_de_7():
    assert week_adherence_ok([True]*5 + [False]*2) is True
    assert week_adherence_ok([True]*4 + [False]*3) is False


# ── proposta de ajuste ──────────────────────────────────────────────────────────

def test_proposta_rapido_demais_soma():
    p = propose_adjustment(-0.9, adherence_ok=False, cfg=CFG)
    assert p["action"] == "add" and p["delta_kcal"] == 100


def test_proposta_travado_com_aderencia_corta():
    p = propose_adjustment(-0.1, adherence_ok=True, cfg=CFG)
    assert p["action"] == "cut" and p["delta_kcal"] == -100


def test_proposta_travado_sem_aderencia_segue_plano():
    p = propose_adjustment(-0.1, adherence_ok=False, cfg=CFG)
    assert p["action"] == "follow_plan" and p["delta_kcal"] == 0


def test_proposta_no_ritmo_mantem():
    p = propose_adjustment(-0.35, adherence_ok=True, cfg=CFG)
    assert p["action"] == "hold" and p["delta_kcal"] == 0


def test_proposta_sem_rate_mantem():
    p = propose_adjustment(None, adherence_ok=True, cfg=CFG)
    assert p["action"] == "hold"
