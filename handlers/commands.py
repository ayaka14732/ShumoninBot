"""
handlers/commands.py
All /command implementations for admin management.
"""

import json
import logging
from telegram import Update, Bot
from telegram.ext import ContextTypes
from config import ALLOWED_CHAT_IDS, DEFAULT_TIMEOUT_SEC, BAN_THRESHOLD
from db import queries
from core.actions import get_bot_permissions, unban_user
from handlers.shared import escape_html

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Permission helpers
# ---------------------------------------------------------------------------

async def _is_admin(bot: Bot, chat_id: int, user_id: int) -> bool:
    """Return True if user is a group admin or creator."""
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status in ("administrator", "creator")
    except Exception as exc:
        logger.warning("Failed to check admin status for user %s: %s", user_id, exc)
        return False


def _check_whitelist(chat_id: int) -> bool:
    return not ALLOWED_CHAT_IDS or chat_id in ALLOWED_CHAT_IDS



# ---------------------------------------------------------------------------
# /setup — guided multi-step setup
# ---------------------------------------------------------------------------

async def cmd_setup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    bot = context.bot

    if not _check_whitelist(chat_id):
        return
    if not await _is_admin(bot, chat_id, user_id):
        return

    queries.upsert_admin_session(chat_id, user_id, "setup_question", {})
    await update.message.reply_text(
        "🔧 <b>Starting verification setup for this group.</b>\n\n"
        "<b>Step 1/3:</b>\n\n"
        "Please enter the verification question to ask new members.\n\n"
        "<i>Example: What is RIME? Why do you want to join this group?</i>",
        parse_mode="HTML",
    )


# ---------------------------------------------------------------------------
# /setquestion — single-step question update
# ---------------------------------------------------------------------------

async def cmd_setquestion(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    bot = context.bot

    if not _check_whitelist(chat_id):
        return
    if not await _is_admin(bot, chat_id, user_id):
        return

    queries.upsert_admin_session(chat_id, user_id, "setquestion", {})
    await update.message.reply_text("Please enter the new verification question:")


# ---------------------------------------------------------------------------
# /setexpected — single-step expected criteria update
# ---------------------------------------------------------------------------

async def cmd_setexpected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    bot = context.bot

    if not _check_whitelist(chat_id):
        return
    if not await _is_admin(bot, chat_id, user_id):
        return

    queries.upsert_admin_session(chat_id, user_id, "setexpected", {})
    await update.message.reply_text("Please enter the new scoring criteria:")


# ---------------------------------------------------------------------------
# /settimeout — single-step timeout update
# ---------------------------------------------------------------------------

async def cmd_settimeout(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    bot = context.bot

    if not _check_whitelist(chat_id):
        return
    if not await _is_admin(bot, chat_id, user_id):
        return

    settings = queries.get_group_settings(chat_id)
    current_min = (settings["timeout_sec"] // 60) if settings else (DEFAULT_TIMEOUT_SEC // 60)
    queries.upsert_admin_session(chat_id, user_id, "settimeout", {})
    await update.message.reply_text(
        f"Please enter the timeout duration in minutes (current: {current_min}):"
    )


# ---------------------------------------------------------------------------
# /settings — view current settings
# ---------------------------------------------------------------------------

async def cmd_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    bot = context.bot

    if not _check_whitelist(chat_id):
        return
    if not await _is_admin(bot, chat_id, user_id):
        return

    settings = queries.get_group_settings(chat_id)
    if not settings:
        await update.message.reply_text(
            "⚠️ No verification settings configured yet.\n"
            "Use /setup to configure verification."
        )
        return

    timeout_min = settings["timeout_sec"] // 60
    question = escape_html(settings["question"] or "(not set)")
    expected = escape_html(settings["expected"] or "(not set)")

    text = (
        "📋 <b>Current Settings</b>\n"
        "──────────────────────────────\n"
        f"<b>Question:</b>\n{question}\n\n"
        f"<b>Criteria:</b>\n{expected}\n\n"
        f"<b>Timeout:</b> {timeout_min} minutes\n"
        f"<b>Failure cap:</b> {BAN_THRESHOLD} (banned on {BAN_THRESHOLD}rd failure)\n"
        "──────────────────────────────\n"
        "Use /setquestion /setexpected /settimeout to update."
    )
    await update.message.reply_text(text, parse_mode="HTML")


# ---------------------------------------------------------------------------
# /unban <user_id> — reset bot-side ban
# ---------------------------------------------------------------------------

async def cmd_unban(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    bot = context.bot

    if not _check_whitelist(chat_id):
        return
    if not await _is_admin(bot, chat_id, user_id):
        return

    if not context.args:
        await update.message.reply_text("Usage: /unban <user_id>")
        return

    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID. Please provide a numeric user ID.")
        return

    # Reset database records
    queries.reset_user_history(chat_id, target_id)

    # Unban in Telegram
    await unban_user(bot, chat_id, target_id)

    await update.message.reply_text(
        f"✅ User <code>{target_id}</code> has been unbanned.\n"
        "Failure count reset. They may rejoin the group.",
        parse_mode="HTML",
    )
    logger.info("Admin %s unbanned user %s in chat %s", user_id, target_id, chat_id)


# ---------------------------------------------------------------------------
# /status — check bot permissions
# ---------------------------------------------------------------------------

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    bot = context.bot

    if not _check_whitelist(chat_id):
        return
    if not await _is_admin(bot, chat_id, user_id):
        return

    perms = await get_bot_permissions(bot, chat_id)

    def _icon(ok: bool) -> str:
        return "✅" if ok else "❌"

    restrict_ok = perms.get("can_restrict_members", False)
    delete_ok = perms.get("can_delete_messages", False)
    ban_ok = perms.get("can_ban_members", False)
    all_ok = restrict_ok and delete_ok and ban_ok

    status_line = "🟢 Shumonin Bot is running normally." if all_ok else "🔴 Shumonin Bot is missing some permissions."
    text = (
        f"{status_line}\n\n"
        "<b>Permission check:</b>\n"
        f"  Restrict members  {_icon(restrict_ok)}\n"
        f"  Kick members      {_icon(restrict_ok)}\n"
        f"  Ban members       {_icon(ban_ok)}\n"
        f"  Delete messages   {_icon(delete_ok)}\n"
    )
    if not all_ok:
        text += "\n⚠️ Please grant the missing permissions to Shumonin Bot."

    await update.message.reply_text(text, parse_mode="HTML")


# ---------------------------------------------------------------------------
# /cancel — cancel active setup session
# ---------------------------------------------------------------------------

async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    bot = context.bot

    if not _check_whitelist(chat_id):
        return
    if not await _is_admin(bot, chat_id, user_id):
        return

    session = queries.get_admin_session(chat_id, user_id)
    if session:
        queries.delete_admin_session(chat_id, user_id)
        await update.message.reply_text("✅ Setup cancelled. No changes were saved.")
    else:
        await update.message.reply_text("No active setup to cancel.")


# ---------------------------------------------------------------------------
# /confirm — confirm setup (used inside /setup flow)
# ---------------------------------------------------------------------------

async def cmd_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    bot = context.bot

    if not _check_whitelist(chat_id):
        return
    if not await _is_admin(bot, chat_id, user_id):
        return

    session = queries.get_admin_session(chat_id, user_id)
    if not session or session["step"] != "setup_confirm":
        await update.message.reply_text("No pending setup to confirm.")
        return

    temp = json.loads(session["temp_data"])
    question = temp.get("question", "")
    expected = temp.get("expected", "")
    timeout_sec = int(temp.get("timeout_sec", DEFAULT_TIMEOUT_SEC))

    queries.upsert_group_settings(chat_id, question, expected, timeout_sec)
    queries.delete_admin_session(chat_id, user_id)

    await update.message.reply_text("✅ Settings saved. Shumonin Bot will now verify new members.")
    logger.info("Admin %s saved settings for chat %s", user_id, chat_id)


# ---------------------------------------------------------------------------
# /help — display all commands
# ---------------------------------------------------------------------------

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    bot = context.bot

    if not _check_whitelist(chat_id):
        return
    if not await _is_admin(bot, chat_id, user_id):
        return

    text = (
        "<b>Admin Commands</b>\n\n"
        "/setup — Guided setup: configure question, criteria, and timeout\n"
        "/setquestion — Update the verification question\n"
        "/setexpected — Update the scoring criteria\n"
        "/settimeout — Update the timeout duration (in minutes)\n"
        "/settings — View current group settings\n"
        "/unban &lt;user_id&gt; — Reset bot-side ban and failure count\n"
        "/status — Check bot permissions\n"
        "/cancel — Cancel the current setup session\n"
        "/help — Show this help message\n\n"
        "<b>User Commands</b>\n\n"
        "/report — Reply to a message to report it as spam\n"
        "/callmods — Mention all group admins to request their attention"
    )
    await update.message.reply_text(text, parse_mode="HTML")


# ---------------------------------------------------------------------------
# Admin setup input router (called from message.py)
# ---------------------------------------------------------------------------

async def handle_admin_setup_input(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    session: dict,
) -> None:
    """
    Route an admin's text message to the appropriate setup step handler.
    Called from message.py when an admin session is active.
    """
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    step = session["step"]
    temp = json.loads(session.get("temp_data", "{}"))
    text = update.message.text or ""

    if step == "setup_question":
        temp["question"] = text
        queries.upsert_admin_session(chat_id, user_id, "setup_expected", temp)
        await update.message.reply_text(
            "<b>Step 2/3:</b>\n\n"
            "Please describe the scoring criteria in natural language.\n"
            "You can specify which questions require strict answers and which are flexible.",
            parse_mode="HTML",
        )

    elif step == "setup_expected":
        temp["expected"] = text
        queries.upsert_admin_session(chat_id, user_id, "setup_timeout", temp)
        await update.message.reply_text(
            "<b>Step 3/3:</b>\n\n"
            f"Please enter the verification timeout in minutes. (Default: {DEFAULT_TIMEOUT_SEC // 60})",
            parse_mode="HTML",
        )

    elif step == "setup_timeout":
        try:
            minutes = int(text.strip())
            if minutes <= 0:
                raise ValueError("Must be positive")
        except ValueError:
            await update.message.reply_text(
                "❌ Invalid input. Please enter a positive integer (number of minutes)."
            )
            return
        temp["timeout_sec"] = minutes * 60
        queries.upsert_admin_session(chat_id, user_id, "setup_confirm", temp)

        question_preview = escape_html(temp.get("question", ""))
        expected_preview = escape_html(temp.get("expected", ""))
        await update.message.reply_text(
            "<b>Please confirm your settings:</b>\n\n"
            f"<b>Question:</b>\n{question_preview}\n\n"
            f"<b>Criteria:</b>\n{expected_preview}\n\n"
            f"<b>Timeout:</b> {minutes} minutes\n\n"
            "Reply /confirm to save, or /cancel to discard.",
            parse_mode="HTML",
        )

    elif step == "setquestion":
        queries.update_group_question(chat_id, text)
        queries.delete_admin_session(chat_id, user_id)
        await update.message.reply_text("✅ Verification question updated.")
        logger.info("Admin %s updated question for chat %s", user_id, chat_id)

    elif step == "setexpected":
        queries.update_group_expected(chat_id, text)
        queries.delete_admin_session(chat_id, user_id)
        await update.message.reply_text("✅ Scoring criteria updated.")
        logger.info("Admin %s updated expected for chat %s", user_id, chat_id)

    elif step == "settimeout":
        try:
            minutes = int(text.strip())
            if minutes <= 0:
                raise ValueError("Must be positive")
        except ValueError:
            await update.message.reply_text(
                "❌ Invalid input. Please enter a positive integer (number of minutes)."
            )
            return
        queries.update_group_timeout(chat_id, minutes * 60)
        queries.delete_admin_session(chat_id, user_id)
        await update.message.reply_text(f"✅ Timeout updated to {minutes} minutes.")
        logger.info("Admin %s updated timeout to %d min for chat %s", user_id, minutes, chat_id)

    elif step == "setup_confirm":
        # Waiting for /confirm or /cancel — ignore other text
        await update.message.reply_text(
            "Please reply /confirm to save settings, or /cancel to discard."
        )

    else:
        logger.warning("Unknown admin session step: %s", step)
        queries.delete_admin_session(chat_id, user_id)
        await update.message.reply_text(
            "⚠️ Unknown setup state. Session cleared. Please start again."
        )
