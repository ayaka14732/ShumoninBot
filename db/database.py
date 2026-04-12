"""
db/database.py
SQLite connection initialization and table creation.
"""

import sqlite3
import threading
import logging
from config import DB_PATH

logger = logging.getLogger(__name__)

# Thread-local storage for SQLite connections
_local = threading.local()


def get_conn() -> sqlite3.Connection:
    """Return a thread-local SQLite connection."""
    if not hasattr(_local, "conn") or _local.conn is None:
        _local.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _local.conn.row_factory = sqlite3.Row
        _local.conn.execute("PRAGMA journal_mode=WAL")
        _local.conn.execute("PRAGMA foreign_keys=ON")
    return _local.conn


def init_db() -> None:
    """Create all required tables if they do not exist."""
    conn = get_conn()
    with conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS group_settings (
                chat_id     INTEGER PRIMARY KEY,
                question    TEXT    NOT NULL DEFAULT '',
                expected    TEXT    NOT NULL DEFAULT '',
                timeout_sec INTEGER NOT NULL DEFAULT 300
            );

            CREATE TABLE IF NOT EXISTS pending_users (
                chat_id         INTEGER NOT NULL,
                user_id         INTEGER NOT NULL,
                username        TEXT,
                display_name    TEXT,
                join_time       INTEGER NOT NULL,
                expire_time     INTEGER NOT NULL,
                attempt         INTEGER NOT NULL DEFAULT 1,
                question_msg_id INTEGER,
                conversation    TEXT    NOT NULL DEFAULT '[]',
                status          TEXT    NOT NULL DEFAULT 'pending',
                ai_fail_count   INTEGER NOT NULL DEFAULT 0,
                answer_rounds   INTEGER NOT NULL DEFAULT 0,
                pending_msg_ids TEXT    NOT NULL DEFAULT '[]',
                PRIMARY KEY (chat_id, user_id)
            );

            CREATE TABLE IF NOT EXISTS user_history (
                chat_id         INTEGER NOT NULL,
                user_id         INTEGER NOT NULL,
                total_failures  INTEGER NOT NULL DEFAULT 0,
                is_banned       INTEGER NOT NULL DEFAULT 0,
                last_join_time  INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (chat_id, user_id)
            );

            CREATE TABLE IF NOT EXISTS admin_sessions (
                chat_id         INTEGER NOT NULL,
                admin_user_id   INTEGER NOT NULL,
                step            TEXT    NOT NULL,
                temp_data       TEXT    NOT NULL DEFAULT '{}',
                created_at      INTEGER NOT NULL,
                PRIMARY KEY (chat_id, admin_user_id)
            );
        """)
    # Migration: add join_msg_id column to pending_users if it doesn't exist yet
    try:
        conn.execute("ALTER TABLE pending_users ADD COLUMN join_msg_id INTEGER")
        logger.info("Migrated pending_users: added join_msg_id column")
    except Exception:
        pass  # Column already exists

    logger.info("Database initialized at %s", DB_PATH)
