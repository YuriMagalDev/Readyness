_FAIXA_EMOJI = {"verde": "🟢", "amarelo": "🟡", "vermelho": "🔴"}


def format_nutri_context(yesterday: dict) -> str | None:
    """Linha de contexto de nutrição (energia + proteína de ontem fechado) pro /saldo.

    Info pura — NÃO altera o veredito. Retorna None quando não há refeição registrada
    ontem (nada útil a mostrar).
    """
    eaten = (yesterday or {}).get("eaten") or {}
    if not (eaten.get("kcal") or eaten.get("p")):
        return None
    ea = (yesterday or {}).get("ea") or {}
    emoji = _FAIXA_EMOJI.get(ea.get("faixa"), "")
    p = eaten.get("p") or 0.0
    alvo = (yesterday or {}).get("protein_target") or 0
    parte_prot = f"proteína {p:.0f}/{alvo:.0f}g"
    if alvo and p < alvo:
        parte_prot += f" (faltaram {alvo - p:.0f})"
    partes = [f"energia {emoji} {ea.get('ea', 0):.0f}".replace("  ", " "), parte_prot]
    saldo = ((yesterday or {}).get("balance") or {}).get("saldo")
    if saldo is not None:
        sinal = "+" if saldo >= 0 else "−"
        partes.append(f"saldo {sinal}{abs(saldo):.0f} kcal")
    return "📊 Ontem (contexto, não muda o veredito): " + " · ".join(partes)


_SOURCE_TAG = {"ia": " ~IA", "foto": " (rótulo)", "manual": " (cadastro)"}


def format_meal_confirm(parsed: dict) -> str:
    meal = (parsed.get("meal") or "Refeição").capitalize()
    lines = [f"🍽 {meal}"]
    tot = {"kcal": 0.0, "p": 0.0, "c": 0.0, "g": 0.0}
    desconhecidos = []
    for it in parsed.get("items", []):
        if it.get("recognized"):
            for k in tot:
                tot[k] += it[k]
            tag = _SOURCE_TAG.get(it.get("source"), "")
            lines.append(
                f"• {it['food']} {round(it['grams'])}g → {round(it['kcal'])} kcal · "
                f"P {it['p']:.0f} · C {it['c']:.0f} · G {it['g']:.0f}{tag}"
            )
        else:
            desconhecidos.append(it.get("raw", "?"))
    lines.append(
        f"─ total: {round(tot['kcal'])} kcal · P {tot['p']:.0f} · "
        f"C {tot['c']:.0f} · G {tot['g']:.0f}"
    )
    for d in desconhecidos:
        lines.append(f"❓ não reconheci \"{d}\" — cadastra ou corrige")
    return "\n".join(lines)
