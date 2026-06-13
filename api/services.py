"""Monta payloads JSON-ready a partir do backend src/. Sem lógica de negócio nova."""
import json as _json
import datetime as _dt
from datetime import date, timedelta

from src.metric_catalog import CATALOG, DOMAIN_ORDER
from src.metric_status import compute_status

from src.data_processor import DataProcessor
from src.health_monitor import HealthMonitor
from src.training_planner import TrainingPlanner
from src.analytics import Analytics
from src.insight_engine import InsightEngine
from src.extractors import splits_from_garmin
from src.plan_tracker import week_start_of, match_plan


def _load_context(client):
    dp = DataProcessor()
    activities = client.get_activities(28)
    hr_data = client.get_heart_rate_stats(7)
    sleep_data = client.get_sleep(14)
    battery_data = client.get_body_battery(7)
    context = dp.build_context_summary(activities, hr_data, sleep_data, battery_data)
    return dp, context, activities, hr_data, sleep_data, battery_data


def build_today(client, db=None, force=False) -> dict:
    dp, context, *_ = _load_context(client)
    status = HealthMonitor().check(context)
    payload = {
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
    if db is not None:
        start, end = _period_range(30)
        snaps = db.get_snapshots(start, end)
        analytics = Analytics().summary(snaps)
        payload["daily_insight"] = InsightEngine(db=db).daily_insight(context, analytics, force=force)
        payload["parametros"] = _param_deltas(snaps)
        # topo reflete o dado recém-sincronizado: sobrepõe FC repouso de hoje pelo snapshot
        if snaps and snaps[-1].get("resting_hr") is not None:
            payload["metrics"]["resting_hr_today"] = snaps[-1]["resting_hr"]
    return payload


# Parâmetros com variação vs dia anterior.
# (key, label, unidade, icon, lower_is_better, kind). kind: "num" | "time" (segundos→mm:ss)
_PARAMS = [
    ("body_battery_high", "Body Battery", "", "⚡", False, "num"),
    ("stress_avg", "Stress médio", "", "🧠", True, "num"),
    ("calories_total", "Calorias", " kcal", "🔥", False, "num"),
    ("steps", "Passos", "", "👟", False, "num"),
    ("floors", "Andares", "", "🪜", False, "num"),
    ("sleep_hours", "Sono", " h", "🌙", False, "num"),
    ("sleep_score", "Score de sono", "", "💤", False, "num"),
    ("intensity_minutes", "Min. intensidade", " min", "🔥", False, "num"),
    ("race_pred_5k", "Prova 5k", "", "🏁", True, "time"),
    ("race_pred_10k", "Prova 10k", "", "🏁", True, "time"),
]


def _fmt_valor(kind: str, val, unidade: str) -> str:
    """Formata o valor pra exibição. time = segundos → [h:]mm:ss."""
    if val is None:
        return ""
    if kind == "time":
        secs = int(round(val))
        m, s = divmod(secs, 60)
        if m >= 60:
            h, m = divmod(m, 60)
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m}:{s:02d}"
    num = int(val) if float(val).is_integer() else round(val, 1)
    return f"{num}{unidade}"


def _fmt_delta(kind: str, delta, unidade: str) -> str:
    """Delta formatado com sinal. None → ''."""
    if delta is None:
        return ""
    sinal = "+" if delta > 0 else "-"
    mag = abs(delta)
    if kind == "time":
        m, s = divmod(int(round(mag)), 60)
        return f"{sinal}{m}:{s:02d}"
    num = int(mag) if float(mag).is_integer() else round(mag, 1)
    return f"{sinal}{num}{unidade}"


def _param_deltas(snaps: list) -> list:
    """Compara os 2 snapshots mais recentes (hoje vs dia anterior)."""
    out = []
    for key, label, unidade, icon, lower_is_better, kind in _PARAMS:
        # pega os 2 dias mais recentes com valor não-nulo desse parâmetro
        vals = [s for s in snaps if s.get(key) is not None]
        if not vals:
            continue
        cur = vals[-1]
        prev = vals[-2] if len(vals) >= 2 else None
        valor = cur[key]
        delta = round(valor - prev[key], 1) if prev else None
        if delta is None or delta == 0:
            direcao = "estável"
        elif delta > 0:
            direcao = "subiu"
        else:
            direcao = "desceu"
        # sentido bom/ruim: stress/predição subir é ruim; bateria/passos é contexto
        bom = None
        if delta and lower_is_better:
            bom = delta < 0
        out.append({
            "label": label, "icon": icon, "valor": valor, "unidade": unidade,
            "valor_fmt": _fmt_valor(kind, valor, unidade),
            "delta": delta, "delta_fmt": _fmt_delta(kind, delta, unidade),
            "direcao": direcao, "bom": bom,
            "data": cur["date"], "data_anterior": prev["date"] if prev else None,
        })
    return out


def build_plan(client, db=None) -> dict:
    _, context, *_ = _load_context(client)
    hoje = date.today()
    week_start = week_start_of(hoje)

    # alimenta o gerador com o cumprimento da semana atual (se houver plano salvo)
    if db is not None:
        saved = db.get_plan(week_start)
        if saved:
            acts = db.get_activities(week_start, hoje.isoformat())
            context["cumprimento_semana"] = match_plan(saved["plan"], acts, hoje, week_start)

    plan = TrainingPlanner().generate_weekly_plan(context)

    if db is not None:
        db.upsert_plan(week_start, plan, hoje.isoformat())
    return plan


def build_plan_status(db, today: date = None) -> dict:
    today = today or date.today()
    week_start = week_start_of(today)
    saved = db.get_plan(week_start)
    if saved is None:
        return {"plan": None, "match": None, "week_start": week_start}
    acts = db.get_activities(week_start, today.isoformat())
    match = match_plan(saved["plan"], acts, today, week_start)
    return {
        "plan": saved["plan"], "match": match,
        "week_start": week_start, "created_at": saved["created_at"],
    }


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


def _period_range(period: int):
    end = date.today()
    start = end - timedelta(days=period - 1)
    return start.isoformat(), end.isoformat()


def build_trends(db, period: int = 30, force: bool = False) -> dict:
    start, end = _period_range(period)
    snaps = db.get_snapshots(start, end)
    metrics = Analytics().summary(snaps)
    insights = InsightEngine(db=db).trend_insights(metrics, period=period, force=force)
    return {"period": period, "metrics": metrics, "insights": insights}


def build_activities(db, period: int = 30) -> list:
    start, end = _period_range(period)
    return db.get_activities(start, end)


def build_activity_detail(db, client, activity_id: int) -> dict:
    act = db.get_activity(activity_id)
    if act is None:
        raise ValueError(f"Atividade {activity_id} não encontrada")
    if act.get("splits_json"):
        splits = _json.loads(act["splits_json"])
    else:
        raw = client.get_activity_splits(activity_id)
        splits = splits_from_garmin(raw)
        act["splits_json"] = _json.dumps(splits)
        db.upsert_activity(act)
    insight = InsightEngine(db=db).activity_insight(act, splits)
    return {"activity": act, "splits": splits, "insight": insight}


def build_metrics(db, date: str, today: _dt.date = None) -> dict:
    today = today or _dt.date.today()
    rows_today = {r["metric_key"]: r for r in db.get_metrics(date)}

    dominios = {d: [] for d in DOMAIN_ORDER}
    for spec in CATALOG:
        row = rows_today.get(spec.key)
        if row is None and spec.cadencia in ("corpo", "fitness"):
            row = _latest_on_or_before(db, spec.key, date)

        if row is None:
            value, measured_at, source = None, None, spec.source_default
        else:
            value, measured_at, source = row["value"], row["measured_at"], row["source"]

        status = compute_status(spec.cadencia, source, measured_at, today)
        dominios[spec.dominio].append({
            "key": spec.key, "label": spec.label, "value": value,
            "unidade": spec.unidade, "measured_at": measured_at,
            "status": status, "source": source,
        })
    return {"date": date, "dominios": dominios}


def _latest_on_or_before(db, metric_key: str, date: str):
    start = (_dt.date.fromisoformat(date) - _dt.timedelta(days=60)).isoformat()
    series = db.get_metric_series(metric_key, start, date)
    return series[-1] if series else None
