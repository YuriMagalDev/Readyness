import datetime as dt
import os
from zoneinfo import ZoneInfo
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
)

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
    app.bot_data["client"] = GarminClient()

    app.add_handler(CommandHandler("start", handlers.cmd_start))
    app.add_handler(CommandHandler("saldo", handlers.cmd_saldo))
    app.add_handler(CommandHandler("insights", handlers.cmd_insights))
    app.add_handler(CommandHandler("checkin", handlers.cmd_checkin))
    app.add_handler(CommandHandler("semana", handlers.cmd_semana))
    app.add_handler(CommandHandler("mes", handlers.cmd_mes))
    app.add_handler(CallbackQueryHandler(handlers.on_checkin_button, pattern=r"^ci:"))

    jq = app.job_queue
    for (h, m) in cfg.morning_slots:
        jq.run_daily(jobs.job_morning, time=dt.time(hour=h, minute=m, tzinfo=TZ))
    jq.run_daily(jobs.job_checkin, time=dt.time(hour=cfg.checkin_hour, minute=0, tzinfo=TZ))
    return app


def main():
    app = build_app()
    app.run_polling()


if __name__ == "__main__":
    main()
