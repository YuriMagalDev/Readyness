import datetime

STRENGTH_ACTIVITY_TYPES = {"strength_training", "indoor_cardio"}
SLEEP_TARGET_HOURS = 7.0

class DataProcessor:
    def classify_activities(self, activities: list) -> list:
        result = []
        for act in activities:
            type_key = act.get("activityType", {}).get("typeKey", "")
            result.append({
                "name": act.get("activityName", ""),
                "type": type_key,
                "is_strength": type_key in STRENGTH_ACTIVITY_TYPES,
                "duration_minutes": round(act.get("duration", 0) / 60),
                "hr_avg": act.get("averageHR"),
                "date": act.get("startTimeLocal", "")[:10],
            })
        return result

    def resting_hr_avg(self, hr_data: list) -> float:
        values = [d["restingHeartRate"] for d in hr_data if "restingHeartRate" in d]
        return round(sum(values) / len(values), 1) if values else 0.0

    def sleep_debt_hours(self, sleep_data: list) -> float:
        target_seconds = SLEEP_TARGET_HOURS * 3600
        total_debt = 0.0
        for day in sleep_data:
            slept = day.get("dailySleepDTO", {}).get("sleepTimeSeconds", target_seconds)
            deficit = target_seconds - slept
            if deficit > 0:
                total_debt += deficit
        return round(total_debt / 3600, 1)

    def morning_body_battery(self, battery_data: list) -> float:
        values = []
        for day in battery_data:
            if day and isinstance(day, list) and day[0].get("charged") is not None:
                values.append(day[0]["charged"])
        return round(sum(values) / len(values), 1) if values else 0.0

    def build_context_summary(
        self,
        activities: list,
        hr_data: list,
        sleep_data: list,
        battery_data: list,
    ) -> dict:
        classified = self.classify_activities(activities)
        today = datetime.date.today()
        week_ago = (today - datetime.timedelta(days=7)).isoformat()
        resting_hr_avg_7d = self.resting_hr_avg(hr_data)
        resting_hr_today = hr_data[0].get("restingHeartRate", resting_hr_avg_7d) if hr_data else resting_hr_avg_7d
        return {
            "resting_hr_avg_7d": resting_hr_avg_7d,
            "resting_hr_today": resting_hr_today,
            "sleep_debt_hours": self.sleep_debt_hours(sleep_data),
            "morning_battery_avg": self.morning_body_battery(battery_data),
            "recent_activities": classified[:10],
            "strength_sessions_7d": sum(
                1 for a in classified if a["is_strength"] and a["date"] >= week_ago
            ),
            "run_sessions_7d": sum(
                1 for a in classified
                if a["type"] in {"running", "trail_running", "treadmill_running"}
                and a["date"] >= week_ago
            ),
        }

    def weekly_trend(self, series: list, unidade: str = "") -> dict:
        """Compara média dos 7 valores mais recentes vs os 7 anteriores.
        `series` ordenada do mais antigo ao mais recente. < 14 pontos → vazio."""
        valores = [v for v in series if v is not None]
        if len(valores) < 14:
            return {"delta": 0.0, "label": ""}
        recentes = valores[-7:]
        anteriores = valores[-14:-7]
        media_rec = sum(recentes) / 7
        media_ant = sum(anteriores) / 7
        delta = round(media_rec - media_ant, 1)
        if delta == 0.0:
            return {"delta": 0.0, "label": f"estável vs semana passada"}
        seta = "▲" if delta > 0 else "▼"
        sufixo = f" {unidade}" if unidade else ""
        return {
            "delta": delta,
            "label": f"{seta} {abs(delta)}{sufixo} vs semana passada",
        }
