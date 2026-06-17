import html as _html

# Mensagens do saldo usam HTML do Telegram (negrito/itálico). Passe parse_mode="HTML".
PARSE_MODE = "HTML"

_SEMAFORO = {"verde": "🟢", "amarelo": "🟡", "vermelho": "🔴"}
_VERDICT_WORD = {"verde": "Pode treinar", "amarelo": "Pegue leve", "vermelho": "Dia de descanso"}
_RULE = "━━━━━━━━━━━━━━━"


def _e(s) -> str:
    """Escapa texto dinâmico pro HTML do Telegram."""
    return _html.escape(str(s)) if s is not None else ""


def _fmt_h(h) -> str:
    """Horas decimais -> '6h18'. None -> '—'."""
    if h is None:
        return "—"
    total_min = round(h * 60)
    return f"{total_min // 60}h{total_min % 60:02d}"


def sleep_insight(sleep: dict) -> str:
    """Frase calorosa sobre a noite, só com os dados disponíveis."""
    if not sleep or sleep.get("hours") is None:
        return "Ainda não peguei seu sono de hoje — sincronize o relógio quando puder. 🌙"
    h = sleep["hours"]
    target = sleep.get("target", 7.0)
    if h >= target:
        partes = [f"Você dormiu <b>{_fmt_h(h)}</b> — uma noite cheia. O corpo agradeceu. 🌙"]
    elif h >= target - 1:
        partes = [f"Você dormiu <b>{_fmt_h(h)}</b>, pertinho das {_fmt_h(target)} ideais."]
    else:
        partes = [f"Só <b>{_fmt_h(h)}</b> de sono essa noite — abaixo das {_fmt_h(target)} que o corpo pede."]
    estagios = []
    if sleep.get("deep_h") is not None:
        estagios.append(f"profundo {_fmt_h(sleep['deep_h'])}")
    if sleep.get("rem_h") is not None:
        estagios.append(f"REM {_fmt_h(sleep['rem_h'])}")
    if estagios:
        partes.append("Sono " + " · ".join(estagios) + ".")
    debt = sleep.get("debt_h")
    if debt and debt > 0:
        partes.append(
            f"Nos últimos 7 dias faltaram <b>{_fmt_h(debt)}</b> pra fechar as {int(target)}h "
            "por noite — vale dormir cedo hoje."
        )
    return " ".join(partes)


def _fc_line(m: dict):
    hoje, avg = m.get("resting_hr_today"), m.get("resting_hr_avg_7d")
    if hoje is None:
        return None
    if avg is None:
        return f"❤️ FC repouso  <b>{hoje}</b> bpm"
    d = hoje - avg
    if d <= -1:
        cauda = f"{abs(d):.1f} abaixo da média · bom sinal"
    elif d >= 5:
        cauda = f"+{d:.1f} acima da média · recuperação incompleta"
    elif d > 0:
        cauda = f"+{d:.1f} vs média"
    else:
        cauda = "na média"
    return f"❤️ FC repouso  <b>{hoje}</b> bpm  · {cauda}"


def format_saldo(veredito: dict, m: dict, sleep: dict = None, wake: str = None) -> str:
    status = veredito.get("status")
    sem = _SEMAFORO.get(status, "⚪")
    word = _VERDICT_WORD.get(status, "Leitura do dia")
    head = f"☀️ <b>Bom dia!</b>  ·  acordou {_e(wake)}" if wake else "☀️ <b>Bom dia!</b>"

    linhas = [head, ""]
    linhas.append(f"{sem} <b>{word}</b>")
    motivo = veredito.get("motivo")
    if motivo:
        linhas.append(f"<i>{_e(motivo)}</i>")
    rec = veredito.get("recomendacao")
    if rec:
        linhas.append(f"→ {_e(rec)}")

    linhas += ["", _RULE, "😴 <b>Sua noite</b>", sleep_insight(sleep)]

    rapidas = []
    fc = _fc_line(m)
    if fc:
        rapidas.append(fc)
    if m.get("morning_battery_avg") is not None:
        rapidas.append(f"⚡ Body Battery  <b>{m['morning_battery_avg']}</b>")
    if rapidas:
        linhas += ["", _RULE] + rapidas

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


def _fmt_clock(minutes) -> str:
    """Minutos decimais -> 'M:SS' ou 'H:MM:SS'. None -> '—'."""
    if minutes is None:
        return "—"
    total = round(minutes * 60)
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def _fmt_pace(min_per_km) -> str:
    """Min/km decimal -> 'M:SS'. None -> '—'."""
    if min_per_km is None:
        return "—"
    total = round(min_per_km * 60)
    return f"{total // 60}:{total % 60:02d}"


def format_activity(activity: dict, insight: str) -> str:
    """Cabeçalho (nome · distância · tempo · pace · FC) + insight da IA. HTML."""
    nome = _e(activity.get("name") or "Corrida")
    dist = activity.get("distance_m")
    km = f"{dist / 1000:.2f} km" if dist else "—"
    tempo = _fmt_clock(activity.get("duration_min"))
    pace = activity.get("pace_min_km")
    pace_s = f"{_fmt_pace(pace)} /km" if pace else "—"
    hr = activity.get("avg_hr")
    hr_s = f"{round(hr)} bpm" if hr else "—"
    head = f"🏃 <b>{nome}</b>\n{km} · {tempo} · {pace_s} · ❤️ {hr_s}"
    return f"{head}\n{_RULE}\n{_e(insight)}"
