"""
handlers/join.py
Handles new_chat_members events.
"""

import logging
import time
from telegram import Update, Bot
from telegram.ext import ContextTypes
from config import ALLOWED_CHAT_IDS, DEFAULT_TIMEOUT_SEC, BAN_THRESHOLD
from db import queries
from core import actions, verifier

logger = logging.getLogger(__name__)


async def handle_join(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Entry point for new_chat_members events."""
    if not update.message or not update.message.new_chat_members:
        return

    chat_id = update.effective_chat.id

    # Pre-check: whitelist
    if ALLOWED_CHAT_IDS and chat_id not in ALLOWED_CHAT_IDS:
        return

    bot: Bot = context.bot

    for member in update.message.new_chat_members:
        # Pre-check: skip bots
        if member.is_bot:
            continue

        user_id = member.id
        username = member.username or ""
        display_name = member.full_name or str(user_id)

        await _process_new_member(bot, chat_id, user_id, username, display_name)


async def _process_new_member(
    bot: Bot,
    chat_id: int,
    user_id: int,
    username: str,
    display_name: str,
) -> None:
    """Process a single new member joining the group."""

    # Update last join time
    queries.update_last_join_time(chat_id, user_id)

    # Check if user is already banned by the bot
    history = queries.get_user_history(chat_id, user_id)
    if history and history["is_banned"]:
        logger.info("Re-banning already-banned user %s in chat %s", user_id, chat_id)
        await actions.ban_user(bot, chat_id, user_id)
        return

    # Check if group has verification settings
    settings = queries.get_group_settings(chat_id)
    if not settings or not settings.get("question"):
        logger.debug("No verification settings for chat %s, allowing user %s", chat_id, user_id)
        return

    timeout_sec = settings.get("timeout_sec") or DEFAULT_TIMEOUT_SEC

    # Restrict the user immediately
    await actions.restrict_user(bot, chat_id, user_id)

    # Determine attempt number and remaining chances
    hist = queries.ensure_user_history(chat_id, user_id)
    total_failures = hist.get("total_failures", 0)
    attempt = total_failures + 1
    remaining = BAN_THRESHOLD - total_failures

    # Calculate expiry
    expire_time = int(time.time()) + timeout_sec

    # Insert/replace pending record
    queries.insert_pending_user(
        chat_id=chat_id,
        user_id=user_id,
        username=username,
        display_name=display_name,
        expire_time=expire_time,
        attempt=attempt,
    )

    # --- Name pre-check ---
    try:
        name_result = verifier.check_name(display_name, username)
        logger.info(
            "Name check for user %s (%s): action=%s reason=%s",
            user_id, display_name, name_result.get("action"), name_result.get("reason")
        )
        if name_result.get("action") == "kick":
            await _fail_user(bot, chat_id, user_id, reason="Name pre-check failed")
            return
    except Exception as exc:
        logger.error("Name check error for user %s: %s", user_id, exc)
        # Fallback: continue with verification

    # --- Send verification question ---
    minutes = timeout_sec // 60
    seconds = timeout_sec % 60
    time_str = f"{minutes}m {seconds}s" if seconds else f"{minutes}m"

    mention = f'<a href="tg://user?id={user_id}">{_escape_html(display_name)}</a>'
    text = (
        f"👋 Welcome, {mention}!\n\n"
        f"Please answer the following verification question to join this group.\n\n"
        f"<b>Question:</b>\n{_escape_html(settings['question'])}\n\n"
        f"⏱ You have <b>{time_str}</b> to answer.\n"
        f"⚠️ Attempts remaining: <b>{remaining}</b> (banned after {BAN_THRESHOLD} failures)"
    )

    try:
        msg = await bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode="HTML",
        )
        queries.update_pending_question_msg_id(chat_id, user_id, msg.message_id)
        logger.info(
            "Verification question sent to user %s in chat %s (expire=%s)",
            user_id, chat_id, expire_time
        )
    except Exception as exc:
        logger.error("Failed to send verification message to user %s: %s", user_id, exc)


async def _fail_user(bot: Bot, chat_id: int, user_id: int, reason: str = "") -> None:
    """Handle verification failure for a user."""
    from handlers.shared import handle_failure
    await handle_failure(bot, chat_id, user_id, reason=reason)


def _escape_html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
