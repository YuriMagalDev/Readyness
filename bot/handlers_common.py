"""Helpers compartilhados pelos módulos de handlers do bot."""

from telegram import Update


def _authorized(update: Update, context) -> bool:
    cfg = context.bot_data["cfg"]
    chat = update.effective_chat
    return chat is not None and chat.id == cfg.chat_id


def _profile(context):
    return context.bot_data.get("profile") or {}


def _run_button_label(raw: dict) -> str:
    data = (raw.get("startTimeLocal") or "")[:10]
    nome = raw.get("activityName") or "Corrida"
    dist = raw.get("distance")
    km = f"{dist / 1000:.1f}km" if dist else "—"
    return f"{data} · {nome} · {km}"
