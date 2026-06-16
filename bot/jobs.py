import datetime as dt
from telegram.ext import ContextTypes

from bot import core, messages
from bot.state import already_sent_saldo, mark_saldo_sent, already_prompted_checkin, mark_checkin_prompted
from bot.wake_detector import wake_time_local
from bot.checkin import CHECKINS, scale_keyboard, prompt_text
from src.ingestor import Ingestor


def _now_time():
    return dt.datetime.now().time()


async def _send_saldo(context, day, wake):
    cfg = context.bot_data["cfg"]
    db = context.bot_data["db"]
    client = context.bot_data["client"]
    try:
        Ingestor(client, db).sync_today()
    except Exception:  # noqa: BLE001 — sem sync ainda dá pra mandar do cache
        pass
    ctx = core.load_context(client)
    analysis = core.daily_analysis(db, day)
    txt = messages.format_saldo(
        analysis["veredito"], core.collect_metrics(ctx), sleep=core.sleep_view(ctx), wake=wake
    )
    await context.bot.send_message(chat_id=cfg.chat_id, text=txt)
    mark_saldo_sent(db, day)


async def job_wake(context: ContextTypes.DEFAULT_TYPE):
    """Roda a cada N min na janela matinal. Envia o saldo 1x ao detectar acordar."""
    cfg = context.bot_data["cfg"]
    db = context.bot_data["db"]
    client = context.bot_data["client"]
    day = dt.date.today().isoformat()
    if already_sent_saldo(db, day):
        return
    start = dt.time(*cfg.wake_start)
    end = dt.time(*cfg.wake_end)
    now = _now_time()
    if now < start:
        return  # antes da janela: não consulta Garmin ainda
    try:
        sleep_day = client.get_sleep_day(day)
    except Exception:  # noqa: BLE001
        sleep_day = None
    wake = wake_time_local(sleep_day)
    if wake:
        await _send_saldo(context, day, wake)
    elif now >= end:
        # fim da janela sem detectar acordar: manda com o que tiver
        await _send_saldo(context, day, None)


async def job_checkin(context: ContextTypes.DEFAULT_TYPE):
    cfg = context.bot_data["cfg"]
    db = context.bot_data["db"]
    day = dt.date.today().isoformat()
    if already_prompted_checkin(db, day):
        return
    for c in CHECKINS:
        await context.bot.send_message(
            chat_id=cfg.chat_id, text=prompt_text(c), reply_markup=scale_keyboard(c["key"])
        )
    mark_checkin_prompted(db, day)
