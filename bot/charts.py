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
           wedgeprops=dict(width=0.30, edgecolor="none"))
    ax.set_aspect("equal")
    ax.text(0, 0.15, value_txt, ha="center", va="center", fontsize=11,
            color="#f0f0f0", fontweight="bold")
    ax.text(0, -0.35, label, ha="center", va="center", fontsize=9, color="#bdbdbd")


def nutrition_panel_png(panel: dict, *, titulo: str = "") -> "io.BytesIO":
    """Two-part panel: TODAY rings (protein-emphasized) + YESTERDAY bar summary."""
    today = panel.get("today", {})
    yday = panel.get("yesterday", {})

    totals = today.get("totals", {})
    target = today.get("target", {})
    ea = today.get("ea", {})

    def frac(cur, tot):
        return (cur / tot) if tot else 0.0

    # ── layout: 3 rows, 3 cols ─────────────────────────────────────────────────
    fig = plt.figure(figsize=(7, 7.5))
    fig.patch.set_facecolor("#1e1e1e")

    # row 0: protein ring (full width, dominant)
    # row 1: kcal + carb + fat rings
    # row 2: yesterday text summary
    gs = fig.add_gridspec(3, 3, height_ratios=[1.4, 1.0, 0.9], hspace=0.45)

    # Protein ring — visually dominant (row 0, full width)
    ax_prot = fig.add_subplot(gs[0, :])
    prot_cur = totals.get("p", 0)
    prot_tgt = target.get("protein_g", 1)
    prot_falta = max(0.0, prot_tgt - prot_cur)
    prot_color = "#3b7dd8"
    # larger radius by using bigger wedge
    ax_prot.pie(
        [frac(prot_cur, prot_tgt), max(0.0, 1 - frac(prot_cur, prot_tgt))],
        colors=[prot_color, "#2b2b2b"], startangle=90, counterclock=False,
        radius=1.0, wedgeprops=dict(width=0.38, edgecolor="none"),
    )
    ax_prot.set_aspect("equal")
    ax_prot.text(0, 0.18, f"{round(prot_cur)}/{round(prot_tgt)}g",
                 ha="center", va="center", fontsize=13, color="#f0f0f0", fontweight="bold")
    ax_prot.text(0, -0.28, "PROTEÍNA", ha="center", va="center",
                 fontsize=10, color=prot_color, fontweight="bold")
    if prot_falta > 0:
        ax_prot.text(0, -0.52, f"faltam {round(prot_falta)}g",
                     ha="center", va="center", fontsize=9, color="#e07b3b")

    # kcal + carb + fat rings (row 1)
    specs = [
        ("kcal", totals.get("kcal", 0), target.get("kcal", 0),
         _FAIXA_COR.get(ea.get("faixa"), "#3b7dd8"),
         f"kcal\nEA {ea.get('faixa','?')}"),
        ("carb", totals.get("c", 0), target.get("carb_g", 0), "#d99a14", "carb"),
        ("gord", totals.get("g", 0), target.get("fat_g", 0), "#9b59b6", "gord"),
    ]
    for col, (lbl, cur, tot, color, display_lbl) in enumerate(specs):
        ax = fig.add_subplot(gs[1, col])
        _ring(ax, frac(cur, tot), display_lbl, f"{round(cur)}/{round(tot)}{'g' if lbl!='kcal' else ''}", color)

    # ── YESTERDAY summary (row 2, full width) ─────────────────────────────────
    ax_yd = fig.add_subplot(gs[2, :])
    ax_yd.set_facecolor("#141414")
    ax_yd.axis("off")

    eaten_y = (yday.get("eaten") or {}).get("kcal", 0) or 0
    burn_y = yday.get("burn")
    balance = yday.get("balance") or {}
    saldo = balance.get("saldo")
    ea_y = yday.get("ea") or {}
    prot_y = (yday.get("eaten") or {}).get("p", 0) or 0
    prot_tgt_y = yday.get("protein_target", 165)

    burn_str = f"{round(burn_y)} kcal" if burn_y is not None else "sem dados Garmin"
    if saldo is None:
        saldo_str = "—"
        saldo_color = "#888888"
    elif saldo < -150:
        saldo_str = f"déficit {abs(round(saldo))} kcal"
        saldo_color = "#3b7dd8"
    elif saldo > 150:
        saldo_str = f"superávit {round(saldo)} kcal"
        saldo_color = "#c0392b"
    else:
        saldo_str = f"equilibrado ({round(saldo):+d} kcal)"
        saldo_color = "#2e9e5b"

    ea_faixa_y = ea_y.get("faixa", "?")
    ea_color_y = _FAIXA_COR.get(ea_faixa_y, "#888888")

    prot_y_color = "#2e9e5b" if prot_y >= prot_tgt_y * 0.9 else "#e07b3b"

    lines = [
        (f"ONTEM — comido: {round(eaten_y)} kcal · gasto: {burn_str}", "#bdbdbd"),
        (f"Saldo: {saldo_str}", saldo_color),
        (f"EA: {ea_faixa_y}  ·  Proteína: {round(prot_y)}/{round(prot_tgt_y)}g", ea_color_y),
    ]
    for i, (line, color) in enumerate(lines):
        ax_yd.text(0.02, 0.78 - i * 0.32, line, transform=ax_yd.transAxes,
                   fontsize=9, color=color, va="top")

    if titulo:
        fig.suptitle(titulo, color="#f0f0f0", fontsize=12)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120, facecolor=fig.get_facecolor())
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
