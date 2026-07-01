from types import SimpleNamespace
from src.history_db import HistoryDB
import src.nutrition.store as store
from bot.nutrition import resolve_unknowns


def _db(tmp_path):
    p = str(tmp_path / "h.db"); HistoryDB(p); return p


def _client(text):
    return SimpleNamespace(messages=SimpleNamespace(
        create=lambda **kw: SimpleNamespace(content=[SimpleNamespace(text=text)])))


def test_resolve_unknowns_cacheia_ia(tmp_path):
    p = _db(tmp_path)
    c = _client('{"name":"pao","base_unit":"100g","porcao_g":null,"kcal":300,"p":8,"c":59,"g":3}')
    out = resolve_unknowns(p, ["pão francês"], c, "m")
    assert out == ["pão francês"]
    foods = store.get_custom_foods(p)
    assert "pao frances" in foods
    assert foods["pao frances"]["source"] == "ia"
    assert foods["pao frances"]["macros"]["kcal"] == 300


def test_resolve_unknowns_sem_cliente(tmp_path):
    p = _db(tmp_path)
    assert resolve_unknowns(p, ["qualquer"], None, "m") == []
