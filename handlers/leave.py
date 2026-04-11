"""
handlers/leave.py
Handles chat_member events where a user leaves or is kicked.
"""

import logging
from telegram import Update, Bot, ChatMemberLeft, ChatMemberBanned
from telegram.ext import ContextTypes
from config import ALLOWED_CHAT_IDS
from db import queries
from core.actions import delete_message

logger = logging.getLogger(__name__)


async def handle_leave(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle a user leaving or being removed from the group."""
    if not update.chat_member:
        return

    chat_id = update.effective_chat.id

    # Pre-check: whitelist
    if ALLOWED_CHAT_IDS and chat_id not in ALLOWED_CHAT_IDS:
        return

    new_status = update.chat_member.new_chat_member
    user = update.chat_member.new_chat_member.user

    # Only care about left or kicked status
    if not isinstance(new_status, (ChatMemberLeft, ChatMemberBanned)):
        return

    user_id = user.id
    bot: Bot = context.bot

    # Check if user has a pending verification record
    pending = queries.get_pending_user(chat_id, user_id)
    if not pending or pending["status"] != "pending":
        return

    logger.info("User %s left chat %s while pending verification", user_id, chat_id)

    # Idempotent status update to 'left' (does NOT count as failure)
    updated = queries.update_pending_status(chat_id, user_id, "left")
    if updated:
        # Delete the verification message
        msg_id = pending.get("question_msg_id")
        if msg_id:
            await delete_message(bot, chat_id, msg_id)
