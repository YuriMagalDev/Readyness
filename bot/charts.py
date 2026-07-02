import io
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

_PANELS = [
    ("resting_hr", "FC repouso (bpm)"),
    ("sleep_hours", "Sono (h)"),
    ("body_battery_high", "Body Battery"),
]

_FAIXA_COR = {"verde": "#2e9e5b", "amarelo": "#d99a14", "vermelho": "#c0392b"}


def recovery_chart_png(trends: dict, titulo: str = "") -> io.BytesIO:
    metrics = trends.get("metrics", {})
    fig, axes = plt.subplots(3, 1, figsize=(7, 6), sharex=False)
    fig.suptitle(titulo)
    for ax, (key, label) in zip(axes, _PANELS):
        serie = (metrics.get(key) or {}).get("series", [])
        ys = [p["valor"] for p in serie if p.get("valor") is not None]
        xs = list(range(len(ys)))
        ax.plot(xs, ys, marker="o", linewidth=1.5)
        ax.set_title(label, loc="left", fontsize=10)
        ax.grid(True, alpha=0.2)
        if not ys:
            ax.text(0.5, 0.5, "sem dados", ha="center", va="center", transform=ax.transAxes)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120)
    plt.close(fig)
    buf.seek(0)
    return buf


def _ring(ax, frac, label, value_txt, color):
    frac = max(0.0, min(1.0, frac))
    ax.pie([frac, 1 - frac], colors=[color, "#2b2b2b"], startangle=90,
           counterclock=False, radius=1.0,
           wedgeprops=dict(width=0.32, edgecolor="none"))
    ax.set_aspect("equal")
    ax.set_xlim(-3.2, 3.0)
    ax.set_ylim(-1.2, 1.2)
    # número à ESQUERDA do anel; legenda à direita — anel no meio
    ax.text(-1.45, 0, value_txt, ha="right", va="center", fontsize=14,
            color="#f0f0f0", fontweight="bold", clip_on=False)
    ax.text(1.45, 0, label, ha="left", va="center", fontsize=14,
            color="#dcdcdc", fontweight="bold", clip_on=False)


def nutrition_panel_png(panel: dict, *, titulo: str = "") -> "io.BytesIO":
    """Painel do dia em barras horizontais (proteína dominante) + rodapé de ontem."""
    today = panel.get("today", {})
    yday = panel.get("yesterday", {})

    totals = today.get("totals", {})
    target = today.get("target", {})
    ea = today.get("ea", {})

    def frac(cur, tot):
        return max(0.0, min(1.0, (cur / tot) if tot else 0.0))

    fig = plt.figure(figsize=(8, 5.6))
    fig.patch.set_facecolor("#16181d")
    ax = fig.add_axes([0.05, 0.20, 0.90, 0.68])
    ax.set_facecolor("#16181d")
    ax.axis("off")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 4)

    rows = [
        # (y, altura, label, cur, tgt, unid, cor, fontsize)
        (3, 0.52, "PROTEÍNA", totals.get("p", 0), target.get("protein_g", 0), "g",
         "#3b7dd8", 17),
        (2, 0.38, "KCAL", totals.get("kcal", 0), target.get("kcal", 0), "",
         "#2fa3a0", 13),
        (1, 0.38, "CARBO", totals.get("c", 0), target.get("carb_g", 0), "g",
         "#d99a14", 13),
        (0, 0.38, "GORDURA", totals.get("g", 0), target.get("fat_g", 0), "g",
         "#9b59b6", 13),
    ]
    # selo de EA colorido ao lado do label KCAL
    ea_faixa = ea.get("faixa")
    if ea_faixa:
        ax.text(0.115, 2 + 0.38 / 2 + 0.06, f"· EA {ea_faixa}", ha="left", va="bottom",
                fontsize=12, color=_FAIXA_COR.get(ea_faixa, "#888888"), fontweight="bold")
    for y, h, label, cur, tgt, unid, color, fs in rows:
        f = frac(cur, tgt)
        cheio = cur >= tgt and tgt > 0
        # trilho + preenchimento
        ax.barh(y, 1.0, height=h, left=0, color="#262a33", zorder=1)
        ax.barh(y, f, height=h, left=0, color=color, zorder=2)
        # label acima da barra, valor à direita
        ax.text(0, y + h / 2 + 0.06, label, ha="left", va="bottom",
                fontsize=fs, color=color, fontweight="bold")
        valor = f"{round(cur)}/{round(tgt)}{unid}"
        if cheio:
            valor += " ✓"
        else:
            falta = tgt - cur
            valor += f"   (faltam {round(falta)}{unid or ' kcal'})"
        ax.text(1.0, y + h / 2 + 0.06, valor, ha="right", va="bottom",
                fontsize=fs - 1, color="#e8e8e8", fontweight="bold")

    # ── rodapé: ontem numa linha ────────────────────────────────────────────────
    eaten_y = (yday.get("eaten") or {}).get("kcal", 0) or 0
    burn_y = yday.get("burn")
    saldo = (yday.get("balance") or {}).get("saldo")
    if saldo is None:
        saldo_str, saldo_color = "saldo —", "#888888"
    elif saldo < 0:
        saldo_str, saldo_color = f"déficit {abs(round(saldo))}", "#3b7dd8"
    else:
        saldo_str, saldo_color = f"superávit {round(saldo)}", "#c0392b"
    burn_str = f"{round(burn_y)}" if burn_y is not None else "s/ Garmin"
    prot_y = (yday.get("eaten") or {}).get("p", 0) or 0
    fig.text(0.05, 0.06,
             f"ONTEM  comido {round(eaten_y)} · gasto {burn_str} · {saldo_str} · "
             f"P {round(prot_y)}g",
             fontsize=12, color="#9a9a9a")
    if saldo is not None:
        fig.text(0.05, 0.02, " ", fontsize=2)  # respiro inferior

    if titulo:
        fig.suptitle(titulo, color="#f0f0f0", fontsize=16, fontweight="bold", y=0.97)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    return buf


def nutrition_chart_png(totals, target, ea, *, titulo=""):
    def frac(cur, tot):
        return (cur / tot) if tot else 0.0

    fig = plt.figure(figsize=(7, 4.2))
    fig.patch.set_facecolor("#1e1e1e")
    gs = fig.add_gridspec(2, 3)

    ax_kcal = fig.add_subplot(gs[0, :])
    kc = _FAIXA_COR.get(ea.get("faixa"), "#3b7dd8")
    _ring(ax_kcal, frac(totals["kcal"], target["kcal"]),
          f"kcal — EA {ea.get('faixa','?')}",
          f"{round(totals['kcal'])}/{round(target['kcal'])}", kc)

    specs = [("prot", totals["p"], target["protein_g"], "#3b7dd8"),
             ("carb", totals["c"], target["carb_g"], "#d99a14"),
             ("gord", totals["g"], target["fat_g"], "#9b59b6")]
    for i, (lbl, cur, tot, col) in enumerate(specs):
        ax = fig.add_subplot(gs[1, i])
        _ring(ax, frac(cur, tot), lbl, f"{round(cur)}/{round(tot)}g", col)

    if titulo:
        fig.suptitle(titulo, color="#f0f0f0", fontsize=13)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120, facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    return buf
