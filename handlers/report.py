"""
handlers/report.py
Handles /report command for spam reporting.
Completely silent: no reply messages regardless of outcome.
"""

import logging
from telegram import Update, Bot
from telegram.ext import ContextTypes
from config import ALLOWED_CHAT_IDS
from core import verifier
from core.actions import ban_user, delete_message

logger = logging.getLogger(__name__)


async def cmd_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /report command.
    User must reply to a message to report it.
    Completely silent — no reply messages sent.
    """
    if not update.message:
        return

    chat_id = update.effective_chat.id

    # Pre-check: whitelist
    if ALLOWED_CHAT_IDS and chat_id not in ALLOWED_CHAT_IDS:
        return

    bot: Bot = context.bot

    # Pre-check: must be a reply to another message
    replied = update.message.reply_to_message
    if not replied:
        return

    # Pre-check: reported message must have a sender
    if not replied.from_user:
        return

    reported_user = replied.from_user
    reported_user_id = reported_user.id

    # Pre-check: do not allow reporting admins — delete the audacious /report message
    try:
        member = await bot.get_chat_member(chat_id, reported_user_id)
        if member.status in ("administrator", "creator"):
            await delete_message(bot, chat_id, update.message.message_id)
            return
    except Exception as exc:
        logger.warning("Failed to check reported user status: %s", exc)
        await delete_message(bot, chat_id, update.message.message_id)
        return

    # Extract message content for AI judgment
    message_content = _extract_message_content(replied)
    if not message_content:
        return

    logger.info(
        "Spam report: user %s reported message from user %s in chat %s",
        update.effective_user.id, reported_user_id, chat_id
    )

    # AI spam check
    try:
        result = verifier.check_spam(message_content)
        logger.info(
            "Spam check result for user %s in chat %s: result=%s reason=%s",
            reported_user_id, chat_id, result.get("result"), result.get("reason")
        )

        if result.get("result") == "spam":
            # Ban the user
            await ban_user(bot, chat_id, reported_user_id)
            # Delete the reported message
            await delete_message(bot, chat_id, replied.message_id)
            # Also delete the /report command message
            await delete_message(bot, chat_id, update.message.message_id)
            logger.info(
                "Spam confirmed: banned user %s and deleted message in chat %s",
                reported_user_id, chat_id
            )
        # If not_spam: silently ignore

    except Exception as exc:
        logger.error("Spam check error in chat %s: %s", chat_id, exc)
        # Silently ignore on error


def _extract_message_content(message) -> str:
    """Extract text content from a Telegram message for spam analysis."""
    parts = []

    if message.text:
        parts.append(message.text)
    elif message.caption:
        parts.append(message.caption)

    # Include media type hints for context
    if message.photo:
        parts.append("[Photo]")
    if message.video:
        parts.append("[Video]")
    if message.document:
        parts.append(f"[Document: {message.document.file_name or 'unknown'}]")
    if message.sticker:
        parts.append(f"[Sticker: {message.sticker.emoji or ''}]")
    if message.voice:
        parts.append("[Voice message]")
    if message.audio:
        parts.append("[Audio]")

    # Include forward info if available (PTB v20+: forward_origin replaces forward_from)
    if message.forward_origin:
        origin = message.forward_origin
        origin_type = type(origin).__name__
        if hasattr(origin, "sender_user") and origin.sender_user:
            parts.append(f"[Forwarded from: {origin.sender_user.full_name}]")
        elif hasattr(origin, "chat") and origin.chat:
            parts.append(f"[Forwarded from channel: {origin.chat.title}]")
        else:
            parts.append(f"[Forwarded ({origin_type})]")

    return " ".join(parts).strip()
