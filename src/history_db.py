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
    "calories", "cadence", "stride_length", "splits_json", "sets_json",
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
            else f"{c} TEXT" if c in ("date", "name", "type", "splits_json", "sets_json")
            else f"{c} REAL"
            for c in ACTIVITY_COLUMNS
        )
        def snap_type(c: str) -> str:
            return "TEXT PRIMARY KEY" if c == "date" else "REAL"

        def act_type(c: str) -> str:
            if c == "activity_id":
                return "INTEGER PRIMARY KEY"
            return "TEXT" if c in ("date", "name", "type", "splits_json", "sets_json") else "REAL"

        with self._connect() as conn:
            conn.execute(f"CREATE TABLE IF NOT EXISTS daily_snapshot ({snap_cols})")
            conn.execute(f"CREATE TABLE IF NOT EXISTS activity ({act_cols})")
            # migração: tabela antiga pode não ter colunas novas (CREATE IF NOT EXISTS
            # não altera tabela existente). Adiciona as que faltam sem quebrar dados.
            self._add_missing_columns(conn, "daily_snapshot", SNAPSHOT_COLUMNS, snap_type)
            self._add_missing_columns(conn, "activity", ACTIVITY_COLUMNS, act_type)
            conn.execute(
                "CREATE TABLE IF NOT EXISTS weekly_plan ("
                "week_start TEXT PRIMARY KEY, plan_json TEXT NOT NULL, created_at TEXT NOT NULL)"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS ai_insights ("
                "kind TEXT NOT NULL, cache_key TEXT NOT NULL, "
                "payload TEXT NOT NULL, created_at TEXT NOT NULL, "
                "PRIMARY KEY (kind, cache_key))"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS metric_value ("
                "date TEXT NOT NULL, metric_key TEXT NOT NULL, value REAL, "
                "measured_at TEXT, source TEXT NOT NULL, "
                "PRIMARY KEY (date, metric_key))"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS bot_state ("
                "key TEXT PRIMARY KEY, value TEXT)"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS notified_activity ("
                "activity_id INTEGER PRIMARY KEY, sent_at TEXT)"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS meal_log ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT NOT NULL, "
                "meal TEXT, food TEXT, grams REAL, kcal REAL, p REAL, c REAL, g REAL, "
                "logged_at TEXT NOT NULL)"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS day_plan ("
                "date TEXT PRIMARY KEY, vai_treinar INTEGER, vai_correr INTEGER, set_at TEXT)"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS custom_foods ("
                "name TEXT PRIMARY KEY, base_unit TEXT NOT NULL, porcao_g REAL, "
                "kcal REAL, p REAL, c REAL, g REAL, created_at TEXT NOT NULL, "
                "source TEXT)"
            )
            # migração: custom_foods antiga pode não ter a coluna source.
            cols = {r[1] for r in conn.execute("PRAGMA table_info(custom_foods)")}
            if "source" not in cols:
                conn.execute("ALTER TABLE custom_foods ADD COLUMN source TEXT")

    @staticmethod
    def _add_missing_columns(conn, table: str, columns: list, type_for):
        existing = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
        for c in columns:
            if c in existing:
                continue
            # ALTER não aceita PRIMARY KEY; chaves já existem na tabela original.
            sql_type = type_for(c).replace(" PRIMARY KEY", "")
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {c} {sql_type}")

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

    def is_notified(self, activity_id: int) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM notified_activity WHERE activity_id = ?", (activity_id,)
            ).fetchone()
        return row is not None

    def mark_notified(self, activity_id: int):
        import datetime as _dt
        with self._connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO notified_activity (activity_id, sent_at) VALUES (?, ?)",
                (activity_id, _dt.datetime.now().isoformat(timespec="seconds")),
            )

    def upsert_plan(self, week_start: str, plan: dict, created_at: str):
        import json as _json
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO weekly_plan (week_start, plan_json, created_at) VALUES (?, ?, ?) "
                "ON CONFLICT(week_start) DO UPDATE SET plan_json=excluded.plan_json, "
                "created_at=excluded.created_at",
                (week_start, _json.dumps(plan), created_at),
            )

    def get_plan(self, week_start: str):
        import json as _json
        with self._connect() as conn:
            row = conn.execute(
                "SELECT plan_json, created_at FROM weekly_plan WHERE week_start = ?", (week_start,)
            ).fetchone()
        if row is None:
            return None
        return {"plan": _json.loads(row["plan_json"]), "created_at": row["created_at"]}

    def get_insight(self, kind: str, cache_key: str):
        import json as _json
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload FROM ai_insights WHERE kind = ? AND cache_key = ?",
                (kind, cache_key),
            ).fetchone()
        return _json.loads(row["payload"]) if row else None

    def set_insight(self, kind: str, cache_key: str, payload, created_at: str) -> None:
        import json as _json
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO ai_insights (kind, cache_key, payload, created_at) "
                "VALUES (?, ?, ?, ?) ON CONFLICT(kind, cache_key) DO UPDATE SET "
                "payload=excluded.payload, created_at=excluded.created_at",
                (kind, cache_key, _json.dumps(payload), created_at),
            )

    def upsert_metric(self, date: str, metric_key: str, value, measured_at, source: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO metric_value (date, metric_key, value, measured_at, source) "
                "VALUES (?, ?, ?, ?, ?) ON CONFLICT(date, metric_key) DO UPDATE SET "
                "value=excluded.value, measured_at=excluded.measured_at, source=excluded.source",
                (date, metric_key, value, measured_at, source),
            )

    def get_metrics(self, date: str) -> list:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT date, metric_key, value, measured_at, source FROM metric_value "
                "WHERE date = ? ORDER BY metric_key", (date,)
            ).fetchall()
        return [dict(r) for r in rows]

    def get_metric_series(self, metric_key: str, start: str, end: str) -> list:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT date, metric_key, value, measured_at, source FROM metric_value "
                "WHERE metric_key = ? AND date >= ? AND date <= ? ORDER BY date ASC",
                (metric_key, start, end)
            ).fetchall()
        return [dict(r) for r in rows]

    def delete_insight(self, kind: str, cache_key: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM ai_insights WHERE kind = ? AND cache_key = ?",
                (kind, cache_key),
            )

    def get_metrics_for_date(self, day: str) -> list:
        with self._connect() as conn:
            return [dict(r) for r in conn.execute(
                "SELECT metric_key, value, measured_at, source FROM metric_value "
                "WHERE date = ?", (day,)
            )]

    def get_state(self, key: str):
        with self._connect() as conn:
            row = conn.execute(
                "SELECT value FROM bot_state WHERE key = ?", (key,)
            ).fetchone()
            return row["value"] if row else None

    def set_state(self, key: str, value: str):
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO bot_state (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value),
            )

    def latest_snapshot_date(self):
        with self._connect() as conn:
            row = conn.execute("SELECT MAX(date) AS d FROM daily_snapshot").fetchone()
        return row["d"] if row and row["d"] else None
