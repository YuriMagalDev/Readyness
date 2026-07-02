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


def _linha_macro(nome, feito, alvo, unidade=""):
    falta = alvo - feito
    base = f"{nome}: {feito:.0f}/{alvo:.0f}{unidade}"
    if falta > 0.5:
        return base + f" (falta {falta:.0f})"
    return base + " ✅"


def format_macros_today(today: dict) -> str:
    """Resumo texto rápido dos macros de hoje: consumido vs alvo (comando /macros)."""
    tot = (today or {}).get("totals") or {}
    tgt = (today or {}).get("target") or {}
    ea = (today or {}).get("ea") or {}
    tipo = "treino" if (today or {}).get("training") else "descanso"
    lines = [f"🍽 *Macros de hoje* ({tipo})"]
    lines.append(_linha_macro("Kcal", tot.get("kcal", 0), tgt.get("kcal", 0)))
    lines.append(_linha_macro("Proteína", tot.get("p", 0), tgt.get("protein_g", 0), "g"))
    lines.append(_linha_macro("Carbo", tot.get("c", 0), tgt.get("carb_g", 0), "g"))
    lines.append(_linha_macro("Gordura", tot.get("g", 0), tgt.get("fat_g", 0), "g"))
    if ea.get("faixa"):
        emoji = _FAIXA_EMOJI.get(ea["faixa"], "")
        lines.append(f"Energia disponível: {emoji} {ea.get('ea', 0):.0f}")
    return "\n".join(lines)


_MEAL_EMOJI = {"café da manhã": "🌅", "almoço": "🍽", "lanche": "🥪", "janta": "🌙"}


def _hhmm(iso: str) -> str:
    try:
        return iso[11:16]
    except Exception:  # noqa: BLE001
        return "--:--"


def format_dieta_text(today: dict, meals: list, suggestions: list) -> str:
    """Camada de decisão do /dieta: o que falta + porções reais pra fechar + dia até agora."""
    tot = (today or {}).get("totals") or {}
    tgt = (today or {}).get("target") or {}
    tipo = "treino" if (today or {}).get("training") else "descanso"

    kcal_left = max(0, (tgt.get("kcal", 0) or 0) - (tot.get("kcal", 0) or 0))
    p_left = max(0, (tgt.get("protein_g", 0) or 0) - (tot.get("p", 0) or 0))
    c_left = max(0, (tgt.get("carb_g", 0) or 0) - (tot.get("c", 0) or 0))

    lines = [f"🍽 Hoje ({tipo}) · alvo {round(tgt.get('kcal', 0))} kcal"]
    if p_left <= 2 and kcal_left > 0:
        lines.append(f"Proteína fechada ✅ · sobram {round(kcal_left)} kcal "
                     f"(carbo até {round(c_left)}g)")
    elif kcal_left <= 0:
        lines.append("Alvo de kcal batido — segura o resto do dia. ✅")
    else:
        lines.append(f"Faltam: {round(kcal_left)} kcal · {round(p_left)}g P · "
                     f"{round(c_left)}g C")
    if suggestions:
        lines.append("")
        lines.append("Pra fechar a proteína, cabe:")
        for s in suggestions:
            lines.append(f"• {round(s['grams'])}g {s['food']} — "
                         f"{round(s['kcal'])} kcal · {round(s['p'])}g P")
    lines.append("")
    if meals:
        lines.append("Registrado hoje:")
        for m in meals:
            nome = m.get("meal") or "refeição"
            emoji = _MEAL_EMOJI.get(nome, "•")
            lines.append(f"{emoji} {nome.capitalize()} {_hhmm(m.get('first_at') or '')} — "
                         f"{round(m.get('kcal') or 0)} kcal · P {round(m.get('p') or 0)}")
    else:
        lines.append("Nenhuma refeição registrada ainda — /comi ou /combo.")
    return "\n".join(lines)


def format_night_balance(today: dict, burn) -> str:
    """Fechamento noturno: comido (diário) × gasto (Garmin) do dia corrente.

    `burn` = calories_total do snapshot Garmin (None = sem sync hoje). Números
    só de fonte real; sem Garmin a comparação degrada mas o comido sai.
    """
    tot = (today or {}).get("totals") or {}
    tgt = (today or {}).get("target") or {}
    tipo = "treino" if (today or {}).get("training") else "descanso"
    eaten = tot.get("kcal", 0) or 0

    lines = [f"🌙 *Fechamento do dia* ({tipo})"]
    lines.append(f"Comido: {round(eaten)}/{round(tgt.get('kcal', 0))} kcal")
    if burn is None:
        lines.append("Gasto Garmin: sem dados hoje (relógio não sincronizou)")
    else:
        lines.append(f"Gasto Garmin (até agora): {round(burn)} kcal")
        saldo = eaten - burn
        if saldo < 0:
            lines.append(f"Saldo: déficit {abs(round(saldo))} kcal 💪")
        elif saldo > 0:
            lines.append(f"Saldo: superávit {round(saldo)} kcal ⚠️")
        else:
            lines.append("Saldo: zerado")
    p, alvo_p = tot.get("p", 0) or 0, tgt.get("protein_g", 0) or 0
    linha_p = f"Proteína: {round(p)}/{round(alvo_p)}g"
    if alvo_p and p < alvo_p:
        linha_p += f" (faltam {round(alvo_p - p)})"
    else:
        linha_p += " ✅"
    lines.append(linha_p)
    return "\n".join(lines)


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
