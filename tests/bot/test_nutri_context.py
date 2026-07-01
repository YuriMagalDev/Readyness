from bot.nutrition_format import format_nutri_context


def test_contexto_com_dados():
    y = {
        "eaten": {"kcal": 2300, "p": 130},
        "ea": {"ea": 27.4, "faixa": "amarelo"},
        "balance": {"saldo": -500},
        "protein_target": 165,
    }
    txt = format_nutri_context(y)
    assert txt is not None
    assert "não muda o veredito" in txt
    assert "🟡" in txt
    assert "130/165g" in txt and "faltaram 35" in txt
    assert "−500 kcal" in txt


def test_sem_refeicao_retorna_none():
    assert format_nutri_context({"eaten": {"kcal": 0, "p": 0}, "ea": {}, "protein_target": 165}) is None
    assert format_nutri_context(None) is None


def test_proteina_batida_sem_faltaram():
    y = {"eaten": {"kcal": 2500, "p": 170}, "ea": {"ea": 31, "faixa": "verde"},
         "balance": {"saldo": None}, "protein_target": 165}
    txt = format_nutri_context(y)
    assert "🟢" in txt and "170/165g" in txt
    assert "faltaram" not in txt
    assert "saldo" not in txt   # saldo None -> omitido


from bot.nutrition_format import format_macros_today


def test_macros_today_falta_e_ok():
    today = {
        "totals": {"kcal": 1200, "p": 90, "c": 60, "g": 60},
        "target": {"kcal": 1780, "protein_g": 180, "carb_g": 130, "fat_g": 60},
        "ea": {"ea": 15.9, "faixa": "vermelho"},
        "training": False,
    }
    txt = format_macros_today(today)
    assert "Macros de hoje" in txt and "descanso" in txt
    assert "Proteína: 90/180g (falta 90)" in txt
    assert "Gordura: 60/60g ✅" in txt        # bateu
    assert "🔴" in txt


def test_macros_today_treino_label():
    today = {"totals": {"kcal": 0, "p": 0, "c": 0, "g": 0},
             "target": {"kcal": 2060, "protein_g": 180, "carb_g": 200, "fat_g": 60},
             "ea": {}, "training": True}
    assert "treino" in format_macros_today(today)
