"""
handlers/shared.py
Shared verification outcome flows: handle_success, handle_failure.
Used by message.py, join.py, and scheduler.py.
"""

import asyncio
import logging
from telegram import Bot
from config import BAN_THRESHOLD
from db import queries
from core import actions

logger = logging.getLogger(__name__)


async def handle_success(bot: Bot, chat_id: int, user_id: int) -> None:
    """
    Verification passed:
    - Restore full permissions
    - Delete the verification message
    - Update status to 'passed'
    - Send a brief welcome message (auto-deleted after 10s)
    """
    # Idempotent status update
    updated = queries.update_pending_status(chat_id, user_id, "passed")
    if not updated:
        logger.debug("Success: record (%s, %s) already processed, skipping", chat_id, user_id)
        return

    # Restore permissions
    await actions.unrestrict_user(bot, chat_id, user_id)

    # Delete verification message
    msg_id = queries.get_pending_question_msg_id(chat_id, user_id)
    if msg_id:
        await actions.delete_message(bot, chat_id, msg_id)

    # Send welcome message and auto-delete after 10 seconds
    try:
        mention = f'<a href="tg://user?id={user_id}">User</a>'
        welcome_msg = await bot.send_message(
            chat_id=chat_id,
            text=f"✅ {mention} has passed verification.",
            parse_mode="HTML",
        )
        await asyncio.sleep(10)
        await actions.delete_message(bot, chat_id, welcome_msg.message_id)
    except Exception as exc:
        logger.warning("Failed to send/delete welcome message: %s", exc)

    logger.info("User %s passed verification in chat %s", user_id, chat_id)


async def handle_failure(
    bot: Bot,
    chat_id: int,
    user_id: int,
    reason: str = "",
) -> None:
    """
    Verification failed:
    - Delete the verification message
    - Update status to 'failed'
    - Increment total_failures
    - Kick or ban depending on threshold
    """
    # Idempotent status update
    updated = queries.update_pending_status(chat_id, user_id, "failed")
    if not updated:
        logger.debug("Failure: record (%s, %s) already processed, skipping", chat_id, user_id)
        return

    # Delete verification message
    msg_id = queries.get_pending_question_msg_id(chat_id, user_id)
    if msg_id:
        await actions.delete_message(bot, chat_id, msg_id)

    # Delete all messages the user sent during this verification session
    pending_msg_ids = queries.get_pending_msg_ids(chat_id, user_id)
    for pmid in pending_msg_ids:
        await actions.delete_message(bot, chat_id, pmid)

    # Increment failures
    total_failures = queries.increment_total_failures(chat_id, user_id)
    logger.info(
        "User %s failed verification in chat %s (total_failures=%s, reason=%s)",
        user_id, chat_id, total_failures, reason
    )

    if total_failures >= BAN_THRESHOLD:
        await actions.ban_user(bot, chat_id, user_id)
        queries.set_user_banned(chat_id, user_id, True)
        logger.info("User %s permanently banned in chat %s", user_id, chat_id)
    else:
        await actions.kick_user(bot, chat_id, user_id)
        remaining = BAN_THRESHOLD - total_failures
        logger.info(
            "User %s kicked from chat %s (%d chance(s) remaining)",
            user_id, chat_id, remaining
        )
