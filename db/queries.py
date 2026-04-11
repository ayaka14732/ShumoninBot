"""
db/queries.py
All database CRUD operations.
"""

import json
import time
import logging
from typing import Optional
from db.database import get_conn

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# group_settings
# ---------------------------------------------------------------------------

def get_group_settings(chat_id: int) -> Optional[dict]:
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM group_settings WHERE chat_id = ?", (chat_id,)
    ).fetchone()
    return dict(row) if row else None


def upsert_group_settings(chat_id: int, question: str, expected: str, timeout_sec: int) -> None:
    conn = get_conn()
    with conn:
        conn.execute("""
            INSERT INTO group_settings (chat_id, question, expected, timeout_sec)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET
                question    = excluded.question,
                expected    = excluded.expected,
                timeout_sec = excluded.timeout_sec
        """, (chat_id, question, expected, timeout_sec))


def update_group_question(chat_id: int, question: str) -> None:
    conn = get_conn()
    with conn:
        conn.execute("""
            INSERT INTO group_settings (chat_id, question, expected, timeout_sec)
            VALUES (?, ?, '', 300)
            ON CONFLICT(chat_id) DO UPDATE SET question = excluded.question
        """, (chat_id, question))


def update_group_expected(chat_id: int, expected: str) -> None:
    conn = get_conn()
    with conn:
        conn.execute("""
            INSERT INTO group_settings (chat_id, question, expected, timeout_sec)
            VALUES (?, '', ?, 300)
            ON CONFLICT(chat_id) DO UPDATE SET expected = excluded.expected
        """, (chat_id, expected))


def update_group_timeout(chat_id: int, timeout_sec: int) -> None:
    conn = get_conn()
    with conn:
        conn.execute("""
            INSERT INTO group_settings (chat_id, question, expected, timeout_sec)
            VALUES (?, '', '', ?)
            ON CONFLICT(chat_id) DO UPDATE SET timeout_sec = excluded.timeout_sec
        """, (chat_id, timeout_sec))


# ---------------------------------------------------------------------------
# pending_users
# ---------------------------------------------------------------------------

def get_pending_user(chat_id: int, user_id: int) -> Optional[dict]:
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM pending_users WHERE chat_id = ? AND user_id = ?",
        (chat_id, user_id)
    ).fetchone()
    return dict(row) if row else None


def insert_pending_user(
    chat_id: int,
    user_id: int,
    username: Optional[str],
    display_name: str,
    expire_time: int,
    attempt: int,
) -> None:
    now = int(time.time())
    conn = get_conn()
    with conn:
        conn.execute("""
            INSERT OR REPLACE INTO pending_users
                (chat_id, user_id, username, display_name, join_time, expire_time,
                 attempt, question_msg_id, conversation, status, ai_fail_count, answer_rounds)
            VALUES (?, ?, ?, ?, ?, ?, ?, NULL, '[]', 'pending', 0, 0)
        """, (chat_id, user_id, username, display_name, now, expire_time, attempt))


def update_pending_question_msg_id(chat_id: int, user_id: int, msg_id: int) -> None:
    conn = get_conn()
    with conn:
        conn.execute(
            "UPDATE pending_users SET question_msg_id = ? WHERE chat_id = ? AND user_id = ?",
            (msg_id, chat_id, user_id)
        )


def get_pending_question_msg_id(chat_id: int, user_id: int) -> Optional[int]:
    conn = get_conn()
    row = conn.execute(
        "SELECT question_msg_id FROM pending_users WHERE chat_id = ? AND user_id = ?",
        (chat_id, user_id)
    ).fetchone()
    return row["question_msg_id"] if row else None


def update_pending_status(chat_id: int, user_id: int, status: str) -> bool:
    """
    Idempotent status update: only updates if current status is 'pending'.
    Returns True if the update was applied, False if skipped (already changed).
    """
    conn = get_conn()
    with conn:
        cursor = conn.execute("""
            UPDATE pending_users
            SET status = ?
            WHERE chat_id = ? AND user_id = ? AND status = 'pending'
        """, (status, chat_id, user_id))
    return cursor.rowcount > 0


def append_conversation(chat_id: int, user_id: int, role: str, content: str, max_turns: int = 10) -> None:
    """Append a message to the conversation history, trimming to max_turns pairs."""
    conn = get_conn()
    row = conn.execute(
        "SELECT conversation FROM pending_users WHERE chat_id = ? AND user_id = ?",
        (chat_id, user_id)
    ).fetchone()
    if not row:
        return
    history = json.loads(row["conversation"])
    history.append({"role": role, "content": content})
    # Keep at most max_turns * 2 entries (each turn = user + assistant)
    if len(history) > max_turns * 2:
        history = history[-(max_turns * 2):]
    with conn:
        conn.execute(
            "UPDATE pending_users SET conversation = ? WHERE chat_id = ? AND user_id = ?",
            (json.dumps(history, ensure_ascii=False), chat_id, user_id)
        )


def increment_answer_rounds(chat_id: int, user_id: int) -> int:
    """Increment answer_rounds counter and return the new value."""
    conn = get_conn()
    with conn:
        conn.execute("""
            UPDATE pending_users SET answer_rounds = answer_rounds + 1
            WHERE chat_id = ? AND user_id = ?
        """, (chat_id, user_id))
    row = conn.execute(
        "SELECT answer_rounds FROM pending_users WHERE chat_id = ? AND user_id = ?",
        (chat_id, user_id)
    ).fetchone()
    return row["answer_rounds"] if row else 0


def increment_ai_fail_count(chat_id: int, user_id: int) -> int:
    """Increment AI failure counter and return the new value."""
    conn = get_conn()
    with conn:
        conn.execute("""
            UPDATE pending_users SET ai_fail_count = ai_fail_count + 1
            WHERE chat_id = ? AND user_id = ?
        """, (chat_id, user_id))
    row = conn.execute(
        "SELECT ai_fail_count FROM pending_users WHERE chat_id = ? AND user_id = ?",
        (chat_id, user_id)
    ).fetchone()
    return row["ai_fail_count"] if row else 0


def reset_ai_fail_count(chat_id: int, user_id: int) -> None:
    conn = get_conn()
    with conn:
        conn.execute(
            "UPDATE pending_users SET ai_fail_count = 0 WHERE chat_id = ? AND user_id = ?",
            (chat_id, user_id)
        )


def append_pending_msg_id(chat_id: int, user_id: int, msg_id: int) -> None:
    """Record a message ID sent by the pending user during this verification session."""
    conn = get_conn()
    row = conn.execute(
        "SELECT pending_msg_ids FROM pending_users WHERE chat_id = ? AND user_id = ?",
        (chat_id, user_id)
    ).fetchone()
    if not row:
        return
    ids = json.loads(row["pending_msg_ids"])
    ids.append(msg_id)
    with conn:
        conn.execute(
            "UPDATE pending_users SET pending_msg_ids = ? WHERE chat_id = ? AND user_id = ?",
            (json.dumps(ids), chat_id, user_id)
        )


def get_pending_msg_ids(chat_id: int, user_id: int) -> list[int]:
    """Return all message IDs sent by the pending user during this verification session."""
    conn = get_conn()
    row = conn.execute(
        "SELECT pending_msg_ids FROM pending_users WHERE chat_id = ? AND user_id = ?",
        (chat_id, user_id)
    ).fetchone()
    if not row:
        return []
    return json.loads(row["pending_msg_ids"])


def get_all_timed_out_pending() -> list[dict]:
    """Return all pending records that have passed their expire_time."""
    now = int(time.time())
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM pending_users WHERE status = 'pending' AND expire_time < ?",
        (now,)
    ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# user_history
# ---------------------------------------------------------------------------

def get_user_history(chat_id: int, user_id: int) -> Optional[dict]:
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM user_history WHERE chat_id = ? AND user_id = ?",
        (chat_id, user_id)
    ).fetchone()
    return dict(row) if row else None


def ensure_user_history(chat_id: int, user_id: int) -> dict:
    """Get or create a user_history record."""
    history = get_user_history(chat_id, user_id)
    if history is None:
        now = int(time.time())
        conn = get_conn()
        with conn:
            conn.execute("""
                INSERT OR IGNORE INTO user_history
                    (chat_id, user_id, total_failures, is_banned, last_join_time)
                VALUES (?, ?, 0, 0, ?)
            """, (chat_id, user_id, now))
        history = get_user_history(chat_id, user_id)
    return history


def increment_total_failures(chat_id: int, user_id: int) -> int:
    """Increment total_failures and return the new value."""
    ensure_user_history(chat_id, user_id)
    conn = get_conn()
    with conn:
        conn.execute("""
            UPDATE user_history SET total_failures = total_failures + 1
            WHERE chat_id = ? AND user_id = ?
        """, (chat_id, user_id))
    row = conn.execute(
        "SELECT total_failures FROM user_history WHERE chat_id = ? AND user_id = ?",
        (chat_id, user_id)
    ).fetchone()
    return row["total_failures"] if row else 0


def set_user_banned(chat_id: int, user_id: int, banned: bool) -> None:
    ensure_user_history(chat_id, user_id)
    conn = get_conn()
    with conn:
        conn.execute("""
            UPDATE user_history SET is_banned = ?
            WHERE chat_id = ? AND user_id = ?
        """, (1 if banned else 0, chat_id, user_id))


def reset_user_history(chat_id: int, user_id: int) -> None:
    """Reset failures and banned status (used by /unban command)."""
    conn = get_conn()
    with conn:
        conn.execute("""
            UPDATE user_history
            SET total_failures = 0, is_banned = 0
            WHERE chat_id = ? AND user_id = ?
        """, (chat_id, user_id))


def update_last_join_time(chat_id: int, user_id: int) -> None:
    now = int(time.time())
    ensure_user_history(chat_id, user_id)
    conn = get_conn()
    with conn:
        conn.execute("""
            UPDATE user_history SET last_join_time = ?
            WHERE chat_id = ? AND user_id = ?
        """, (now, chat_id, user_id))


# ---------------------------------------------------------------------------
# admin_sessions
# ---------------------------------------------------------------------------

def get_admin_session(chat_id: int, admin_user_id: int) -> Optional[dict]:
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM admin_sessions WHERE chat_id = ? AND admin_user_id = ?",
        (chat_id, admin_user_id)
    ).fetchone()
    return dict(row) if row else None


def upsert_admin_session(chat_id: int, admin_user_id: int, step: str, temp_data: dict) -> None:
    now = int(time.time())
    conn = get_conn()
    with conn:
        conn.execute("""
            INSERT INTO admin_sessions (chat_id, admin_user_id, step, temp_data, created_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(chat_id, admin_user_id) DO UPDATE SET
                step       = excluded.step,
                temp_data  = excluded.temp_data,
                created_at = excluded.created_at
        """, (chat_id, admin_user_id, step, json.dumps(temp_data, ensure_ascii=False), now))


def delete_admin_session(chat_id: int, admin_user_id: int) -> None:
    conn = get_conn()
    with conn:
        conn.execute(
            "DELETE FROM admin_sessions WHERE chat_id = ? AND admin_user_id = ?",
            (chat_id, admin_user_id)
        )


def is_admin_session_expired(session: dict, expiry_sec: int) -> bool:
    return int(time.time()) - session["created_at"] > expiry_sec
