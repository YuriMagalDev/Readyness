from types import SimpleNamespace
from src.nutrition.label_vision import parse_label_response, extract_label


def test_parse_json_valido():
    txt = '{"name":"whey soldier","base_unit":"porcao","porcao_g":30,"kcal":120,"p":24,"c":3,"g":1.5}'
    out = parse_label_response(txt)
    assert out["base_unit"] == "porcao" and out["p"] == 24


def test_parse_json_com_cerca_e_virgula_decimal():
    txt = '```json\n{"name":"tapioca","base_unit":"100g","porcao_g":null,"kcal":240,"p":"0,5","c":60,"g":0.1}\n```'
    out = parse_label_response(txt)
    assert out["base_unit"] == "100g" and out["p"] == 0.5


def test_parse_invalido():
    assert parse_label_response("desculpe, não consegui ler") is None
    assert parse_label_response('{"kcal":120}') is None     # faltam campos


def test_extract_usa_cliente_mock():
    fake_resp = SimpleNamespace(content=[SimpleNamespace(
        text='{"name":"x","base_unit":"100g","porcao_g":null,"kcal":50,"p":1,"c":2,"g":0.3}')])
    fake_client = SimpleNamespace(messages=SimpleNamespace(create=lambda **kw: fake_resp))
    out = extract_label(b"fakeimg", client=fake_client, model="claude-opus-4-8")
    assert out["kcal"] == 50
