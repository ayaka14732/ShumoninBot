"""
config.py
Reads static configuration from environment variables or a .env file.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# Telegram Bot Token (required)
TELEGRAM_BOT_TOKEN: str = os.environ.get("TELEGRAM_BOT_TOKEN", "")

# OpenRouter API Key (required)
OPENROUTER_API_KEY: str = os.environ.get("OPENROUTER_API_KEY", "")

# Comma-separated list of allowed chat IDs, e.g. "-100123456,-100654321"
_raw_ids = os.environ.get("ALLOWED_CHAT_IDS", "")
ALLOWED_CHAT_IDS: set[int] = (
    {int(cid.strip()) for cid in _raw_ids.split(",") if cid.strip()}
    if _raw_ids.strip()
    else set()
)

# SQLite database file path
DB_PATH: str = os.environ.get("DB_PATH", "bot.db")

# OpenRouter model
AI_MODEL: str = "qwen/qwen3.5-flash-02-23"
OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"

# AI parameters
AI_TEMPERATURE: float = 0.2
AI_MAX_TOKENS: int = 1000

# Verification defaults
DEFAULT_TIMEOUT_SEC: int = 300          # 5 minutes
MAX_CONVERSATION_ROUNDS: int = 10       # max stored conversation turns
MAX_USER_ANSWER_ROUNDS: int = 5         # max user answer rounds before auto-timeout
MAX_MESSAGE_LENGTH: int = 50            # characters; longer messages → immediate kick
MAX_AI_FAILURES: int = 3               # consecutive AI call failures before kick

# Ban threshold
BAN_THRESHOLD: int = 3                  # total_failures >= this → permanent ban

# Admin session expiry
ADMIN_SESSION_EXPIRY_SEC: int = 600     # 10 minutes

# Timeout polling interval
TIMEOUT_POLL_INTERVAL_SEC: int = 30
