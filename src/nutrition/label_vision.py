import base64
import json
import re

_REQUIRED = ("name", "base_unit", "kcal", "p", "c", "g")

_PROMPT = (
    "Você recebe a foto de uma tabela nutricional brasileira (padrão ANVISA). "
    "Responda APENAS um JSON com as chaves: name (string curta do alimento), "
    "base_unit ('100g' se os valores são por 100g, 'porcao' se por porção), "
    "porcao_g (gramas de 1 porção, ou null), kcal, p (proteína g), c (carboidrato g), "
    "g (gordura g). Use os valores da coluna correspondente a base_unit. "
    "Números com ponto decimal. Sem texto fora do JSON."
)


def _num(v):
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        s = v.strip().replace(",", ".")
        return float(s)
    raise ValueError("not a number")


def parse_label_response(text: str):
    if not text:
        return None
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        raw = json.loads(m.group(0))
    except (json.JSONDecodeError, ValueError):
        return None
    if any(k not in raw for k in _REQUIRED):
        return None
    try:
        return {
            "name": str(raw["name"]).strip(),
            "base_unit": "porcao" if str(raw["base_unit"]).startswith("por") else "100g",
            "porcao_g": _num(raw["porcao_g"]) if raw.get("porcao_g") not in (None, "null") else None,
            "kcal": _num(raw["kcal"]),
            "p": _num(raw["p"]),
            "c": _num(raw["c"]),
            "g": _num(raw["g"]),
        }
    except (ValueError, TypeError):
        return None


def extract_label(image_bytes: bytes, *, client, model: str):
    b64 = base64.standard_b64encode(image_bytes).decode("ascii")
    resp = client.messages.create(
        model=model,
        max_tokens=400,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64",
                 "media_type": "image/jpeg", "data": b64}},
                {"type": "text", "text": _PROMPT},
            ],
        }],
    )
    text = resp.content[0].text if resp.content else ""
    return parse_label_response(text)
