from telegram import InlineKeyboardButton, InlineKeyboardMarkup

CHECKINS = [
    {"key": "hidratacao", "label": "Hidratação", "low": "desidratado", "high": "bem hidratado"},
    {"key": "energia", "label": "Energia", "low": "esgotado", "high": "cheio de energia"},
    {"key": "soreness", "label": "Dor muscular", "low": "muito dolorido", "high": "sem dor"},
    {"key": "alimentacao", "label": "Alimentação", "low": "mal alimentado", "high": "bem alimentado"},
]
_BY_KEY = {c["key"]: c for c in CHECKINS}


def scale_keyboard(key: str, day: str) -> InlineKeyboardMarkup:
    """Teclado 1–5. `day` (YYYY-MM-DD) viaja no callback pra resposta gravar
    sempre no dia do check-in, mesmo que respondida após a meia-noite."""
    row = [InlineKeyboardButton(str(n), callback_data=f"ci:{key}:{n}:{day}") for n in range(1, 6)]
    return InlineKeyboardMarkup([row])


def parse_callback(data: str):
    """'ci:<key>:<n>:<YYYY-MM-DD>' -> (key, n, day) ou None."""
    parts = (data or "").split(":")
    if len(parts) != 4 or parts[0] != "ci":
        return None
    try:
        return parts[1], int(parts[2]), parts[3]
    except ValueError:
        return None


def prompt_text(c: dict) -> str:
    return f"{c['label']}? (1 = {c['low']} · 5 = {c['high']})"
