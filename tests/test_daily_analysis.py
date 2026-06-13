import json
from unittest.mock import MagicMock, patch
from src.daily_analysis import DailyAnalysis

METRICS = {
    "date": "2026-06-13",
    "dominios": {
        "recuperacao": [
            {"key": "resting_hr", "label": "FC repouso", "value": 58, "unidade": " bpm",
             "measured_at": "2026-06-13T00:00", "status": "fresco", "source": "garmin"},
            {"key": "hrv_overnight", "label": "HRV noturno", "value": None, "unidade": " ms",
             "measured_at": None, "status": "ausente", "source": "garmin"},
        ],
        "prontidao": [], "atividade": [], "corpo": [], "checkin": [],
    },
}


@patch("src.daily_analysis.ask_coach", return_value=json.dumps(
    {"insights": [{"texto": "FC subiu.", "metricas_usadas": ["resting_hr"]}]}))
def test_insights_resolves_valid_key(mock_ask):
    eng = DailyAnalysis(db=MagicMock())
    out = eng._insights(METRICS, force=True)
    assert len(out) == 1
    src = out[0]["metricas_usadas"][0]
    assert src["key"] == "resting_hr"
    assert src["valor"] == 58
    assert src["label"] == "FC repouso"
    assert src["status"] == "fresco"


@patch("src.daily_analysis.ask_coach", return_value=json.dumps(
    {"insights": [{"texto": "X.", "metricas_usadas": ["inexistente"]}]}))
def test_insights_drops_insight_with_no_valid_key(mock_ask):
    eng = DailyAnalysis(db=MagicMock())
    out = eng._insights(METRICS, force=True)
    assert out == []


@patch("src.daily_analysis.ask_coach", return_value=json.dumps(
    {"insights": [{"texto": "Y.", "metricas_usadas": ["resting_hr", "inexistente"]}]}))
def test_insights_filters_invalid_keeps_valid(mock_ask):
    eng = DailyAnalysis(db=MagicMock())
    out = eng._insights(METRICS, force=True)
    assert len(out) == 1
    assert [s["key"] for s in out[0]["metricas_usadas"]] == ["resting_hr"]


@patch("src.daily_analysis.ask_coach", return_value="not json")
def test_insights_empty_on_llm_failure(mock_ask):
    eng = DailyAnalysis(db=MagicMock())
    assert eng._insights(METRICS, force=True) == []


@patch("src.daily_analysis.ask_coach", return_value=json.dumps({"insights": [
    {"texto": "Z.", "metricas_usadas": ["resting_hr"]}]}))
def test_insights_cache_hit_no_second_call(mock_ask):
    db = MagicMock()
    db.get_insight.side_effect = [None, [{"texto": "Z.", "metricas_usadas": [
        {"key": "resting_hr", "label": "FC repouso", "valor": 58, "unidade": " bpm", "status": "fresco"}]}]]
    eng = DailyAnalysis(db=db)
    eng._insights(METRICS)
    eng._insights(METRICS)
    assert mock_ask.call_count == 1
    db.set_insight.assert_called_once()
