"""
core/scheduler.py
Background coroutine that polls for expired pending users every 30 seconds.
"""

import asyncio
import logging
from telegram import Bot
from config import EXPIRY_POLL_INTERVAL_SEC, BAN_THRESHOLD
from db import queries
from core import actions

logger = logging.getLogger(__name__)


async def _handle_expiry(bot: Bot, record: dict) -> None:
    """Process a single expired pending user record."""
    chat_id = record["chat_id"]
    user_id = record["user_id"]

    # Idempotent lock: only proceed if status is still 'pending'
    updated = queries.update_pending_status(chat_id, user_id, "expired")
    if not updated:
        logger.debug("Verification expiry: record (%s, %s) already processed, skipping", chat_id, user_id)
        return

    logger.info("Verification expiry triggered for user %s in chat %s", user_id, chat_id)

    # Delete the "xx joined the group" service message
    join_msg_id = record.get("join_msg_id")
    if join_msg_id:
        await actions.delete_message(bot, chat_id, join_msg_id)

    # Delete the verification message
    msg_id = record.get("question_msg_id")
    if msg_id:
        await actions.delete_message(bot, chat_id, msg_id)

    # Delete user's messages sent during verification (best-effort)
    for pending_msg_id in queries.get_pending_msg_ids(chat_id, user_id):
        await actions.delete_message(bot, chat_id, pending_msg_id)

    # Increment failure counter and decide kick vs ban
    total_failures = queries.increment_total_failures(chat_id, user_id)
    if total_failures >= BAN_THRESHOLD:
        await actions.ban_user(bot, chat_id, user_id)
        queries.set_user_banned(chat_id, user_id, True)
        logger.info(
            "User %s permanently banned in chat %s (total_failures=%s)",
            user_id, chat_id, total_failures
        )
    else:
        await actions.kick_user(bot, chat_id, user_id)
        logger.info(
            "User %s kicked from chat %s due to verification expiry (total_failures=%s)",
            user_id, chat_id, total_failures
        )


async def run_expiry_poll(bot: Bot) -> None:
    """
    Continuously poll for expired pending users.
    This coroutine runs indefinitely and should be started as a background task.
    """
    logger.info("Verification expiry scheduler started (interval=%ss)", EXPIRY_POLL_INTERVAL_SEC)
    while True:
        try:
            expired = queries.get_all_expired_pending()
            if expired:
                logger.info("Verification expiry poll: found %d expired record(s)", len(expired))
            for record in expired:
                try:
                    await _handle_expiry(bot, record)
                except Exception as exc:
                    logger.error(
                        "Error handling verification expiry for user %s in chat %s: %s",
                        record.get("user_id"), record.get("chat_id"), exc
                    )
        except Exception as exc:
            logger.error("Verification expiry poll error: %s", exc)

        await asyncio.sleep(EXPIRY_POLL_INTERVAL_SEC)


async def process_startup_expiries(bot: Bot) -> None:
    """
    Called once at startup to handle any pending users whose verification
    expired while the bot was offline.
    """
    logger.info("Processing startup verification expiries...")
    expired = queries.get_all_expired_pending()
    logger.info("Found %d expired verification record(s) at startup", len(expired))
    for record in expired:
        try:
            await _handle_expiry(bot, record)
        except Exception as exc:
            logger.error(
                "Startup verification expiry error for user %s in chat %s: %s",
                record.get("user_id"), record.get("chat_id"), exc
            )
