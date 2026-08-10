"""SQLite access + schema init for the Copyright Corpus.

DB path is overridable for deployment (CORPUS_DB_PATH -> a persistent disk), defaulting
to the in-repo db/corpus.db for local dev. WAL mode so the web layer's reads never block
ingest writes. foreign_keys ON on every connection.
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.environ.get("CORPUS_DB_PATH") or (REPO_ROOT / "db" / "corpus.db"))
SCHEMA_PATH = REPO_ROOT / "db" / "schema.sql"


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def init_db() -> sqlite3.Connection:
    """Create db/corpus.db from schema.sql (idempotent — schema uses IF NOT EXISTS)."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = connect()
    conn.executescript(SCHEMA_PATH.read_text())
    seed = REPO_ROOT / "db" / "seed_jurisdictions.sql"
    if seed.exists():
        conn.executescript(seed.read_text())
    conn.commit()
    return conn


if __name__ == "__main__":
    init_db()
    print(f"initialized {DB_PATH}")
