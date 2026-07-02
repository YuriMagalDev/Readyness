from src.nutrition.suggest import suggest_to_close
from src.nutrition.food_db import FoodDB


def _fdb(custom=None):
    return FoodDB("tests/fixtures/taco_min.csv", custom=custom)


def test_sugere_porcao_que_fecha_proteina():
    # frango grelhado ~32g P/100g (TACO); faltam 48g P e 800 kcal
    out = suggest_to_close({"kcal": 800, "p": 48}, ["frango"], _fdb())
    assert len(out) == 1
    s = out[0]
    assert s["p"] >= 43                    # fecha (ou quase) a proteína
    assert s["kcal"] <= 800 * 1.15         # cabe nas kcal restantes
    assert s["grams"] % 10 == 0            # gramas redondas


def test_reduz_quando_kcal_nao_cabe():
    # faltam 60g P mas só 300 kcal -> porção reduzida pra caber
    out = suggest_to_close({"kcal": 300, "p": 60}, ["frango"], _fdb())
    assert out and out[0]["kcal"] <= 300 * 1.15


def test_proteina_fechada_sem_sugestao():
    assert suggest_to_close({"kcal": 500, "p": 0}, ["frango"], _fdb()) == []


def test_ignora_alimento_pobre_em_proteina():
    # arroz cozido (~2.5g P/100g) não serve pra fechar proteína
    out = suggest_to_close({"kcal": 500, "p": 40}, ["arroz cozido"], _fdb())
    assert out == []


def test_custom_por_porcao():
    custom = {"whey soldier": {"name": "whey soldier", "base_unit": "porcao",
                               "porcao_g": 30,
                               "macros": {"kcal": 120, "p": 24, "c": 3, "g": 1.5},
                               "source": "manual"}}
    out = suggest_to_close({"kcal": 400, "p": 48}, ["whey soldier"], _fdb(custom))
    assert out and out[0]["p"] == 48 and out[0]["grams"] == 60   # 2 scoops


def test_nao_repete_alimento_e_limita_opcoes():
    out = suggest_to_close({"kcal": 2000, "p": 60},
                           ["frango", "peito de frango", "frango", "atum", "ovos"],
                           _fdb(), max_options=2)
    assert len(out) <= 2
    nomes = [s["food"] for s in out]
    assert len(nomes) == len(set(nomes))
