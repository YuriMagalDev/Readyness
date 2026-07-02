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


# ── format_night_balance ────────────────────────────────────────────────────────

from bot.nutrition_format import format_night_balance


def _today(kcal=1850, p=148, training=True, tgt_kcal=2065, tgt_p=160):
    return {"totals": {"kcal": kcal, "p": p, "c": 100, "g": 40},
            "target": {"kcal": tgt_kcal, "protein_g": tgt_p, "carb_g": 210, "fat_g": 65},
            "ea": {"ea": 20, "faixa": "amarelo"},
            "training": training}


def test_night_balance_com_garmin_deficit():
    txt = format_night_balance(_today(), burn=2600)
    assert "1850" in txt and "2600" in txt
    assert "déficit 750" in txt
    assert "148/160" in txt
    assert "faltam 12" in txt.lower() or "falta 12" in txt.lower()


def test_night_balance_superavit_alerta():
    txt = format_night_balance(_today(kcal=3000), burn=2600)
    assert "superávit 400" in txt


def test_night_balance_sem_garmin_degrada():
    txt = format_night_balance(_today(), burn=None)
    assert "sem dados" in txt.lower()
    assert "1850" in txt          # comido continua saindo


def test_night_balance_proteina_ok():
    txt = format_night_balance(_today(p=165), burn=2600)
    assert "165/160" in txt and "✅" in txt
