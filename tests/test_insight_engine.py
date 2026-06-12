import json
from unittest.mock import patch, ANY as _ANY_DATE, MagicMock
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


@patch("src.insight_engine.ask_coach", return_value=json.dumps({"insight": "x"}))
def test_daily_insight_cache_hit_calls_api_once(mock_ask):
    db = MagicMock()
    db.get_insight.side_effect = [None, "x"]  # 1st miss, 2nd hit
    eng = InsightEngine(db=db)
    eng.daily_insight({"a": 1}, ANALYTICS)
    out2 = eng.daily_insight({"a": 1}, ANALYTICS)
    assert mock_ask.call_count == 1
    assert out2 == "x"
    db.set_insight.assert_called_once()


@patch("src.insight_engine.ask_coach", return_value=json.dumps({"insight": "x"}))
def test_daily_insight_force_recomputes(mock_ask):
    db = MagicMock()
    db.get_insight.return_value = "cached"
    eng = InsightEngine(db=db)
    out = eng.daily_insight({"a": 1}, ANALYTICS, force=True)
    assert mock_ask.call_count == 1
    assert out == "x"


@patch("src.insight_engine.ask_coach", return_value="boom")
def test_daily_insight_fallback_not_cached(mock_ask):
    db = MagicMock()
    db.get_insight.return_value = None
    eng = InsightEngine(db=db)
    eng.daily_insight({}, ANALYTICS)
    db.set_insight.assert_not_called()


@patch("src.insight_engine.ask_coach", return_value=json.dumps({"insights": ["a"]}))
def test_trend_insight_cache_hit(mock_ask):
    db = MagicMock()
    db.get_insight.side_effect = [None, ["a"]]
    eng = InsightEngine(db=db)
    eng.trend_insights(ANALYTICS, period=30)
    eng.trend_insights(ANALYTICS, period=30)
    assert mock_ask.call_count == 1


@patch("src.insight_engine.ask_coach", return_value=json.dumps({"insight": "ok"}))
def test_activity_insight_no_id_skips_cache(mock_ask):
    db = MagicMock()
    eng = InsightEngine(db=db)
    out = eng.activity_insight({"name": "C"}, [])  # no activity_id
    assert out == "ok"
    db.get_insight.assert_not_called()
    db.set_insight.assert_not_called()


@patch("src.insight_engine.ask_coach", return_value=json.dumps({"insight": "ok"}))
def test_activity_insight_cache_by_id(mock_ask):
    db = MagicMock()
    db.get_insight.side_effect = [None, "ok"]
    eng = InsightEngine(db=db)
    eng.activity_insight({"activity_id": 7, "name": "C"}, [])
    eng.activity_insight({"activity_id": 7, "name": "C"}, [])
    assert mock_ask.call_count == 1
    db.set_insight.assert_called_once_with("activity", "activity:7", "ok", _ANY_DATE)
