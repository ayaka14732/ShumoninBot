"""
core/scheduler.py
Background coroutine that polls for timed-out pending users every 30 seconds.
"""

import asyncio
import logging
import time
from telegram import Bot
from config import TIMEOUT_POLL_INTERVAL_SEC, BAN_THRESHOLD
from db import queries
from core import actions

logger = logging.getLogger(__name__)


async def _handle_timeout(bot: Bot, record: dict) -> None:
    """Process a single timed-out pending user record."""
    chat_id = record["chat_id"]
    user_id = record["user_id"]

    # Idempotent lock: only proceed if status is still 'pending'
    updated = queries.update_pending_status(chat_id, user_id, "timeout")
    if not updated:
        logger.debug("Timeout: record (%s, %s) already processed, skipping", chat_id, user_id)
        return

    logger.info("Timeout triggered for user %s in chat %s", user_id, chat_id)

    # Delete the "xx joined the group" service message
    join_msg_id = record.get("join_msg_id")
    if join_msg_id:
        await actions.delete_message(bot, chat_id, join_msg_id)

    # Delete the verification message
    msg_id = record.get("question_msg_id")
    if msg_id:
        await actions.delete_message(bot, chat_id, msg_id)

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
            "User %s kicked from chat %s due to timeout (total_failures=%s)",
            user_id, chat_id, total_failures
        )


async def run_timeout_poll(bot: Bot) -> None:
    """
    Continuously poll for timed-out pending users.
    This coroutine runs indefinitely and should be started as a background task.
    """
    logger.info("Timeout scheduler started (interval=%ss)", TIMEOUT_POLL_INTERVAL_SEC)
    while True:
        try:
            timed_out = queries.get_all_timed_out_pending()
            if timed_out:
                logger.info("Timeout poll: found %d timed-out record(s)", len(timed_out))
            for record in timed_out:
                try:
                    await _handle_timeout(bot, record)
                except Exception as exc:
                    logger.error(
                        "Error handling timeout for user %s in chat %s: %s",
                        record.get("user_id"), record.get("chat_id"), exc
                    )
        except Exception as exc:
            logger.error("Timeout poll error: %s", exc)

        await asyncio.sleep(TIMEOUT_POLL_INTERVAL_SEC)


async def process_startup_timeouts(bot: Bot) -> None:
    """
    Called once at startup to handle any pending users that timed out
    while the bot was offline.
    """
    logger.info("Processing startup timeouts...")
    timed_out = queries.get_all_timed_out_pending()
    logger.info("Found %d timed-out record(s) at startup", len(timed_out))
    for record in timed_out:
        try:
            await _handle_timeout(bot, record)
        except Exception as exc:
            logger.error(
                "Startup timeout error for user %s in chat %s: %s",
                record.get("user_id"), record.get("chat_id"), exc
            )
