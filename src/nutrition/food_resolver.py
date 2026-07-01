"""Resolve macros de um alimento comum pelo nome, via API Anthropic (texto).

Usado quando o alimento não está no cache (custom_foods) nem bate exato na TACO.
Resultado é cacheado em custom_foods (source='ia') — 1 chamada por alimento novo.
Reusa o parse tolerante de label_vision. Cliente injetável (mockado nos testes).
"""
from src.nutrition.label_vision import parse_label_response

_PROMPT = (
    "Você é uma tabela de composição de alimentos. Para o alimento a seguir, "
    "responda APENAS um JSON com as chaves: name (nome curto do alimento), "
    "base_unit (sempre \"100g\"), porcao_g (null), kcal, p (proteína g), "
    "c (carboidrato g), g (gordura g) — valores por 100 g na forma como é "
    "normalmente consumido (cozido/preparado). Números com ponto decimal, sem "
    "texto fora do JSON. Se não souber o alimento, responda {}.\n\nAlimento: "
)


def resolve_food(name: str, *, client, model: str):
    """Nome do alimento -> {name, base_unit, porcao_g, kcal, p, c, g} ou None."""
    if not name or client is None:
        return None
    resp = client.messages.create(
        model=model,
        max_tokens=300,
        messages=[{"role": "user", "content": _PROMPT + name}],
    )
    text = resp.content[0].text if resp.content else ""
    return parse_label_response(text)
