_SEMAFORO = {"verde": "🟢", "amarelo": "🟡", "vermelho": "🔴"}


def format_saldo(veredito: dict, m: dict, wake: str = None) -> str:
    sem = _SEMAFORO.get(veredito.get("status"), "⚪")
    head = f"☀️ Bom dia — acordou {wake}" if wake else "☀️ Bom dia"
    delta = m["resting_hr_today"] - m["resting_hr_avg_7d"]
    delta_s = f"{'+' if delta > 0 else ''}{delta:.1f}"
    linhas = [
        head,
        f"{sem} {veredito.get('motivo', '')}",
        veredito.get("recomendacao", ""),
        "",
        f"FC repouso  {m['resting_hr_today']}  ({delta_s} vs 7d)",
        f"Body Battery {m['morning_battery_avg']}",
        f"Sono · dívida {m['sleep_debt_hours']}h",
        f"Corridas {m['run_sessions_7d']}/semana",
    ]
    return "\n".join(linhas)


def format_insights(insights: list) -> str:
    if not insights:
        return "IA indisponível — o veredito do dia segue válido."
    blocos = []
    for ins in insights:
        fontes = " · ".join(
            f"{s['label']} {s.get('valor', '')}{s.get('unidade', '')}".strip()
            for s in ins.get("metricas_usadas", [])
        )
        bloco = f"• {ins['texto']}"
        if fontes:
            bloco += f"\n   fontes: {fontes}"
        blocos.append(bloco)
    return "\n\n".join(blocos)
