import datetime as dt
from telegram import Update
from telegram.ext import ContextTypes

from bot import core, messages
from bot.checkin import CHECKINS, scale_keyboard, parse_callback, prompt_text
from bot.charts import recovery_chart_png
from src.services_core import save_checkin, build_trends


def _authorized(update: Update, context) -> bool:
    cfg = context.bot_data["cfg"]
    chat = update.effective_chat
    return chat is not None and chat.id == cfg.chat_id


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _authorized(update, context):
        return
    await update.message.reply_text(
        "Readiness bot. Comandos:\n"
        "/saldo — saldo do dia\n/insights — leitura da IA\n"
        "/checkin — responder hidratação/energia/dor/alimentação\n"
        "/semana — resumo 7d\n/mes — resumo 30d"
    )


async def cmd_saldo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _authorized(update, context):
        return
    db = context.bot_data["db"]
    client = context.bot_data["client"]
    day = dt.date.today().isoformat()
    try:
        ctx = core.load_context(client)
        analysis = core.daily_analysis(db, day)
        txt = messages.format_saldo(analysis["veredito"], core.collect_metrics(ctx))
    except Exception as e:  # noqa: BLE001
        txt = f"Não consegui montar o saldo agora ({e})."
    await update.message.reply_text(txt)


async def cmd_insights(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _authorized(update, context):
        return
    db = context.bot_data["db"]
    day = dt.date.today().isoformat()
    try:
        analysis = core.daily_analysis(db, day)
        txt = messages.format_insights(analysis["insights"])
    except Exception:  # noqa: BLE001
        txt = messages.format_insights([])
    await update.message.reply_text(txt)


async def cmd_checkin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _authorized(update, context):
        return
    for c in CHECKINS:
        await update.message.reply_text(prompt_text(c), reply_markup=scale_keyboard(c["key"]))


async def on_checkin_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _authorized(update, context):
        return
    q = update.callback_query
    parsed = parse_callback(q.data)
    if not parsed:
        await q.answer("inválido")
        return
    key, val = parsed
    save_checkin(context.bot_data["db"], {key: val})
    label = next((c["label"] for c in CHECKINS if c["key"] == key), key)
    await q.answer("anotado")
    await q.edit_message_text(f"{label}: {val} ✓")


async def _send_trends(update, context, period: int, titulo: str):
    db = context.bot_data["db"]
    trends = build_trends(db, period=period)
    png = recovery_chart_png(trends, titulo=titulo)
    legenda = messages.format_insights(
        [{"texto": t, "metricas_usadas": []} for t in trends.get("insights", [])]
    )
    await update.message.reply_photo(photo=png, caption=legenda[:1024] or titulo)


async def cmd_semana(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _authorized(update, context):
        return
    await _send_trends(update, context, 7, "Semana")


async def cmd_mes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _authorized(update, context):
        return
    await _send_trends(update, context, 30, "Mês")
