from bot.handlers import parse_manual_macros


def test_parse_macros_ok():
    assert parse_manual_macros("120 24 3 1.5") == {"kcal": 120, "p": 24, "c": 3, "g": 1.5}


def test_parse_macros_virgula():
    assert parse_manual_macros("120 24 3 1,5")["g"] == 1.5


def test_parse_macros_invalido():
    assert parse_manual_macros("abc") is None
    assert parse_manual_macros("120 24") is None      # faltam campos
