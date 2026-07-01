"""Estado e contexto da conversa /ask (coach). Puro, sem Telegram."""

from src.services_core import build_run_detail
from bot.nutrition import today_panel

_KEY = "ask_thread"


def open_thread(user_data, mode, run_id, context):
    user_data[_KEY] = {"mode": mode, "run_id": run_id,
                       "context": context or {}, "history": []}


def is_active(user_data) -> bool:
    return _KEY in user_data


def get_context(user_data) -> dict:
    return (user_data.get(_KEY) or {}).get("context", {})


def history(user_data) -> list:
    return (user_data.get(_KEY) or {}).get("history", [])


def append_user(user_data, text):
    th = user_data.get(_KEY)
    if th is not None:
        th["history"].append({"role": "user", "content": text})


def append_assistant(user_data, text):
    th = user_data.get(_KEY)
    if th is not None:
        th["history"].append({"role": "assistant", "content": text})


def close_thread(user_data):
    user_data.pop(_KEY, None)


def build_run_context(db, client, activity_id) -> dict:
    """Contexto de uma corrida. Degrada sem splits se Garmin indisponível."""
    try:
        detail = build_run_detail(db, client, activity_id)
        return {"activity": detail["activity"], "splits": detail["splits"],
                "insight": detail["insight"]}
    except Exception:  # noqa: BLE001 — 429/sem splits: usa só o que tem no DB
        act = db.get_activity(activity_id)
        return {"activity": act, "splits": [], "insight": None}


def build_general_context(db, db_path, profile, date) -> dict:
    """Contexto do dia: readiness (snapshot determinístico) + painel de nutrição."""
    snaps = db.get_snapshots(date, date)
    readiness = snaps[0] if snaps else {}
    try:
        nutricao = today_panel(db_path, profile, date).get("today", {})
    except Exception:  # noqa: BLE001 — sem nutrição: contexto segue
        nutricao = {}
    return {"readiness": readiness, "nutricao": nutricao}
