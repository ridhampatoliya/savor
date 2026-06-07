import os
import sqlite3
from datetime import date

DB_PATH = os.environ.get("DB_PATH", "/data/savor.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                vault TEXT NOT NULL,
                amount REAL NOT NULL,
                note TEXT,
                date TEXT NOT NULL,
                transferred INTEGER NOT NULL DEFAULT 0
            )
        """)
        # migrate existing rows that predate user_id column
        try:
            conn.execute("ALTER TABLE entries ADD COLUMN user_id INTEGER NOT NULL DEFAULT 778638074")
        except Exception:
            pass
        conn.commit()


def add_entry(user_id: int, vault: str, amount: float, note: str | None = None):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO entries (user_id, vault, amount, note, date) VALUES (?, ?, ?, ?, ?)",
            (user_id, vault, amount, note, date.today().isoformat()),
        )
        conn.commit()


def get_totals(user_id: int, transferred: bool = False) -> dict[str, float]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT vault, SUM(amount) as total FROM entries WHERE user_id = ? AND transferred = ? GROUP BY vault",
            (user_id, 1 if transferred else 0),
        ).fetchall()
    return {row["vault"]: row["total"] for row in rows}


def get_history(user_id: int, days: int = 7) -> list[sqlite3.Row]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT vault, amount, note, date FROM entries
            WHERE user_id = ? AND date >= date('now', ?)
            ORDER BY date DESC, id DESC
            """,
            (user_id, f"-{days} days"),
        ).fetchall()
    return rows


def mark_transferred(user_id: int, vault: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE entries SET transferred = 1 WHERE user_id = ? AND vault = ? AND transferred = 0",
            (user_id, vault),
        )
        conn.commit()
