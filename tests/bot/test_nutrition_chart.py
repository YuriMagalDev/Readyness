from bot.charts import nutrition_chart_png


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
