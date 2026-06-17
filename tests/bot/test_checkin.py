from bot.checkin import CHECKINS, scale_keyboard, parse_callback

def test_catalogo_tem_4():
    keys = [c["key"] for c in CHECKINS]
    assert keys == ["hidratacao", "energia", "soreness", "alimentacao"]

def test_keyboard_tem_5_botoes_com_data():
    kb = scale_keyboard("energia", "2026-06-16")
    botoes = kb.inline_keyboard[0]
    assert len(botoes) == 5
    assert botoes[0].callback_data == "ci:energia:1:2026-06-16"
    assert botoes[4].callback_data == "ci:energia:5:2026-06-16"

def test_parse_callback_inclui_dia():
    assert parse_callback("ci:soreness:3:2026-06-16") == ("soreness", 3, "2026-06-16")
    assert parse_callback("ci:energia:4") is None   # formato antigo (sem dia) é inválido
    assert parse_callback("lixo") is None
