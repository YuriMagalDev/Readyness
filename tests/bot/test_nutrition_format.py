from bot.nutrition_format import format_meal_confirm


def test_confirm_lista_itens_e_total():
    parsed = {"meal": "almoço", "items": [
        {"recognized": True, "food": "arroz cozido", "grams": 100,
         "kcal": 128, "p": 2.5, "c": 28, "g": 0.2},
        {"recognized": True, "food": "peito de frango grelhado", "grams": 200,
         "kcal": 318, "p": 62, "c": 0, "g": 7},
    ]}
    txt = format_meal_confirm(parsed)
    assert "Almoço" in txt
    assert "arroz cozido" in txt
    assert "446" in txt          # total kcal 128+318


def test_confirm_marca_nao_reconhecido():
    parsed = {"meal": None, "items": [{"recognized": False, "raw": "patinho"}]}
    txt = format_meal_confirm(parsed)
    assert "patinho" in txt
    assert "não" in txt.lower()


def test_confirm_mix_e_items_ausente():
    parsed = {"meal": "jantar", "items": [
        {"recognized": True, "food": "arroz cozido", "grams": 100,
         "kcal": 128, "p": 2.5, "c": 28, "g": 0.2},
        {"recognized": False, "raw": "patinho"},
    ]}
    txt = format_meal_confirm(parsed)
    assert "arroz cozido" in txt and "patinho" in txt
    assert "128" in txt
    # missing "items" key must not raise
    assert "Refeição" in format_meal_confirm({"meal": None})
