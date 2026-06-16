_SEMAFORO = {"verde": "🟢", "amarelo": "🟡", "vermelho": "🔴"}


def _v(x, suffix=""):
    """Valor da métrica ou em-dash quando ausente (Forerunner 55 vem vazio)."""
    return "—" if x is None else f"{x}{suffix}"


def format_saldo(veredito: dict, m: dict, wake: str = None) -> str:
    sem = _SEMAFORO.get(veredito.get("status"), "⚪")
    head = f"☀️ Bom dia — acordou {wake}" if wake else "☀️ Bom dia"
    hoje, avg = m.get("resting_hr_today"), m.get("resting_hr_avg_7d")
    if hoje is not None and avg is not None:
        d = hoje - avg
        fc = f"FC repouso  {hoje}  ({'+' if d > 0 else ''}{d:.1f} vs 7d)"
    else:
        fc = f"FC repouso  {_v(hoje)}"
    linhas = [
        head,
        f"{sem} {veredito.get('motivo', '')}",
        veredito.get("recomendacao", ""),
        "",
        fc,
        f"Body Battery {_v(m.get('morning_battery_avg'))}",
        f"Sono · dívida {_v(m.get('sleep_debt_hours'), 'h')}",
        f"Corridas {_v(m.get('run_sessions_7d'))}/semana",
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
