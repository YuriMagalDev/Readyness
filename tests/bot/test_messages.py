from bot.messages import format_saldo, format_insights

VER = {"status": "amarelo", "motivo": "Dívida de sono 2.4h", "recomendacao": "Durma cedo."}
MET = {"resting_hr_today": 55, "resting_hr_avg_7d": 60.9, "morning_battery_avg": 38,
       "sleep_debt_hours": 2.4, "run_sessions_7d": 3}

def test_saldo_tem_veredito_e_metricas():
    txt = format_saldo(VER, MET, wake="06:12")
    assert "06:12" in txt
    assert "🟡" in txt and "Durma cedo" in txt
    assert "55" in txt and "-5.9" in txt
    assert "2.4" in txt
    assert "3" in txt

def test_saldo_tolera_metricas_ausentes():
    vazio = {"resting_hr_today": None, "resting_hr_avg_7d": None, "morning_battery_avg": None,
             "sleep_debt_hours": None, "run_sessions_7d": 0}
    txt = format_saldo(VER, vazio)  # não pode lançar
    assert "FC repouso  —" in txt
    assert "Body Battery —" in txt


def test_insights_vazio():
    assert "indisponível" in format_insights([]).lower()

def test_insights_lista():
    ins = [{"texto": "FC alta + bateria baixa", "metricas_usadas": [
        {"label": "FC repouso", "valor": 55, "unidade": " bpm"}]}]
    txt = format_insights(ins)
    assert "FC alta" in txt and "FC repouso" in txt and "55" in txt
