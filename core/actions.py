"""
core/actions.py
Telegram operation wrappers: restrict / kick / ban / delete / unban.
All functions are async and swallow non-critical errors gracefully.
"""

import logging
from telegram import Bot, ChatPermissions
from telegram.error import TelegramError

logger = logging.getLogger(__name__)

# Full permissions object (used to restore after passing verification)
FULL_PERMISSIONS = ChatPermissions(
    can_send_messages=True,
    can_send_audios=True,
    can_send_documents=True,
    can_send_photos=True,
    can_send_videos=True,
    can_send_video_notes=True,
    can_send_voice_notes=True,
    can_send_polls=True,
    can_send_other_messages=True,
    can_add_web_page_previews=True,
    can_change_info=False,
    can_invite_users=True,
    can_pin_messages=False,
)

# Restricted permissions for pending users: text-only, no media/polls/stickers.
# can_send_messages must remain True so users can answer the verification question.
NO_PERMISSIONS = ChatPermissions(
    can_send_messages=True,
    can_send_audios=False,
    can_send_documents=False,
    can_send_photos=False,
    can_send_videos=False,
    can_send_video_notes=False,
    can_send_voice_notes=False,
    can_send_polls=False,
    can_send_other_messages=False,
    can_add_web_page_previews=False,
)


async def restrict_user(bot: Bot, chat_id: int, user_id: int) -> bool:
    """Mute a user (no send permissions)."""
    try:
        await bot.restrict_chat_member(chat_id, user_id, permissions=NO_PERMISSIONS)
        logger.info("Restricted user %s in chat %s", user_id, chat_id)
        return True
    except TelegramError as e:
        logger.warning("Failed to restrict user %s in chat %s: %s", user_id, chat_id, e)
        return False


async def unrestrict_user(bot: Bot, chat_id: int, user_id: int) -> bool:
    """Restore full permissions for a user."""
    try:
        await bot.restrict_chat_member(chat_id, user_id, permissions=FULL_PERMISSIONS)
        logger.info("Unrestricted user %s in chat %s", user_id, chat_id)
        return True
    except TelegramError as e:
        logger.warning("Failed to unrestrict user %s in chat %s: %s", user_id, chat_id, e)
        return False


async def kick_user(bot: Bot, chat_id: int, user_id: int) -> bool:
    """Kick a user (ban then immediately unban so they can rejoin)."""
    try:
        await bot.ban_chat_member(chat_id, user_id)
        await bot.unban_chat_member(chat_id, user_id, only_if_banned=True)
        logger.info("Kicked user %s from chat %s", user_id, chat_id)
        return True
    except TelegramError as e:
        logger.warning("Failed to kick user %s from chat %s: %s", user_id, chat_id, e)
        return False


async def ban_user(bot: Bot, chat_id: int, user_id: int) -> bool:
    """Permanently ban a user."""
    try:
        await bot.ban_chat_member(chat_id, user_id)
        logger.info("Banned user %s from chat %s", user_id, chat_id)
        return True
    except TelegramError as e:
        logger.warning("Failed to ban user %s from chat %s: %s", user_id, chat_id, e)
        return False


async def unban_user(bot: Bot, chat_id: int, user_id: int) -> bool:
    """Unban a user (allow them to rejoin)."""
    try:
        await bot.unban_chat_member(chat_id, user_id, only_if_banned=True)
        logger.info("Unbanned user %s from chat %s", user_id, chat_id)
        return True
    except TelegramError as e:
        logger.warning("Failed to unban user %s from chat %s: %s", user_id, chat_id, e)
        return False


async def delete_message(bot: Bot, chat_id: int, message_id: int) -> bool:
    """Delete a message silently."""
    if not message_id:
        return False
    try:
        await bot.delete_message(chat_id, message_id)
        logger.debug("Deleted message %s in chat %s", message_id, chat_id)
        return True
    except TelegramError as e:
        logger.warning("Could not delete message %s in chat %s: %s", message_id, chat_id, e)
        return False


async def get_bot_permissions(bot: Bot, chat_id: int) -> dict:
    """
    Return a dict of permission name → bool for the bot in the given chat.
    Keys: can_restrict_members, can_delete_messages, can_ban_members
    """
    try:
        member = await bot.get_chat_member(chat_id, bot.id)
        return {
            "can_restrict_members": getattr(member, "can_restrict_members", False),
            "can_delete_messages": getattr(member, "can_delete_messages", False),
            "can_ban_members": getattr(member, "can_restrict_members", False),  # same permission
        }
    except TelegramError as e:
        logger.warning("Failed to get bot permissions in chat %s: %s", chat_id, e)
        return {
            "can_restrict_members": False,
            "can_delete_messages": False,
            "can_ban_members": False,
        }
