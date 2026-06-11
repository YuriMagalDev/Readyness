"""Monta payloads JSON-ready a partir do backend src/. Sem lógica de negócio nova."""
from datetime import date, timedelta

from src.data_processor import DataProcessor
from src.health_monitor import HealthMonitor
from src.training_planner import TrainingPlanner


def _load_context(client):
    dp = DataProcessor()
    activities = client.get_activities(28)
    hr_data = client.get_heart_rate_stats(7)
    sleep_data = client.get_sleep(14)
    battery_data = client.get_body_battery(7)
    context = dp.build_context_summary(activities, hr_data, sleep_data, battery_data)
    return dp, context, activities, hr_data, sleep_data, battery_data


def build_today(client) -> dict:
    _, context, *_ = _load_context(client)
    status = HealthMonitor().check(context)
    return {
        "status": status["status"],
        "motivo": status["motivo"],
        "recomendacao": status["recomendacao"],
        "metrics": {
            "resting_hr_today": context["resting_hr_today"],
            "resting_hr_avg_7d": context["resting_hr_avg_7d"],
            "morning_battery_avg": context["morning_battery_avg"],
            "sleep_debt_hours": context["sleep_debt_hours"],
            "run_sessions_7d": context["run_sessions_7d"],
        },
    }


def build_plan(client) -> dict:
    _, context, *_ = _load_context(client)
    return TrainingPlanner().generate_weekly_plan(context)


def _datas(n: int) -> list:
    hoje = date.today()
    return [(hoje - timedelta(days=i)).isoformat() for i in range(n - 1, -1, -1)]


def build_data(client) -> dict:
    dp = DataProcessor()
    activities = client.get_activities(28)
    # 14 dias: weekly_trend compara 7 recentes vs 7 anteriores (precisa de 14 pontos)
    hr_data = client.get_heart_rate_stats(14)
    sleep_data = client.get_sleep(14)
    battery_data = client.get_body_battery(14)

    # séries do mais antigo ao mais recente (hr_data[0] = hoje → inverter)
    fc = [d.get("restingHeartRate") for d in reversed(hr_data)]
    bat = [
        day[0]["charged"] if day and isinstance(day, list) and day[0].get("charged") is not None else None
        for day in reversed(battery_data)
    ]
    sono = [
        round(d.get("dailySleepDTO", {}).get("sleepTimeSeconds", 0) / 3600, 1)
        for d in reversed(sleep_data)
    ]

    def serie(vals, datas):
        return [{"data": dt, "valor": v} for dt, v in zip(datas, vals)]

    atividades = [
        {
            "data": a["date"], "nome": a["name"], "tipo": a["type"],
            "is_strength": a["is_strength"], "duracao": a["duration_minutes"],
        }
        for a in dp.classify_activities(activities)[:15]
    ]

    return {
        "fc_series": serie(fc, _datas(len(fc))),
        "battery_series": serie(bat, _datas(len(bat))),
        "sleep_series": serie(sono, _datas(len(sono))),
        "fc_trend": dp.weekly_trend(fc, unidade="bpm"),
        "battery_trend": dp.weekly_trend(bat, unidade="%"),
        "atividades": atividades,
    }
