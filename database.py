"""
database.py – SQLite setup and connection helper for Household Ops.
"""
import sqlite3
import os
from pathlib import Path

DB_PATH = Path(__file__).parent / "household_ops.db"


def get_conn() -> sqlite3.Connection:
    """Return a connection with row_factory so results come back as dicts."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    """Create tables if they don't already exist."""
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS pantry (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                name    TEXT    NOT NULL COLLATE NOCASE,
                qty     REAL    NOT NULL DEFAULT 0,
                unit    TEXT    NOT NULL DEFAULT 'pcs',
                expires TEXT    DEFAULT NULL   -- ISO-8601 date or NULL
            );

            CREATE TABLE IF NOT EXISTS bills (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                name    TEXT    NOT NULL,
                amount  REAL    NOT NULL,
                due     TEXT    NOT NULL   -- ISO-8601 date
            );

            CREATE TABLE IF NOT EXISTS shopping (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                item    TEXT    NOT NULL COLLATE NOCASE,
                qty     REAL    NOT NULL DEFAULT 1,
                unit    TEXT    NOT NULL DEFAULT 'pcs',
                UNIQUE(item)
            );
        """)
