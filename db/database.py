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
                expiry_sec  INTEGER NOT NULL DEFAULT 120
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
                join_msg_id     INTEGER,
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
    # Migration: rename timeout_sec → expiry_sec in group_settings
    try:
        conn.execute("ALTER TABLE group_settings RENAME COLUMN timeout_sec TO expiry_sec")
        logger.info("Migrated group_settings: renamed timeout_sec to expiry_sec")
    except Exception:
        pass  # Column already renamed or doesn't exist

    # Migration: rename status value 'timeout' → 'expired' in pending_users
    try:
        conn.execute("UPDATE pending_users SET status = 'expired' WHERE status = 'timeout'")
        logger.info("Migrated pending_users: renamed status 'timeout' to 'expired'")
    except Exception:
        pass

    logger.info("Database initialized at %s", DB_PATH)
