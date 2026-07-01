import datetime as dt
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot import core, messages

_log = logging.getLogger(__name__)
from bot.state import already_sent_saldo, mark_saldo_sent, already_prompted_checkin, mark_checkin_prompted
from bot.wake_detector import wake_time_local
from bot.checkin import CHECKINS, scale_keyboard, prompt_text
from src.ingestor import Ingestor
from src import alerts
from src.metric_reader import context_from_metrics
from bot.runs import filter_runs
from src.services_core import build_run_detail
from src.extractors import activity_from_garmin
from src.weekly_briefing import build_weekly_briefing


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
    # veredito/insights vêm do DB (confiáveis); só as métricas/sono dependem do Garmin.
    try:
        ctx = core.load_context(client)
        met, sleep = core.collect_metrics(ctx), core.sleep_view(ctx)
    except Exception:  # noqa: BLE001 — Garmin fora/429: degrada, manda o veredito mesmo assim
        met, sleep = {}, {}
    analysis = core.daily_analysis(db, day)
    txt = messages.format_saldo(analysis["veredito"], met, sleep=sleep, wake=wake)
    await context.bot.send_message(chat_id=cfg.chat_id, text=txt, parse_mode=messages.PARSE_MODE)
    mark_saldo_sent(db, day)


async def job_morning(context: ContextTypes.DEFAULT_TYPE):
    """Roda em cada slot fixo (ex.: 09:30, 12:00, 14:00). Manda o saldo 1x ao detectar
    que o sono já sincronizou; no último slot manda mesmo sem sincronizar (fallback)."""
    cfg = context.bot_data["cfg"]
    db = context.bot_data["db"]
    client = context.bot_data["client"]
    day = dt.date.today().isoformat()
    if already_sent_saldo(db, day):
        return
    try:
        sleep_day = client.get_sleep_day(day)
    except Exception:  # noqa: BLE001
        sleep_day = None
    wake = wake_time_local(sleep_day)
    last = dt.time(*cfg.morning_slots[-1]) if cfg.morning_slots else dt.time(14, 0)
    if wake:
        await _send_saldo(context, day, wake)
    elif _now_time() >= last:
        # último slot e o sono ainda não sincronizou: manda com o que tiver
        await _send_saldo(context, day, None)


async def job_checkin(context: ContextTypes.DEFAULT_TYPE):
    cfg = context.bot_data["cfg"]
    db = context.bot_data["db"]
    day = dt.date.today().isoformat()
    if already_prompted_checkin(db, day):
        return
    for c in CHECKINS:
        await context.bot.send_message(
            chat_id=cfg.chat_id, text=prompt_text(c), reply_markup=scale_keyboard(c["key"], day)
        )
    mark_checkin_prompted(db, day)


_RUNS_SEEDED = "runs_seeded"


async def job_runs(context: ContextTypes.DEFAULT_TYPE):
    """A cada 15min: detecta corrida nova no Garmin e manda o insight. 1ª passada seeda
    o histórico (marca como visto sem enviar) pra não spammar corridas antigas no deploy."""
    cfg = context.bot_data["cfg"]
    db = context.bot_data["db"]
    client = context.bot_data["client"]
    try:
        runs = filter_runs(client.get_activities(2, fresh=True))  # ~últimas 48h
    except Exception as e:  # noqa: BLE001 — Garmin 429/fora: tenta no próximo ciclo
        _log.warning("job_runs: falha ao buscar atividades: %s", e)
        return
    seeded = db.get_state(_RUNS_SEEDED) == "1"
    for raw in runs:
        aid = raw.get("activityId")
        if aid is None or db.is_notified(aid):
            continue
        if not seeded:
            db.mark_notified(aid)          # seed silencioso
            continue
        db.upsert_activity(activity_from_garmin(raw))  # garante row pro build_run_detail
        try:
            detail = build_run_detail(db, client, aid)
        except Exception as e:  # noqa: BLE001 — splits/IA falhou: tenta depois, não marca
            _log.warning("job_runs: falha ao montar insight da corrida %s: %s", aid, e)
            continue
        await context.bot.send_message(
            chat_id=cfg.chat_id, text=messages.format_activity(detail["activity"], detail["insight"]),
            parse_mode=messages.PARSE_MODE,
        )
        db.mark_notified(aid)
    if not seeded:
        db.set_state(_RUNS_SEEDED, "1")


_BRIEFING_DATE = "briefing_date"


async def job_briefing(context: ContextTypes.DEFAULT_TYPE):
    """Domingo 19:00: resumo da semana. Auto-guard por weekday (6=domingo, Mon=0)."""
    cfg = context.bot_data["cfg"]
    db = context.bot_data["db"]
    client = context.bot_data["client"]
    today = dt.date.today()
    if today.weekday() != 6:
        return
    day = today.isoformat()
    if db.get_state(_BRIEFING_DATE) == day:
        return
    try:
        Ingestor(client, db).sync_today()
    except Exception as e:  # noqa: BLE001
        _log.warning("job_briefing: sync falhou: %s", e)
    data = build_weekly_briefing(db, today)
    await context.bot.send_message(
        chat_id=cfg.chat_id, text=messages.format_briefing(data),
        parse_mode=messages.PARSE_MODE)
    db.set_state(_BRIEFING_DATE, day)


async def job_day_plan(context: ContextTypes.DEFAULT_TYPE):
    """07:30 — manda a pergunta do plano do dia com teclado inline dp:*."""
    cfg = context.bot_data["cfg"]
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("🏋 treinar", callback_data="dp:treino"),
        InlineKeyboardButton("🏃 correr", callback_data="dp:corrida"),
    ], [
        InlineKeyboardButton("💪🏃 os 2", callback_data="dp:ambos"),
        InlineKeyboardButton("😴 descanso", callback_data="dp:descanso"),
    ]])
    await context.bot.send_message(chat_id=cfg.chat_id,
                                   text="Bom dia. Hoje você vai:", reply_markup=kb)


async def job_alerts(context: ContextTypes.DEFAULT_TYPE):
    """Diário: checa FC subindo / ACWR risco / overreaching e alerta 1x por episódio."""
    cfg = context.bot_data["cfg"]
    db = context.bot_data["db"]
    client = context.bot_data["client"]
    day = dt.date.today().isoformat()
    try:
        Ingestor(client, db).sync_today()
    except Exception as e:  # noqa: BLE001
        _log.warning("job_alerts: sync falhou: %s", e)
    try:
        ctx = context_from_metrics(db, day)
        veredito = core.daily_analysis(db, day)["veredito"]
        start7 = (dt.date.today() - dt.timedelta(days=6)).isoformat()
        hr_rows = db.get_metric_series("resting_hr", start7, day)
    except Exception as e:  # noqa: BLE001
        _log.warning("job_alerts: contexto falhou: %s", e)
        return
    over = {"kind": "overreaching", "veredito": veredito} if veredito.get("overreaching") else None
    checks = [
        ("alert_hr", alerts.hr_rising(hr_rows, ctx.get("resting_hr_baseline"))),
        ("alert_acwr", alerts.acwr_risk(ctx.get("acwr"))),
        ("alert_over", over),
    ]
    for key, detail in checks:
        if detail is not None:
            if db.get_state(key) != "1":
                await context.bot.send_message(
                    chat_id=cfg.chat_id, text=messages.format_alert(detail),
                    parse_mode=messages.PARSE_MODE)
                db.set_state(key, "1")
        else:
            db.set_state(key, "0")


async def job_weekly_weight(context: ContextTypes.DEFAULT_TYPE):
    """Pergunta o peso da semana (cadência semanal proposital; pesar todo dia é ruído)."""
    cfg = context.bot_data["cfg"]
    await context.bot.send_message(
        chat_id=cfg.chat_id,
        text="🗓 Peso da semana? Manda com /peso 107.4 — depois /progresso pra ver a tendência.",
    )
