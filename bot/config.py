import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


def _hm(s: str) -> tuple:
    h, m = s.strip().split(":")
    return int(h), int(m)


def _slots(s: str) -> tuple:
    return tuple(_hm(p) for p in s.split(",") if p.strip())


@dataclass
class Config:
    token: str
    chat_id: int
    checkin_hour: int
    morning_slots: tuple  # ((h, m), ...) horários de tentativa do saldo; o último é o final
    db_path: str
    vision_model: str = "claude-haiku-4-5-20251001"  # Anthropic model for label vision (Task 14 populates client)

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
            morning_slots=_slots(os.getenv("MORNING_SLOTS", "09:30,12:00,14:00")),
            db_path=os.getenv("DB_PATH", "history.db"),
            vision_model=os.getenv("VISION_MODEL", "claude-haiku-4-5-20251001"),
        )
