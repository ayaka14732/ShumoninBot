# Shumonin Bot

[[中文說明]](README-zh.md)

**Shumonin Bot** is a Telegram group management bot that uses AI to verify new members through multi-turn conversations. It prevents spam, enforces strict entry criteria, and provides a seamless setup experience for group administrators.

## Features

- **AI-Powered Verification**: Conducts multi-turn interviews with new members based on custom questions and criteria.
- **Provider Fallback**: AI calls go through a configurable model chain (`core/ai_models.py`); if one provider fails, the next is tried automatically.
- **Name Pre-check**: Automatically kicks users with spam, adult, or scam-related display names before verification even starts.
- **Spam Reporting**: Users can reply to any message with `/report` to have AI silently analyze it; confirmed spam is deleted and the sender is banned. Attempting to report an admin silently deletes the report.
- **Guided Admin Setup**: Easy `/setup` command to configure verification rules in natural language.
- **Safety Mechanisms**: Rate limiting, maximum answer length, timeout polling, and ban thresholds.

## Requirements

- Python 3.11+
- `python-telegram-bot`
- `openai` (for OpenRouter compatibility)
- `python-dotenv`

## BotFather Configuration

Before adding the bot to a group, you must disable Privacy Mode so the bot can read all messages:

1. Open [@BotFather](https://t.me/BotFather) on Telegram.
2. Send `/mybots` and select your bot.
3. Go to **Bot Settings** > **Group Privacy** > **Turn off**.

Without this step, the bot will only receive messages that directly mention it and will not function correctly.

## Setup & Execution

1. Create a `.env` file in the project root:
   ```env
   TELEGRAM_BOT_TOKEN=your_telegram_bot_token
   OPENROUTER_API_KEY=your_openrouter_api_key
   OPENAI_API_KEY=your_openai_api_key   # optional, used as fallback
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
