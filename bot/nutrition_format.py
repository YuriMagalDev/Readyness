def format_meal_confirm(parsed: dict) -> str:
    meal = (parsed.get("meal") or "Refeição").capitalize()
    lines = [f"🍽 {meal}"]
    tot = {"kcal": 0.0, "p": 0.0, "c": 0.0, "g": 0.0}
    desconhecidos = []
    for it in parsed.get("items", []):
        if it.get("recognized"):
            for k in tot:
                tot[k] += it[k]
            lines.append(
                f"• {it['food']} {round(it['grams'])}g → {round(it['kcal'])} kcal · "
                f"P {it['p']:.0f} · C {it['c']:.0f} · G {it['g']:.0f}"
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
