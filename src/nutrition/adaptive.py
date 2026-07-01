"""Perfil vivo: tendência de peso, ritmo, BF estimado e proposta de ajuste.

Camada pura e determinística. O alvo só muda por proposta confirmada pelo usuário
(esta camada apenas *sugere*). BF é o único número inferido — sempre marcado "estimado"
na UI que consome estas funções.
"""


def trend_kg(kgs, window=3):
    """Média móvel dos últimos `window` pesos. None se lista vazia."""
    if not kgs:
        return None
    last = kgs[-window:]
    return round(sum(last) / len(last), 2)


def weekly_rate_pct(kgs):
    """Slope por passo (semana) via mínimos quadrados, em % do peso médio.

    None com <2 pontos. Negativo = perdendo peso.
    """
    n = len(kgs)
    if n < 2:
        return None
    xs = list(range(n))
    mean_x = sum(xs) / n
    mean_y = sum(kgs) / n
    num = sum((xs[i] - mean_x) * (kgs[i] - mean_y) for i in range(n))
    den = sum((x - mean_x) ** 2 for x in xs)
    if den == 0 or mean_y == 0:
        return 0.0
    slope = num / den            # kg por semana
    return slope / mean_y * 100  # %/semana


def derive_bf(prev_weight, prev_bf, new_weight, fat_frac=0.85):
    """Novo %BF estimado assumindo que fat_frac da variação de peso é gordura."""
    delta = new_weight - prev_weight
    prev_fat_mass = prev_weight * prev_bf / 100.0
    new_fat_mass = prev_fat_mass + delta * fat_frac
    if new_weight <= 0:
        return prev_bf
    return new_fat_mass / new_weight * 100.0


def is_adherent_day(totals, target, protein_frac=0.9, kcal_over=150):
    """Dia aderente: bateu proteína (>=90% do alvo) e não estourou kcal (+150)."""
    return (totals["p"] >= protein_frac * target["protein_g"]
            and totals["kcal"] <= target["kcal"] + kcal_over)


def week_adherence_ok(flags, need=5):
    return sum(1 for f in flags if f) >= need


def propose_adjustment(rate_pct, adherence_ok, cfg):
    """Sugere ajuste de kcal a partir do ritmo e da aderência. Nunca aplica sozinho."""
    if rate_pct is None:
        return {"action": "hold", "delta_kcal": 0, "reason": "sem dado de peso suficiente"}
    if rate_pct <= cfg["fast_rate"]:
        return {"action": "add", "delta_kcal": 100,
                "reason": "caindo rápido demais — risco de perder músculo"}
    if rate_pct >= cfg["target_rate_high"]:   # travado (perde pouco ou nada)
        if adherence_ok:
            return {"action": "cut", "delta_kcal": -100,
                    "reason": "peso travado com boa aderência — apertar o alvo"}
        return {"action": "follow_plan", "delta_kcal": 0,
                "reason": "peso travado, mas aderência baixa — segue o plano primeiro"}
    return {"action": "hold", "delta_kcal": 0, "reason": "no ritmo alvo"}
