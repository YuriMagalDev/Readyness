import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


def _hm(s: str) -> tuple:
    h, m = s.split(":")
    return int(h), int(m)


@dataclass
class Config:
    token: str
    chat_id: int
    checkin_hour: int
    wake_start: tuple
    wake_end: tuple
    wake_poll_minutes: int
    db_path: str

    @classmethod
    def from_env(cls) -> "Config":
        token = os.getenv("TELEGRAM_TOKEN")
        chat = os.getenv("TELEGRAM_CHAT_ID")
        if not token or not chat:
            raise ValueError("TELEGRAM_TOKEN e TELEGRAM_CHAT_ID são obrigatórios")
        return cls(
            token=token,
            chat_id=int(chat),
            checkin_hour=int(os.getenv("CHECKIN_HOUR", "21")),
            wake_start=_hm(os.getenv("WAKE_WINDOW_START", "05:00")),
            wake_end=_hm(os.getenv("WAKE_WINDOW_END", "11:00")),
            wake_poll_minutes=int(os.getenv("WAKE_POLL_MINUTES", "15")),
            db_path=os.getenv("DB_PATH", "history.db"),
        )
