import sqlite3
import time
from pathlib import Path


class StateStore:
    def __init__(self, database_path: str):
        path = Path(database_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        self.connection = sqlite3.connect(path)
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS notified_events (
                event_key TEXT PRIMARY KEY,
                notified_at INTEGER NOT NULL
            )
            """
        )
        self.connection.commit()

    def is_notified(self, event_key: str) -> bool:
        row = self.connection.execute(
            "SELECT 1 FROM notified_events WHERE event_key = ?",
            (event_key,),
        ).fetchone()
        return row is not None

    def mark_notified(self, event_key: str):
        self.connection.execute(
            "INSERT OR IGNORE INTO notified_events (event_key, notified_at) VALUES (?, ?)",
            (event_key, int(time.time())),
        )
        self.connection.commit()

    def close(self):
        self.connection.close()
