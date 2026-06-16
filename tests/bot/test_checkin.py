from bot.checkin import CHECKINS, scale_keyboard, parse_callback

def test_catalogo_tem_4():
    keys = [c["key"] for c in CHECKINS]
    assert keys == ["hidratacao", "energia", "soreness", "alimentacao"]

def test_keyboard_tem_5_botoes():
    kb = scale_keyboard("energia")
    botoes = kb.inline_keyboard[0]
    assert len(botoes) == 5
    assert botoes[0].callback_data == "ci:energia:1"
    assert botoes[4].callback_data == "ci:energia:5"

def test_parse_callback():
    assert parse_callback("ci:soreness:3") == ("soreness", 3)
    assert parse_callback("lixo") is None
