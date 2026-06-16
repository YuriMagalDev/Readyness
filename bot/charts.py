import io
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

_PANELS = [
    ("resting_hr", "FC repouso (bpm)"),
    ("sleep_hours", "Sono (h)"),
    ("body_battery_high", "Body Battery"),
]


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
