TREND_METRICS = [
    "resting_hr", "sleep_hours", "stress_avg", "body_battery_high",
    "intensity_minutes", "race_pred_5k",
]
SLOPE_EPSILON = 0.05  # |slope| abaixo disso = estável


class Analytics:
    def series(self, snapshots: list, metric: str) -> list:
        return [{"data": s["date"], "valor": s.get(metric)} for s in snapshots]

    def trend(self, snapshots: list, metric: str) -> dict:
        pts = [(i, s[metric]) for i, s in enumerate(snapshots) if s.get(metric) is not None]
        if len(pts) < 2:
            return {"slope": 0.0, "direction": "estável"}
        n = len(pts)
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        mx = sum(xs) / n
        my = sum(ys) / n
        denom = sum((x - mx) ** 2 for x in xs)
        if denom == 0:
            return {"slope": 0.0, "direction": "estável"}
        slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / denom
        if abs(slope) < SLOPE_EPSILON:
            direction = "estável"
        elif slope > 0:
            direction = "subindo"
        else:
            direction = "descendo"
        return {"slope": round(slope, 4), "direction": direction}

    def summary(self, snapshots: list) -> dict:
        out = {}
        for metric in TREND_METRICS:
            out[metric] = {
                "series": self.series(snapshots, metric),
                "trend": self.trend(snapshots, metric),
            }
        return out
