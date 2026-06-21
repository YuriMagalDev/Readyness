from src.plan_parser import parse_plan


def test_parse_separa_corrida_e_musculacao():
    txt = "/plano\nseg corrida intervalado 6x800\nter musculacao superior\nsex corrida longao 12km"
    out = parse_plan(txt)
    assert [s["dia"] for s in out["corrida"]] == ["seg", "sex"]
    assert out["corrida"][0]["descricao"] == "intervalado 6x800"
    assert [s["dia"] for s in out["musculacao"]] == ["ter"]


def test_parse_aceita_variacoes_de_tipo_e_acento():
    out = parse_plan("qua força inferior\nterça corrida leve 40min")
    assert out["musculacao"][0]["dia"] == "qua"
    assert out["corrida"][0]["dia"] == "terça"     # dia original preservado


def test_parse_ignora_linha_invalida_e_vazia():
    out = parse_plan("/plano\n\nblah\nseg corrida x\nzzz musculacao y")
    assert len(out["corrida"]) == 1 and out["corrida"][0]["dia"] == "seg"
    assert out["musculacao"] == []                 # 'zzz' não é dia válido


def test_parse_texto_vazio():
    assert parse_plan("") == {"corrida": [], "musculacao": []}
    assert parse_plan("/plano") == {"corrida": [], "musculacao": []}
