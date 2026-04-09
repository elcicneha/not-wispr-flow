"""Transcript history storage for Not Wispr Flow.

Uses SQLite for persistent, fast access to past transcriptions.
DB file: ~/.config/notwisprflow/transcript_history.db
Size cap: 5MB — oldest entries pruned automatically when exceeded.
"""

import os
import sqlite3
import logging
from datetime import datetime

logger = logging.getLogger("notwisprflow")

_DB_DIR = os.path.expanduser("~/.config/notwisprflow")
_DB_PATH = os.path.join(_DB_DIR, "transcript_history.db")
_MAX_SIZE_BYTES = 5 * 1024 * 1024  # 5MB
_PRUNE_FRACTION = 0.2              # Delete oldest 20% when over limit


def init_db():
    """Create the transcripts table if it doesn't exist."""
    try:
        os.makedirs(_DB_DIR, exist_ok=True)
        with _connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS transcripts (
                    id        INTEGER PRIMARY KEY AUTOINCREMENT,
                    text      TEXT    NOT NULL,
                    timestamp TEXT    NOT NULL
                )
            """)
    except Exception as e:
        logger.warning(f"Transcript history: failed to init DB: {e}")


def _connect():
    return sqlite3.connect(_DB_PATH, timeout=5)


def add_transcript(text):
    """Save a new transcript. Prunes oldest entries if DB exceeds 5MB."""
    if not text or not text.strip():
        return
    try:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with _connect() as conn:
            conn.execute(
                "INSERT INTO transcripts (text, timestamp) VALUES (?, ?)", (text, ts)
            )
        _prune_if_needed()
    except Exception as e:
        logger.warning(f"Transcript history: failed to save: {e}")


def _prune_if_needed():
    """Delete the oldest 20% of rows when the DB file exceeds 5MB."""
    try:
        if not os.path.exists(_DB_PATH):
            return
        size = os.path.getsize(_DB_PATH)
        if size <= _MAX_SIZE_BYTES:
            return
        with _connect() as conn:
            count = conn.execute("SELECT COUNT(*) FROM transcripts").fetchone()[0]
            to_delete = max(1, int(count * _PRUNE_FRACTION))
            conn.execute(
                "DELETE FROM transcripts WHERE id IN "
                "(SELECT id FROM transcripts ORDER BY id ASC LIMIT ?)",
                (to_delete,),
            )
            conn.execute("VACUUM")
        logger.info(f"Transcript history: pruned {to_delete} oldest entries (DB exceeded 5MB)")
    except Exception as e:
        logger.warning(f"Transcript history: failed to prune: {e}")


def get_recent(n=10):
    """Return the n most recent transcripts, newest first.

    Returns:
        list of (id, text, timestamp) tuples
    """
    try:
        with _connect() as conn:
            return conn.execute(
                "SELECT id, text, timestamp FROM transcripts ORDER BY id DESC LIMIT ?", (n,)
            ).fetchall()
    except Exception as e:
        logger.warning(f"Transcript history: failed to load recent: {e}")
        return []


def get_all():
    """Return all transcripts, newest first.

    Returns:
        list of (id, text, timestamp) tuples
    """
    try:
        with _connect() as conn:
            return conn.execute(
                "SELECT id, text, timestamp FROM transcripts ORDER BY id DESC"
            ).fetchall()
    except Exception as e:
        logger.warning(f"Transcript history: failed to load all: {e}")
        return []
