"""Backfill inicial do histórico (3 meses). Rodar uma vez:
    python scripts/backfill.py
Throttle embutido para evitar rate limit do Garmin."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.garmin_client import GarminClient
from src.history_db import HistoryDB
from src.ingestor import Ingestor

DAYS = 90

if __name__ == "__main__":
    client = GarminClient()
    db = HistoryDB()
    ing = Ingestor(client, db, sleep_seconds=1.5)
    print(f"Backfill de {DAYS} dias (resume de onde parou)...")
    ing.backfill(days=DAYS)
    rows = db.get_snapshots("2000-01-01", "2100-01-01")
    print(f"OK — {len(rows)} snapshots no history.db")
