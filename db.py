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
                vault TEXT NOT NULL,
                amount REAL NOT NULL,
                note TEXT,
                date TEXT NOT NULL,
                transferred INTEGER NOT NULL DEFAULT 0
            )
        """)
        conn.commit()


def add_entry(vault: str, amount: float, note: str | None = None):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO entries (vault, amount, note, date) VALUES (?, ?, ?, ?)",
            (vault, amount, note, date.today().isoformat()),
        )
        conn.commit()


def get_totals(transferred: bool = False) -> dict[str, float]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT vault, SUM(amount) as total FROM entries WHERE transferred = ? GROUP BY vault",
            (1 if transferred else 0,),
        ).fetchall()
    return {row["vault"]: row["total"] for row in rows}


def get_history(days: int = 7) -> list[sqlite3.Row]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT vault, amount, note, date FROM entries
            WHERE date >= date('now', ?)
            ORDER BY date DESC, id DESC
            """,
            (f"-{days} days",),
        ).fetchall()
    return rows


def mark_transferred(vault: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE entries SET transferred = 1 WHERE vault = ? AND transferred = 0",
            (vault,),
        )
        conn.commit()
