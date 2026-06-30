from bot.charts import nutrition_chart_png, nutrition_panel_png


def test_gera_png_nao_vazio():
    totals = {"kcal": 1840, "p": 98, "c": 210, "g": 48}
    target = {"kcal": 2500, "protein_g": 165, "carb_g": 290, "fat_g": 60}
    ea = {"ea": 32.0, "faixa": "verde"}
    buf = nutrition_chart_png(totals, target, ea, titulo="Hoje")
    data = buf.getvalue()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"     # assinatura PNG
    assert len(data) > 1000


def test_lida_com_alvo_zero():
    buf = nutrition_chart_png({"kcal": 0, "p": 0, "c": 0, "g": 0},
                              {"kcal": 0, "protein_g": 0, "carb_g": 0, "fat_g": 0},
                              {"ea": 0, "faixa": "vermelho"})
    assert buf.getvalue()[:8] == b"\x89PNG\r\n\x1a\n"


def _make_panel(*, burn=2900.0):
    today = {
        "totals": {"kcal": 1800, "p": 120, "c": 200, "g": 50},
        "target": {"kcal": 2500, "protein_g": 165, "carb_g": 280, "fat_g": 60},
        "ea": {"ea": 28.0, "faixa": "amarelo"},
        "training": True,
        "exercise_kcal": 400.0,
    }
    yesterday = {
        "eaten": {"kcal": 2200, "p": 140, "c": 220, "g": 55},
        "burn": burn,
        "active": 450.0 if burn is not None else None,
        "balance": {"saldo": 2200 - burn if burn is not None else None,
                    "eaten": 2200, "burn": burn},
        "ea": {"ea": 25.5, "faixa": "amarelo"},
        "protein_target": 165,
    }
    return {"today": today, "yesterday": yesterday}


def test_panel_png_nao_vazio():
    panel = _make_panel()
    buf = nutrition_panel_png(panel, titulo="Hoje (dia treino)")
    data = buf.getvalue()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(data) > 1000


def test_panel_png_sem_burn():
    """Panel renders even when yesterday has no Garmin snapshot (burn=None)."""
    panel = _make_panel(burn=None)
    buf = nutrition_panel_png(panel, titulo="Hoje (descanso)")
    data = buf.getvalue()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(data) > 1000
