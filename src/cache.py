import json
import sqlite3
import time

class Cache:
    def __init__(self, db_path: str = "cache.db", ttl_hours: float = 6.0):
        self._db_path = db_path
        self._ttl_seconds = ttl_hours * 3600
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    expires_at REAL NOT NULL
                )
            """)

    def get(self, key: str):
        with sqlite3.connect(self._db_path) as conn:
            row = conn.execute(
                "SELECT value, expires_at FROM cache WHERE key = ?", (key,)
            ).fetchone()
        if row is None:
            return None
        value, expires_at = row
        if time.time() > expires_at:
            return None
        return json.loads(value)

    def set(self, key: str, data) -> None:
        expires_at = time.time() + self._ttl_seconds
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO cache (key, value, expires_at) VALUES (?, ?, ?)",
                (key, json.dumps(data), expires_at),
            )

    def clear(self) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("DELETE FROM cache")
