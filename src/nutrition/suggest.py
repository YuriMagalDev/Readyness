"""Sugestão determinística de porções pra fechar os macros do dia.

Nenhum número inventado: só alimentos que resolvem na base (TACO/custom),
com gramas calculadas por regra de três a partir da proteína restante e
capadas pelas kcal restantes.
"""

_MIN_P_PER_100G = 8.0     # abaixo disso o alimento não serve pra fechar proteína
_KCAL_TOLERANCE = 1.15    # porção pode passar até 15% das kcal restantes
_MAX_GRAMS = 500.0
_MIN_GRAMS = 30.0


def _round10(g: float) -> float:
    return round(g / 10.0) * 10.0


def _from_per100(per: dict, p_left: float, kcal_left: float):
    if per["p"] < _MIN_P_PER_100G:
        return None
    grams = _round10(min(p_left / per["p"] * 100.0, _MAX_GRAMS))
    if grams < _MIN_GRAMS:
        grams = _MIN_GRAMS
    kcal = per["kcal"] * grams / 100.0
    if kcal_left > 0 and kcal > kcal_left * _KCAL_TOLERANCE:
        grams = _round10(kcal_left / per["kcal"] * 100.0)
        if grams < _MIN_GRAMS:
            return None
        kcal = per["kcal"] * grams / 100.0
    return grams, kcal, per["p"] * grams / 100.0


def _from_portion(hit: dict, p_left: float, kcal_left: float):
    pp = hit["per_portion"]
    pg = hit.get("portion_g") or 0
    if pp["p"] <= 0:
        return None
    qty = max(1, round(p_left / pp["p"]))
    while qty > 1 and kcal_left > 0 and pp["kcal"] * qty > kcal_left * _KCAL_TOLERANCE:
        qty -= 1
    kcal = pp["kcal"] * qty
    if kcal_left > 0 and kcal > kcal_left * _KCAL_TOLERANCE:
        return None
    return qty * pg, kcal, pp["p"] * qty


def suggest_to_close(remaining: dict, pool: list, fdb, max_options: int = 3) -> list:
    """Porções que fecham a proteína restante cabendo nas kcal restantes.

    remaining: {'kcal': .., 'p': ..} (o que falta). pool: nomes de alimentos em
    ordem de preferência (histórico do usuário + defaults). Retorna
    [{'food','grams','kcal','p'}] (até max_options, sem repetir alimento).
    """
    p_left = remaining.get("p", 0) or 0
    kcal_left = remaining.get("kcal", 0) or 0
    if p_left <= 2:
        return []
    out, seen = [], set()
    for name in pool:
        if len(out) >= max_options:
            break
        hit = fdb.match(name, fuzzy=False)
        if not hit or hit["name"] in seen:
            continue
        if "per100" in hit:
            calc = _from_per100(hit["per100"], p_left, kcal_left)
        elif "per_portion" in hit:
            calc = _from_portion(hit, p_left, kcal_left)
        else:
            calc = None
        if not calc:
            continue
        grams, kcal, p = calc
        seen.add(hit["name"])
        out.append({"food": hit["name"], "grams": grams, "kcal": kcal, "p": p})
    return out
