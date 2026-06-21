from bot.messages import format_saldo, format_insights, sleep_insight

VER = {"status": "amarelo", "motivo": "FC repouso elevada", "recomendacao": "Treino leve; durma cedo."}
MET = {"resting_hr_today": 55, "resting_hr_avg_7d": 60.9, "morning_battery_avg": 38,
       "sleep_debt_hours": 2.4, "run_sessions_7d": 3}
SLEEP = {"hours": 6.3, "deep_h": 0.8, "rem_h": 1.2, "debt_h": 2.4, "target": 7.0}


def test_saldo_tem_semaforo_palavra_e_recomendacao():
    txt = format_saldo(VER, MET, sleep=SLEEP, wake="06:12")
    assert "06:12" in txt
    assert "🟡" in txt and "Pegue leve" in txt       # semáforo + palavra do veredito
    assert "durma cedo" in txt.lower()
    assert "55" in txt                                # FC repouso
    assert "corrida" not in txt.lower()               # corridas removidas da inicial


def test_saldo_inclui_insight_da_noite():
    txt = format_saldo(VER, MET, sleep=SLEEP)
    assert "Sua noite" in txt
    assert "6h18" in txt                              # 6.3h -> 6h18
    assert "profundo" in txt.lower()
    assert "dívida" not in txt.lower()                # sem jargão; déficit explicado


def test_sleep_insight_sem_dados():
    assert "sincronize" in sleep_insight({}).lower()


def test_saldo_tolera_metricas_ausentes():
    vazio = {"resting_hr_today": None, "resting_hr_avg_7d": None, "morning_battery_avg": None}
    txt = format_saldo(VER, vazio, sleep={})          # não pode lançar
    assert "Pegue leve" in txt
    assert "sincronize" in txt.lower()                # fallback do insight da noite


def test_insights_vazio():
    assert "indisponível" in format_insights([]).lower()


def test_insights_lista():
    ins = [{"texto": "FC alta + bateria baixa", "metricas_usadas": [
        {"label": "FC repouso", "valor": 55, "unidade": " bpm"}]}]
    txt = format_insights(ins)
    assert "FC alta" in txt and "FC repouso" in txt and "55" in txt


def test_saldo_mostra_score_e_fatores():
    veredito = {
        "status": "amarelo", "score": 58, "motivo": "dor muscular 4",
        "recomendacao": "Treino leve.",
        "fatores": [{"chave": "soreness", "label": "Dor muscular", "valor": 4, "desconto": 18}],
    }
    txt = format_saldo(veredito, MET)
    assert "58/100" in txt
    assert "Dor muscular" in txt


def test_saldo_sem_score_degrada():
    veredito = {"status": "verde", "motivo": "Métricas normais", "recomendacao": "Pode treinar."}
    txt = format_saldo(veredito, MET)   # sem 'score'/'fatores'
    assert "/100" not in txt                       # não quebra, só omite


def test_format_alert_cada_kind():
    from bot import messages
    hr = messages.format_alert({"kind": "hr_rising", "dias": 3, "baseline": 50.0,
                                "valores": [54, 55, 56]})
    assert "FC repouso" in hr
    acwr = messages.format_alert({"kind": "acwr_risk", "acwr": 1.8})
    assert "1.8" in acwr and "risco" in acwr.lower()
    over = messages.format_alert({"kind": "overreaching",
                                  "veredito": {"motivo": "FC alta + carga + dor"}})
    assert "Overreaching" in over
    # kind desconhecido não quebra
    assert isinstance(messages.format_alert({"kind": "zzz"}), str)


def test_format_briefing():
    from bot import messages
    txt = messages.format_briefing({"km_7d": 13.0, "sessoes": 2, "acwr": 1.2,
                                    "sono_medio": 7.0, "fc_max": 190,
                                    "recomendacao": "Mantenha a carga atual."})
    assert "Resumo da semana" in txt and "13.0" in txt
    # campos None viram em-dash, não quebra
    vazio = messages.format_briefing({"km_7d": 0.0, "sessoes": 0, "acwr": None,
                                      "sono_medio": None, "fc_max": 190,
                                      "recomendacao": "Mantenha a carga atual."})
    assert "—" in vazio
