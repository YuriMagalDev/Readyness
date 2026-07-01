from types import SimpleNamespace
from src.nutrition.food_resolver import resolve_food


def _client(text):
    return SimpleNamespace(messages=SimpleNamespace(
        create=lambda **kw: SimpleNamespace(content=[SimpleNamespace(text=text)])))


def test_resolve_food_ok():
    c = _client('{"name":"pão francês","base_unit":"100g","porcao_g":null,"kcal":300,"p":8,"c":59,"g":3}')
    out = resolve_food("pão francês", client=c, model="m")
    assert out["kcal"] == 300 and out["base_unit"] == "100g"


def test_resolve_food_desconhecido_vira_none():
    c = _client("{}")
    assert resolve_food("xyzqwk", client=c, model="m") is None


def test_resolve_food_sem_cliente():
    assert resolve_food("arroz", client=None, model="m") is None
