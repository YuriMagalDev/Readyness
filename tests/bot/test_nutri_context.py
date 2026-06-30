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
