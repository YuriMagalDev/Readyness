import datetime as dt
import json
import os
from zoneinfo import ZoneInfo
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters,
)
import anthropic

from bot.config import Config
from bot import handlers, jobs
from src.history_db import HistoryDB
from src.garmin_client import GarminClient

# JobQueue do PTB roda em UTC por padrão; ancoramos os horários no fuso local (TZ)
# pra os slots dispararem na hora certa de São Paulo, não em UTC.
TZ = ZoneInfo(os.getenv("TZ", "America/Sao_Paulo"))


def build_app() -> Application:
    cfg = Config.from_env()
    app = Application.builder().token(cfg.token).build()
    app.bot_data["cfg"] = cfg
    app.bot_data["db"] = HistoryDB(db_path=cfg.db_path)
    app.bot_data["db_path"] = cfg.db_path
    app.bot_data["client"] = GarminClient()
    try:
        with open("athlete_profile.json", encoding="utf-8") as fh:
            app.bot_data["profile"] = json.load(fh)
    except FileNotFoundError:
        app.bot_data["profile"] = {}
    try:
        app.bot_data["anthropic"] = anthropic.Anthropic()
    except Exception:  # noqa: BLE001 — sem ANTHROPIC_API_KEY: cadastro por foto fica indisponivel, bot sobe
        app.bot_data["anthropic"] = None

    app.add_handler(CommandHandler("start", handlers.cmd_start))
    app.add_handler(CommandHandler("saldo", handlers.cmd_saldo))
    app.add_handler(CommandHandler("insights", handlers.cmd_insights))
    app.add_handler(CommandHandler("checkin", handlers.cmd_checkin))
    app.add_handler(CommandHandler("semana", handlers.cmd_semana))
    app.add_handler(CommandHandler("mes", handlers.cmd_mes))
    app.add_handler(CallbackQueryHandler(handlers.on_checkin_button, pattern=r"^ci:"))
    app.add_handler(CommandHandler("atividades", handlers.cmd_atividades))
    app.add_handler(CallbackQueryHandler(handlers.on_activity_button, pattern=r"^act:"))
    app.add_handler(CommandHandler("plano", handlers.cmd_plano))
    app.add_handler(CommandHandler("comi", handlers.cmd_comi))
    app.add_handler(CommandHandler("combo", handlers.cmd_combo))
    app.add_handler(CallbackQueryHandler(handlers.on_combo_button, pattern=r"^cmb:"))
    app.add_handler(CommandHandler("dieta", handlers.cmd_dieta))
    app.add_handler(CommandHandler("ref", handlers.cmd_ref))
    app.add_handler(CommandHandler("cancelar", handlers.cmd_cancelar))
    app.add_handler(CommandHandler("macros", handlers.cmd_macros))
    app.add_handler(CommandHandler("peso", handlers.cmd_peso))
    app.add_handler(CommandHandler("progresso", handlers.cmd_progresso))
    app.add_handler(CallbackQueryHandler(handlers.on_adjust_button, pattern=r"^adj:"))
    app.add_handler(CallbackQueryHandler(handlers.on_nutrition_button, pattern=r"^nut:"))
    app.add_handler(CallbackQueryHandler(handlers.on_day_plan_button, pattern=r"^dp:"))
    app.add_handler(CommandHandler("ask", handlers.cmd_ask))
    app.add_handler(CallbackQueryHandler(handlers.on_ask_button, pattern=r"^ask:"))
    app.add_handler(MessageHandler(filters.PHOTO, handlers.on_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.on_text_macros))

    jq = app.job_queue
    for (h, m) in cfg.morning_slots:
        jq.run_daily(jobs.job_morning, time=dt.time(hour=h, minute=m, tzinfo=TZ))
    jq.run_daily(jobs.job_checkin, time=dt.time(hour=cfg.checkin_hour, minute=0, tzinfo=TZ))
    jq.run_repeating(jobs.job_runs, interval=15 * 60, first=30)
    jq.run_daily(jobs.job_alerts, time=dt.time(hour=10, minute=0, tzinfo=TZ))
    jq.run_daily(jobs.job_briefing, time=dt.time(hour=19, minute=0, tzinfo=TZ))
    jq.run_daily(jobs.job_day_plan, time=dt.time(hour=7, minute=30, tzinfo=TZ))
    # peso semanal: domingo 09:00 (day 6 = domingo no python-telegram-bot)
    jq.run_daily(jobs.job_weekly_weight, time=dt.time(hour=9, minute=0, tzinfo=TZ), days=(6,))
    return app


def main():
    app = build_app()
    app.run_polling()


if __name__ == "__main__":
    main()
