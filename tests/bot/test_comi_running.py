from bot.handlers import _comi_running


def test_running_acumula_e_total():
    comi = {"meal": "almoço", "items": [
        {"recognized": True, "food": "Arroz", "grams": 100, "kcal": 128, "p": 2.5, "c": 28, "g": 0.2, "source": "taco"},
        {"recognized": True, "food": "Frango", "grams": 200, "kcal": 318, "p": 62, "c": 0, "g": 7, "source": "taco"},
    ]}
    txt = _comi_running(comi)
    assert "Almoço" in txt and "Arroz" in txt and "Frango" in txt
    assert "446" in txt  # 128+318


def test_running_mostra_desconhecido_extra():
    comi = {"meal": "janta", "items": []}
    txt = _comi_running(comi, extra=[{"recognized": False, "raw": "xyz"}])
    assert "não reconheci" in txt and "xyz" in txt
