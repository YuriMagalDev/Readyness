import datetime as dt
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot import core, messages
from bot.checkin import CHECKINS, scale_keyboard, parse_callback, prompt_text
from bot.charts import recovery_chart_png, nutrition_chart_png
from bot.nutrition import load_food_db, today_panel
from bot.nutrition_format import format_meal_confirm
from bot.runs import filter_runs
from src.services_core import save_checkin, build_trends, build_run_detail
from src.extractors import activity_from_garmin
from src.plan_parser import parse_plan
from src.plan_tracker import match_plan, week_start_of
from src.readiness_score import compute_readiness
from src.metric_reader import context_from_metrics
from src.nutrition.meal_parser import parse_meal
import src.nutrition.store as store


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
        "/semana — resumo 7d\n/mes — resumo 30d\n"
        "/plano — registrar/ver o plano da semana"
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


def _run_button_label(raw: dict) -> str:
    data = (raw.get("startTimeLocal") or "")[:10]
    nome = raw.get("activityName") or "Corrida"
    dist = raw.get("distance")
    km = f"{dist / 1000:.1f}km" if dist else "—"
    return f"{data} · {nome} · {km}"


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


def _profile(context):
    return context.bot_data.get("profile") or {}


async def cmd_comi(update, context):
    if not _authorized(update, context):
        return
    db_path = context.bot_data["db_path"]
    text = update.message.text.partition(" ")[2].strip()
    if not text:
        await update.message.reply_text(
            "Use: /comi almoço: 100g arroz, 200g frango, 1 ovo")
        return
    fdb = load_food_db(db_path)
    parsed = parse_meal(text, fdb)
    context.user_data["pending_meal"] = parsed
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ salvar", callback_data="nut:save"),
        InlineKeyboardButton("✏️ corrigir", callback_data="nut:edit"),
    ]])
    await update.message.reply_text(format_meal_confirm(parsed), reply_markup=kb)


async def on_nutrition_button(update, context):
    if not _authorized(update, context):
        return
    q = update.callback_query
    await q.answer()
    db_path = context.bot_data["db_path"]
    day = dt.date.today().isoformat()
    if q.data == "nut:save":
        parsed = context.user_data.get("pending_meal")
        if not parsed:
            await q.edit_message_text("Nada pra salvar.")
            return
        store.save_meal_items(db_path, day, parsed.get("meal"), parsed["items"])
        context.user_data.pop("pending_meal", None)
        t = store.day_totals(db_path, day)
        await q.edit_message_text(f"Salvo. Hoje: {round(t['kcal'])} kcal · P {t['p']:.0f}")
    elif q.data == "nut:edit":
        await q.edit_message_text("Reenvie a refeição com /comi corrigindo o item.")
    elif q.data == "nut:del":
        ok = store.delete_last_meal_item(db_path, day)
        await q.edit_message_text("Última refeição apagada." if ok else "Nada pra apagar.")


async def cmd_dieta(update, context):
    if not _authorized(update, context):
        return
    db_path = context.bot_data["db_path"]
    day = dt.date.today().isoformat()
    panel = today_panel(db_path, _profile(context), day)
    titulo = "Hoje (dia treino)" if panel["training"] else "Hoje (descanso)"
    png = nutrition_chart_png(panel["totals"], panel["target"], panel["ea"], titulo=titulo)
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🗑 apagar última", callback_data="nut:del")]])
    await update.message.reply_photo(png, reply_markup=kb)


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
