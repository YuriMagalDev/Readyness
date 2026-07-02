"""Handlers core do bot (saldo, insights, checkin, tendências, plano, atividades).

Nutrição vive em bot/handlers_nutrition.py e o coach /ask em bot/handlers_ask.py;
os nomes são re-exportados aqui pra manter o wiring do main.py e imports antigos.
"""

import datetime as dt
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot import core, messages
from bot.checkin import CHECKINS, scale_keyboard, parse_callback, prompt_text
from bot.charts import recovery_chart_png
from bot.handlers_common import _authorized, _profile, _run_button_label
from bot.nutrition import today_panel
from bot.nutrition_format import format_nutri_context
from bot.runs import filter_runs
from src.services_core import save_checkin, build_trends, build_run_detail
from src.extractors import activity_from_garmin
from src.plan_parser import parse_plan
from src.plan_tracker import match_plan, week_start_of
from src.readiness_score import compute_readiness
from src.metric_reader import context_from_metrics

from bot.handlers_nutrition import (  # noqa: F401 — re-export (main.py + testes)
    _DP_MAP, parse_day_plan_callback, on_day_plan_button, parse_manual_macros,
    cmd_comi, _comi_process_text, _COMI_KB, _comi_running, _comi_add_foods,
    on_nutrition_button, _ref_view, cmd_ref, cmd_dieta, on_photo,
    on_text_nutrition, cmd_cancelar, cmd_macros, cmd_peso, _week_context,
    cmd_progresso, on_adjust_button, _food_like,
)
from bot.handlers_ask import (  # noqa: F401 — re-export (main.py + testes)
    _ASK_KB, _ASK_FIM_KB, _ASK_STYLE, _profile_file_exists, cmd_ask,
    on_ask_button, on_text_macros, _split_message, _handle_ask_turn, _ask_turn,
)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _authorized(update, context):
        return
    await update.message.reply_text(
        "Readiness bot. Comandos:\n"
        "/saldo — saldo do dia\n/insights — leitura da IA\n"
        "/checkin — responder hidratação/energia/dor/alimentação\n"
        "/semana — resumo 7d\n/mes — resumo 30d\n"
        "/plano — registrar/ver o plano da semana\n"
        "/comi — registrar refeição\n"
        "/dieta — macros e energia do dia (gráfico)\n"
        "/macros — macros de hoje em texto (consumido vs alvo)\n"
        "/ask — conversar com o coach (corrida ou assunto geral)\n"
        "/progresso — tendência de peso, BF estimado, ajuste\n"
        "/ref — refeições de hoje (editar/apagar item)\n"
        "/cancelar — cancelar registro em andamento"
    )


async def cmd_saldo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _authorized(update, context):
        return
    db = context.bot_data["db"]
    client = context.bot_data["client"]
    day = dt.date.today().isoformat()
    # métricas/sono dependem do Garmin (pode 429 / sem sync); veredito vem do DB e sempre sai
    try:
        ctx = core.load_context(client)
        met, sleep = core.collect_metrics(ctx), core.sleep_view(ctx)
    except Exception:  # noqa: BLE001
        met, sleep = {}, {}
    try:
        analysis = core.daily_analysis(db, day)
        txt = messages.format_saldo(analysis["veredito"], met, sleep=sleep)
        # nutrição = contexto informativo (não muda o veredito); nunca derruba o /saldo
        try:
            panel = today_panel(context.bot_data["db_path"], _profile(context), day)
            nutri = format_nutri_context(panel["yesterday"])
            if nutri:
                txt += "\n\n" + nutri
        except Exception:  # noqa: BLE001 — sem dados de nutrição: saldo segue normal
            pass
        await update.message.reply_text(txt, parse_mode=messages.PARSE_MODE)
    except Exception as e:  # noqa: BLE001
        await update.message.reply_text(f"Não consegui montar o saldo agora ({e}).")


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
    day = dt.date.today().isoformat()
    for c in CHECKINS:
        await update.message.reply_text(prompt_text(c), reply_markup=scale_keyboard(c["key"], day))


async def on_checkin_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _authorized(update, context):
        return
    q = update.callback_query
    parsed = parse_callback(q.data)
    if not parsed:
        await q.answer("inválido")
        return
    key, val, day = parsed
    # grava sempre no dia do check-in (vindo no callback), não no dia do clique
    save_checkin(context.bot_data["db"], {key: val}, today=dt.date.fromisoformat(day))
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


async def cmd_atividades(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _authorized(update, context):
        return
    client = context.bot_data["client"]
    try:
        runs = filter_runs(client.get_activities(7, fresh=True))[:8]   # últimas 8 corridas
    except Exception:  # noqa: BLE001
        await update.message.reply_text("Não consegui buscar suas atividades agora.")
        return
    if not runs:
        await update.message.reply_text("Nenhuma corrida recente encontrada.")
        return
    db = context.bot_data["db"]
    for r in runs:
        db.upsert_activity(activity_from_garmin(r))
    teclado = [
        [InlineKeyboardButton(_run_button_label(r), callback_data=f"act:{r['activityId']}")]
        for r in runs
    ]
    await update.message.reply_text(
        "Escolha uma corrida pra ver o insight:", reply_markup=InlineKeyboardMarkup(teclado)
    )


async def cmd_plano(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _authorized(update, context):
        return
    db = context.bot_data["db"]
    today = dt.date.today()
    week_start = week_start_of(today)
    texto = update.message.text or ""
    corpo = "\n".join(texto.splitlines()[1:]).strip()  # linhas após o /plano

    if corpo:
        plan = parse_plan(texto)
        if not plan["corrida"] and not plan["musculacao"]:
            await update.message.reply_text(
                "Formato inválido. Ex:\n/plano\nseg corrida 40min\nter musculacao superior")
            return
        db.upsert_plan(week_start, plan, dt.datetime.now().isoformat(timespec="seconds"))
        await update.message.reply_text(
            f"Plano salvo: {len(plan['corrida'])} corridas, {len(plan['musculacao'])} musculações.")

    stored = db.get_plan(week_start)
    if stored is None:
        await update.message.reply_text(
            "Nenhum plano esta semana. Registre colando:\n"
            "/plano\nseg corrida 40min\nter musculacao superior")
        return

    plan = stored["plan"]
    acts = db.get_activities(week_start, today.isoformat())
    matched = match_plan(plan, acts, today, week_start)
    try:
        ctx = context_from_metrics(db, today.isoformat())
        score, acwr = compute_readiness(ctx)["score"], ctx.get("acwr")
    except Exception:  # noqa: BLE001 — prontidão é enfeite do cabeçalho; plano sai mesmo sem ela
        score, acwr = None, None
    await update.message.reply_text(
        messages.format_plan(matched, score, acwr), parse_mode=messages.PARSE_MODE)


async def on_activity_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _authorized(update, context):
        return
    q = update.callback_query
    await q.answer()
    try:
        aid = int(q.data.split(":", 1)[1])
    except (ValueError, IndexError):
        await q.edit_message_text("Atividade inválida.")
        return
    db = context.bot_data["db"]
    client = context.bot_data["client"]
    try:
        detail = build_run_detail(db, client, aid)
    except Exception:  # noqa: BLE001
        await q.edit_message_text("Não consegui analisar essa corrida agora.")
        return
    await q.edit_message_text(
        messages.format_activity(detail["activity"], detail["insight"]),
        parse_mode=messages.PARSE_MODE,
    )
