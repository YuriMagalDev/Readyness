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
