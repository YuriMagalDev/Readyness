import io
from bot.charts import recovery_chart_png

def test_gera_png():
    trends = {"period": 7, "metrics": {
        "resting_hr": {"series": [{"data": "2026-06-10", "valor": 58},
                                   {"data": "2026-06-11", "valor": 55}], "trend": {"direction": "descendo"}},
        "sleep_hours": {"series": [{"data": "2026-06-10", "valor": 6.2},
                                    {"data": "2026-06-11", "valor": 7.1}], "trend": {"direction": "subindo"}},
        "body_battery_high": {"series": [{"data": "2026-06-10", "valor": 70},
                                          {"data": "2026-06-11", "valor": 73}], "trend": {"direction": "estável"}},
    }, "insights": []}
    png = recovery_chart_png(trends, titulo="Semana")
    data = png.getvalue() if isinstance(png, io.BytesIO) else png
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
