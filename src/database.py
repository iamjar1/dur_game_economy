import sqlite3
import os
from datetime import datetime, timedelta, timezone
from contextlib import contextmanager

@contextmanager
def get_db():
    """Get database connection with row factory enabled."""
    db_path = os.getenv("DATABASE_PATH", "game_economy.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")  # Write-Ahead Logging for crash safety
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db():
    """Initialize database with schema."""
    with get_db() as conn:
        with open("migrations/001_initial.sql", "r") as f:
            conn.executescript(f.read())

def cleanup_expired_keys():
    """Remove expired idempotency keys (older than 48 hours)."""
    with get_db() as conn:
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
        conn.execute("DELETE FROM idempotency_keys WHERE expires_at < ?", (cutoff,))