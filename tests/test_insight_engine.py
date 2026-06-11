import json
from unittest.mock import patch
from src.insight_engine import InsightEngine

ANALYTICS = {
    "resting_hr": {"trend": {"direction": "subindo", "slope": 0.5}, "series": []},
    "sleep_hours": {"trend": {"direction": "descendo", "slope": -0.2}, "series": []},
}


@patch("src.insight_engine.ask_coach", return_value=json.dumps(
    {"insights": ["FC repouso subindo", "Sono caindo"]}))
def test_trend_insights_parses(mock_ask):
    eng = InsightEngine()
    out = eng.trend_insights(ANALYTICS)
    assert out == ["FC repouso subindo", "Sono caindo"]


@patch("src.insight_engine.ask_coach", return_value=json.dumps({"insights": []}))
def test_trend_insights_uses_haiku(mock_ask):
    InsightEngine().trend_insights(ANALYTICS)
    call = mock_ask.call_args
    depth = call[1].get("depth") or call[0][2]
    assert depth == "quick"


@patch("src.insight_engine.ask_coach", return_value="not json at all")
def test_trend_insights_fallback_on_bad_json(mock_ask):
    out = InsightEngine().trend_insights(ANALYTICS)
    assert isinstance(out, list)
    assert len(out) == 1  # fallback message


@patch("src.insight_engine.ask_coach", return_value=json.dumps({"insight": "Treine leve hoje"}))
def test_daily_insight_parses(mock_ask):
    out = InsightEngine().daily_insight({"resting_hr_today": 55}, ANALYTICS)
    assert out == "Treine leve hoje"


@patch("src.insight_engine.ask_coach", return_value="boom")
def test_daily_insight_fallback(mock_ask):
    out = InsightEngine().daily_insight({}, ANALYTICS)
    assert isinstance(out, str)
    assert out != ""


@patch("src.insight_engine.ask_coach", return_value=json.dumps({"insight": "Pace consistente"}))
def test_activity_insight_parses(mock_ask):
    out = InsightEngine().activity_insight({"name": "Corrida", "pace_min_km": 5.0}, [])
    assert out == "Pace consistente"
