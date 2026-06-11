import sqlite3

SNAPSHOT_COLUMNS = [
    "date", "resting_hr", "sleep_hours", "sleep_score",
    "body_battery_high", "body_battery_low", "stress_avg", "stress_max",
    "respiration_avg", "spo2_avg", "intensity_minutes", "steps", "floors",
    "calories_total", "calories_active",
    "race_pred_5k", "race_pred_10k", "race_pred_21k", "race_pred_42k",
    "runs", "strength", "train_minutes",
]

ACTIVITY_COLUMNS = [
    "activity_id", "date", "name", "type", "is_strength",
    "distance_m", "duration_min", "pace_min_km", "avg_hr", "max_hr",
    "calories", "cadence", "stride_length", "splits_json",
]


class HistoryDB:
    def __init__(self, db_path: str = "history.db"):
        self._db_path = db_path
        self._init_db()

    def _connect(self):
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        snap_cols = ", ".join(
            f"{c} TEXT PRIMARY KEY" if c == "date" else f"{c} REAL"
            for c in SNAPSHOT_COLUMNS
        )
        act_cols = ", ".join(
            f"{c} INTEGER PRIMARY KEY" if c == "activity_id"
            else f"{c} TEXT" if c in ("date", "name", "type", "splits_json")
            else f"{c} REAL"
            for c in ACTIVITY_COLUMNS
        )
        with self._connect() as conn:
            conn.execute(f"CREATE TABLE IF NOT EXISTS daily_snapshot ({snap_cols})")
            conn.execute(f"CREATE TABLE IF NOT EXISTS activity ({act_cols})")

    def _upsert(self, table: str, columns: list, row: dict):
        cols = [c for c in columns if c in row]
        placeholders = ", ".join("?" for _ in cols)
        col_list = ", ".join(cols)
        updates = ", ".join(f"{c}=excluded.{c}" for c in cols if c != columns[0])
        key = columns[0]
        sql = (
            f"INSERT INTO {table} ({col_list}) VALUES ({placeholders}) "
            f"ON CONFLICT({key}) DO UPDATE SET {updates}"
        )
        with self._connect() as conn:
            conn.execute(sql, [row[c] for c in cols])

    def upsert_snapshot(self, row: dict):
        self._upsert("daily_snapshot", SNAPSHOT_COLUMNS, row)

    def upsert_activity(self, row: dict):
        self._upsert("activity", ACTIVITY_COLUMNS, row)

    def get_snapshots(self, start: str, end: str) -> list:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM daily_snapshot WHERE date >= ? AND date <= ? ORDER BY date ASC",
                (start, end),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_activities(self, start: str, end: str) -> list:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM activity WHERE date >= ? AND date <= ? ORDER BY date DESC",
                (start, end),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_activity(self, activity_id: int):
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM activity WHERE activity_id = ?", (activity_id,)
            ).fetchone()
        return dict(row) if row else None

    def latest_snapshot_date(self):
        with self._connect() as conn:
            row = conn.execute("SELECT MAX(date) AS d FROM daily_snapshot").fetchone()
        return row["d"] if row and row["d"] else None
