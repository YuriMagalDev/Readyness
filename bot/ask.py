"""Estado e contexto da conversa /ask (coach). Puro, sem Telegram."""

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
