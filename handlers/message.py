"""
handlers/message.py
Handles all group message events:
  - Routes admin setup flow messages to the command handler
  - Processes pending user answers via AI verification
"""

import json
import logging
import time
from telegram import Update, Bot
from telegram.ext import ContextTypes
from config import (
    ALLOWED_CHAT_IDS,
    MAX_MESSAGE_LENGTH,
    MAX_USER_ANSWER_ROUNDS,
    MAX_AI_FAILURES,
    ADMIN_SESSION_EXPIRY_SEC,
)
from db import queries
from core import verifier
from handlers.shared import handle_success, handle_failure

logger = logging.getLogger(__name__)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Entry point for group message events."""
    if not update.message or not update.effective_user:
        return

    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    # Pre-check: whitelist
    if ALLOWED_CHAT_IDS and chat_id not in ALLOWED_CHAT_IDS:
        return

    # Pre-check: check if sender is in an admin setup session
    admin_session = queries.get_admin_session(chat_id, user_id)
    if admin_session:
        # Check session expiry
        if queries.is_admin_session_expired(admin_session, ADMIN_SESSION_EXPIRY_SEC):
            queries.delete_admin_session(chat_id, user_id)
            await update.message.reply_text(
                "⚠️ Setup session expired. Please start again."
            )
            return
        # Route to admin setup flow handler
        from handlers.commands import handle_admin_setup_input
        await handle_admin_setup_input(update, context, admin_session)
        return

    # Check if sender is a pending user
    pending = queries.get_pending_user(chat_id, user_id)
    if not pending or pending["status"] != "pending":
        return

    bot: Bot = context.bot
    message_text = update.message.text or ""

    # Track this message so it can be deleted if the user fails verification
    queries.append_pending_msg_id(chat_id, user_id, update.message.message_id)

    # Pre-check: timeout
    if int(time.time()) > pending["expire_time"]:
        logger.info("User %s in chat %s timed out during message handling", user_id, chat_id)
        updated = queries.update_pending_status(chat_id, user_id, "timeout")
        if updated:
            msg_id = pending.get("question_msg_id")
            if msg_id:
                from core.actions import delete_message
                await delete_message(bot, chat_id, msg_id)
            from core.scheduler import _handle_timeout
            # Re-use timeout logic (already idempotent)
            await _handle_timeout(bot, pending)
        return

    # Pre-check: message too long
    if len(message_text) > MAX_MESSAGE_LENGTH:
        logger.info(
            "User %s in chat %s sent message too long (%d chars), kicking",
            user_id, chat_id, len(message_text)
        )
        await handle_failure(bot, chat_id, user_id, reason="Message too long")
        return

    # Check max answer rounds
    answer_rounds = queries.increment_answer_rounds(chat_id, user_id)
    if answer_rounds > MAX_USER_ANSWER_ROUNDS:
        logger.info(
            "User %s in chat %s exceeded max answer rounds (%d), timing out",
            user_id, chat_id, MAX_USER_ANSWER_ROUNDS
        )
        updated = queries.update_pending_status(chat_id, user_id, "timeout")
        if updated:
            msg_id = pending.get("question_msg_id")
            if msg_id:
                from core.actions import delete_message
                await delete_message(bot, chat_id, msg_id)
            from db.queries import increment_total_failures, set_user_banned
            from core.actions import kick_user, ban_user
            from config import BAN_THRESHOLD
            total_failures = increment_total_failures(chat_id, user_id)
            if total_failures >= BAN_THRESHOLD:
                await ban_user(bot, chat_id, user_id)
                set_user_banned(chat_id, user_id, True)
            else:
                await kick_user(bot, chat_id, user_id)
        return

    # Append user message to conversation history
    queries.append_conversation(chat_id, user_id, "user", message_text)

    # Reload pending record to get updated conversation
    pending = queries.get_pending_user(chat_id, user_id)
    conversation = json.loads(pending["conversation"])

    # Load group settings
    settings = queries.get_group_settings(chat_id)
    if not settings:
        return

    # Call AI verifier
    try:
        result = verifier.verify_answer(
            question=settings["question"],
            expected=settings["expected"],
            conversation_history=conversation[:-1],  # history before this message
            user_message=message_text,
        )
        # Reset AI fail counter on success
        queries.reset_ai_fail_count(chat_id, user_id)
    except Exception as exc:
        logger.error("AI verification error for user %s in chat %s: %s", user_id, chat_id, exc)
        fail_count = queries.increment_ai_fail_count(chat_id, user_id)
        if fail_count >= MAX_AI_FAILURES:
            logger.warning(
                "AI failed %d times for user %s in chat %s, applying failure",
                fail_count, user_id, chat_id
            )
            await handle_failure(bot, chat_id, user_id, reason="AI API consecutive failures")
        else:
            # Fallback: re-send the verification question
            try:
                msg_id = pending.get("question_msg_id")
                if msg_id:
                    from core.actions import delete_message
                    await delete_message(bot, chat_id, msg_id)
                resent = await bot.send_message(
                    chat_id=chat_id,
                    text=(
                        "⚠️ An error occurred. Please try answering the verification question again.\n\n"
                        f"{_escape_html(settings['question'])}"
                    ),
                    parse_mode="HTML",
                )
                queries.update_pending_question_msg_id(chat_id, user_id, resent.message_id)
            except Exception as send_exc:
                logger.error("Failed to resend verification question: %s", send_exc)
        return

    action = result.get("action")
    reply = result.get("reply", "")

    logger.info(
        "AI decision for user %s in chat %s: action=%s reply=%s",
        user_id, chat_id, action, reply
    )

    if action == "pass":
        await handle_success(bot, chat_id, user_id)

    elif action == "continue":
        # Append AI reply to conversation history
        queries.append_conversation(chat_id, user_id, "assistant", reply)
        # Send the follow-up question
        try:
            msg_id = pending.get("question_msg_id")
            if msg_id:
                from core.actions import delete_message
                await delete_message(bot, chat_id, msg_id)
            new_msg = await bot.send_message(
                chat_id=chat_id,
                text=reply,
                parse_mode="HTML",
            )
            queries.update_pending_question_msg_id(chat_id, user_id, new_msg.message_id)
        except Exception as exc:
            logger.error("Failed to send follow-up question: %s", exc)

    elif action == "kick":
        await handle_failure(bot, chat_id, user_id, reason=reply)

    else:
        logger.warning("Unknown AI action '%s' for user %s, treating as continue", action, user_id)


def _escape_html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
