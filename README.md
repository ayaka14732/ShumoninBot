# Shumonin Bot

**Shumonin Bot** is a Telegram group management bot that uses AI (Qwen3.5-Flash via OpenRouter) to verify new members through multi-turn conversations. It prevents spam, enforces strict entry criteria, and provides a seamless setup experience for group administrators.

## Features

- **AI-Powered Verification**: Conducts multi-turn interviews with new members based on custom questions and criteria.
- **Name Pre-check**: Automatically kicks users with spam, adult, or scam-related display names before verification even starts.
- **Spam Reporting**: Users can reply to a message with `/report` to have AI silently analyze and delete spam, and ban the sender if confirmed.
- **Guided Admin Setup**: Easy `/setup` command to configure verification rules in natural language.
- **Safety Mechanisms**: Rate limiting, maximum answer length, timeout polling, and ban thresholds.

## Project Structure

```
shumonin-bot/
├── main.py                  # Entry point, initializes Bot and handlers
├── config.py                # Environment variables and static config
├── README.md                # Documentation
│
├── core/                    # Core business logic
│   ├── actions.py           # Telegram API wrappers (restrict/kick/ban)
│   ├── scheduler.py         # Background timeout polling
│   └── verifier.py          # AI integration (OpenRouter API calls)
│
├── db/                      # Database layer (SQLite)
│   ├── database.py          # Connection and table creation
│   └── queries.py           # CRUD operations
│
├── handlers/                # Telegram event handlers
│   ├── commands.py          # Admin commands (/setup, /settings, etc.)
│   ├── join.py              # new_chat_members events
│   ├── leave.py             # chat_member events (left/kicked)
│   ├── message.py           # Group messages (answers and setup input)
│   ├── report.py            # /report command
│   └── shared.py            # Shared success/failure flows
│
└── prompts/                 # AI system prompts
    ├── name_check.txt
    ├── spam_check.txt
    └── verification.txt
```

## Requirements

- Python 3.11+
- `python-telegram-bot`
- `openai` (for OpenRouter compatibility)
- `python-dotenv`

## Setup & Execution

1. Create a `.env` file in the project root:
   ```env
   TELEGRAM_BOT_TOKEN=your_telegram_bot_token
   OPENROUTER_API_KEY=your_openrouter_api_key
   ALLOWED_CHAT_IDS=-100123456789,-100987654321
   DB_PATH=bot.db
   ```

2. Install dependencies:
   ```bash
   pip install python-telegram-bot openai python-dotenv
   ```

3. Run the bot:
   ```bash
   python main.py
   ```

## Admin Commands

- `/setup` - Start the guided setup process.
- `/setquestion` - Update the verification question.
- `/setexpected` - Update the scoring criteria.
- `/settimeout` - Update the timeout duration.
- `/settings` - View current group settings.
- `/unban <user_id>` - Reset bot-side ban and failure count.
- `/status` - Check bot permissions.
- `/cancel` - Cancel the current setup session.
- `/help` - Show all commands.
