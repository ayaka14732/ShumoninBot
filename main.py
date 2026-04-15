"""
main.py
Entry point for Shumonin Bot — Telegram AI Group Verification Bot.
Initializes the bot, sets up the database, registers all handlers,
and starts the background expiry polling task.
"""

import asyncio
import logging
import sys
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ChatMemberHandler,
    filters,
)
from config import TELEGRAM_BOT_TOKEN, OPENAI_API_KEY, OPENROUTER_API_KEY
from db.database import init_db
from core.scheduler import run_expiry_poll, process_startup_expiries
from handlers.join import handle_join, handle_chat_member_join
from handlers.message import handle_message
from handlers.leave import handle_leave
from handlers.commands import (
    cmd_setup,
    cmd_setquestion,
    cmd_setexpected,
    cmd_setexpiry,
    cmd_settings,
    cmd_unban,
    cmd_status,
    cmd_cancel,
    cmd_confirm,
    cmd_help,
)
from handlers.report import cmd_report, cmd_callmods

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


def main() -> None:
    """Initialize and run the bot."""
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN is not set in environment.")
        sys.exit(1)
    if not OPENAI_API_KEY and not OPENROUTER_API_KEY:
        logger.error("At least one of OPENAI_API_KEY or OPENROUTER_API_KEY must be set.")
        sys.exit(1)

    # Initialize SQLite database
    logger.info("Initializing database...")
    init_db()

    # Create the Application
    logger.info("Initializing Shumonin Bot application...")
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Register Admin Commands
    application.add_handler(CommandHandler("setup", cmd_setup))
    application.add_handler(CommandHandler("setquestion", cmd_setquestion))
    application.add_handler(CommandHandler("setexpected", cmd_setexpected))
    application.add_handler(CommandHandler("setexpiry", cmd_setexpiry))
    application.add_handler(CommandHandler("settings", cmd_settings))
    application.add_handler(CommandHandler("unban", cmd_unban))
    application.add_handler(CommandHandler("status", cmd_status))
    application.add_handler(CommandHandler("cancel", cmd_cancel))
    application.add_handler(CommandHandler("confirm", cmd_confirm))
    application.add_handler(CommandHandler("help", cmd_help))

    # Register User Commands
    application.add_handler(CommandHandler("report", cmd_report))
    application.add_handler(CommandHandler("callmods", cmd_callmods))

    # Register Event Handlers
    # 1a. New chat members via service message (small groups / direct joins)
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, handle_join))

    # 1b. New chat members via chat_member update (large groups where Telegram omits service messages).
    # Must be in a separate group from handler 3 because PTB only fires the first matching
    # ChatMemberHandler within a group.
    application.add_handler(ChatMemberHandler(handle_chat_member_join, ChatMemberHandler.CHAT_MEMBER), group=1)

    # 2. General group messages (handles both AI verification answers and admin setup inputs)
    application.add_handler(MessageHandler(
        filters.TEXT & (~filters.COMMAND) & filters.ChatType.GROUPS,
        handle_message
    ))

    # 3. Chat member status changes (left, kicked). Group 2 so it runs independently of handler 1b.
    application.add_handler(ChatMemberHandler(handle_leave, ChatMemberHandler.CHAT_MEMBER), group=2)

    # Post-init hook to start background tasks
    async def post_init(app: Application) -> None:
        logger.info("Running post-init tasks...")
        # Process any verification expiries that occurred while the bot was offline
        await process_startup_expiries(app.bot)
        # Start the background expiry polling loop
        asyncio.create_task(run_expiry_poll(app.bot))

    application.post_init = post_init

    # Run the bot until the user presses Ctrl-C
    logger.info("Shumonin Bot is starting...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
