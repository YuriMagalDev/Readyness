from telegram import InlineKeyboardButton, InlineKeyboardMarkup

CHECKINS = [
    {"key": "hidratacao", "label": "Hidratação", "low": "desidratado", "high": "bem hidratado"},
    {"key": "energia", "label": "Energia", "low": "esgotado", "high": "cheio de energia"},
    {"key": "soreness", "label": "Dor muscular", "low": "muito dolorido", "high": "sem dor"},
    {"key": "alimentacao", "label": "Alimentação", "low": "mal alimentado", "high": "bem alimentado"},
]
_BY_KEY = {c["key"]: c for c in CHECKINS}


def scale_keyboard(key: str) -> InlineKeyboardMarkup:
    row = [InlineKeyboardButton(str(n), callback_data=f"ci:{key}:{n}") for n in range(1, 6)]
    return InlineKeyboardMarkup([row])


def parse_callback(data: str):
    parts = (data or "").split(":")
    if len(parts) != 3 or parts[0] != "ci":
        return None
    try:
        return parts[1], int(parts[2])
    except ValueError:
        return None


def prompt_text(c: dict) -> str:
    return f"{c['label']}? (1 = {c['low']} · 5 = {c['high']})"
