"""
handlers/join.py
Handles new member join events via both new_chat_members service messages and
chat_member updates (the latter is required for large groups where Telegram no
longer sends service messages for non-bot joins).
"""

import logging
import time
from telegram import Update, Bot, ChatMemberLeft, ChatMemberBanned, ChatMemberMember, ChatMemberRestricted
from telegram.ext import ContextTypes
from config import ALLOWED_CHAT_IDS, DEFAULT_TIMEOUT_SEC, BAN_THRESHOLD
from db import queries
from core import actions, verifier

logger = logging.getLogger(__name__)


async def handle_join(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Entry point for new_chat_members service message events."""
    if not update.message or not update.message.new_chat_members:
        return

    chat_id = update.effective_chat.id

    # Pre-check: whitelist
    if ALLOWED_CHAT_IDS and chat_id not in ALLOWED_CHAT_IDS:
        return

    bot: Bot = context.bot

    join_msg_id = update.message.message_id

    for member in update.message.new_chat_members:
        # Pre-check: skip bots
        if member.is_bot:
            logger.debug("Skipping bot %s in chat %s (service message path)", member.id, chat_id)
            continue

        user_id = member.id
        username = member.username or ""
        display_name = member.full_name or str(user_id)

        logger.info(
            "Join detected via service message: user=%s (@%s, %r) in chat=%s",
            user_id, username, display_name, chat_id,
        )
        await _process_new_member(
            bot, chat_id, user_id, username, display_name, join_msg_id,
            source="service_message",
        )


async def handle_chat_member_join(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Entry point for chat_member update events (covers joins that produce no service message)."""
    if not update.chat_member:
        return

    old_status = update.chat_member.old_chat_member
    new_status = update.chat_member.new_chat_member

    # Only handle transitions into the group (left/banned → member/restricted)
    if not isinstance(old_status, (ChatMemberLeft, ChatMemberBanned)):
        return
    if not isinstance(new_status, (ChatMemberMember, ChatMemberRestricted)):
        return

    user = new_status.user
    if user.is_bot:
        logger.debug("Skipping bot %s in chat %s (chat_member update path)", user.id, update.effective_chat.id)
        return

    chat_id = update.effective_chat.id

    # Pre-check: whitelist
    if ALLOWED_CHAT_IDS and chat_id not in ALLOWED_CHAT_IDS:
        return

    bot: Bot = context.bot
    user_id = user.id
    username = user.username or ""
    display_name = user.full_name or str(user_id)

    logger.info(
        "Join detected via chat_member update: user=%s (@%s, %r) in chat=%s, transition=%s→%s",
        user_id, username, display_name, chat_id,
        type(old_status).__name__, type(new_status).__name__,
    )
    # No service message exists for this join, so no join_msg_id
    await _process_new_member(
        bot, chat_id, user_id, username, display_name, join_msg_id=None,
        source="chat_member_update",
    )


async def _process_new_member(
    bot: Bot,
    chat_id: int,
    user_id: int,
    username: str,
    display_name: str,
    join_msg_id: int = None,
    source: str = "unknown",
) -> None:
    """Process a single new member joining the group."""

    logger.info(
        "Processing new member: user=%s (@%s, %r) in chat=%s source=%s join_msg_id=%s",
        user_id, username, display_name, chat_id, source, join_msg_id,
    )

    # Deduplicate: if the user already has an active pending record (created within
    # the last 10 seconds), this is a duplicate event from the other join path —
    # skip to avoid sending a second verification message.
    existing = queries.get_pending_user(chat_id, user_id)
    if existing and existing["status"] == "pending":
        age = int(time.time()) - existing.get("join_time", 0)
        if age < 10:
            logger.info(
                "Duplicate join event suppressed for user=%s in chat=%s source=%s "
                "(existing pending record is %ds old)",
                user_id, chat_id, source, age,
            )
            return

    # Update last join time
    queries.update_last_join_time(chat_id, user_id)

    # Check if user is already banned by the bot
    history = queries.get_user_history(chat_id, user_id)
    if history and history["is_banned"]:
        logger.info("Re-banning already-banned user %s in chat %s", user_id, chat_id)
        await actions.ban_user(bot, chat_id, user_id)
        if join_msg_id:
            await actions.delete_message(bot, chat_id, join_msg_id)
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
        join_msg_id=join_msg_id,
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
    text = f"{mention} {_escape_html(settings['question'])}"

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
