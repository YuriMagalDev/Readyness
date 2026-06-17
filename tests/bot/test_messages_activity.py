from bot import messages


def test_format_activity_cabecalho_e_insight():
    act = {"name": "Corrida matinal", "distance_m": 5230, "duration_min": 28.5,
           "pace_min_km": 5.45, "avg_hr": 152.3}
    txt = messages.format_activity(act, "Ritmo firme, FC controlada.")
    assert "<b>Corrida matinal</b>" in txt
    assert "5.23 km" in txt
    assert "28:30" in txt          # 28.5 min -> 28:30
    assert "5:27 /km" in txt       # 5.45 min/km -> 5:27
    assert "152 bpm" in txt
    assert "Ritmo firme" in txt


def test_format_activity_tolera_none():
    act = {"name": None, "distance_m": None, "duration_min": None,
           "pace_min_km": None, "avg_hr": None}
    txt = messages.format_activity(act, "ok")
    assert "—" in txt              # campos ausentes viram em-dash
    assert "ok" in txt             # insight ainda sai
    assert "Corrida" in txt        # nome default
