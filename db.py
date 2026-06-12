"""
db.py — SQLite database initialisation for RepoGuard AI auth system.
Tables:
  - users:       id, email, password_hash, plan, created_at
  - token_usage: id, user_id, date, tokens_used, analyses_count
"""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "repoguard.db")


def get_connection() -> sqlite3.Connection:
    """Return a new SQLite connection with row_factory for dict-like access."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create tables if they do not already exist."""
    conn = get_connection()
    cur = conn.cursor()

    cur.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            email         TEXT    NOT NULL UNIQUE,
            password_hash TEXT    NOT NULL,
            plan          TEXT    NOT NULL DEFAULT 'free',
            created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS token_usage (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id        INTEGER NOT NULL,
            date           TEXT    NOT NULL,       -- ISO date: YYYY-MM-DD
            tokens_used    INTEGER NOT NULL DEFAULT 0,
            analyses_count INTEGER NOT NULL DEFAULT 0,
            UNIQUE (user_id, date),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
    """)

    conn.commit()
    conn.close()


# Automatically initialise on import
init_db()
