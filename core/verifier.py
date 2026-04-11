"""
core/verifier.py
All AI call logic: name pre-check, verification judgment, spam judgment.
"""

import json
import logging
import os
from pathlib import Path
from openai import OpenAI
from config import (
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
    AI_MODEL,
    AI_TEMPERATURE,
    AI_MAX_TOKENS,
)

logger = logging.getLogger(__name__)

# Load prompt templates once at module import
_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

def _load_prompt(filename: str) -> str:
    return (_PROMPTS_DIR / filename).read_text(encoding="utf-8")

NAME_CHECK_PROMPT = _load_prompt("name_check.txt")
VERIFICATION_PROMPT_TEMPLATE = _load_prompt("verification.txt")
SPAM_CHECK_PROMPT_TEMPLATE = _load_prompt("spam_check.txt")

# OpenAI-compatible client pointed at OpenRouter
_client = OpenAI(
    api_key=OPENROUTER_API_KEY,
    base_url=OPENROUTER_BASE_URL,
)


def _call_ai(system_prompt: str, user_content: str) -> dict:
    """
    Call the AI model and return the parsed JSON response dict.
    Raises ValueError if the response cannot be parsed as JSON.
    """
    response = _client.chat.completions.create(
        model=AI_MODEL,
        temperature=AI_TEMPERATURE,
        max_tokens=AI_MAX_TOKENS,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        extra_body={"thinking": {"type": "disabled"}},
    )
    raw = response.choices[0].message.content.strip()
    logger.debug("AI raw response: %s", raw)

    # Strip Markdown code fences if present
    if raw.startswith("```"):
        lines = raw.splitlines()
        # Remove first and last fence lines
        inner = lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
        raw = "\n".join(inner).strip()

    return json.loads(raw)


def check_name(display_name: str, username: str) -> dict:
    """
    Check if a user's display name or username contains spam/adult/scam patterns.
    Returns: {"action": "ok" | "kick", "reason": str}
    """
    user_content = f"Display name: {display_name}\nUsername: @{username or '(none)'}"
    try:
        result = _call_ai(NAME_CHECK_PROMPT, user_content)
        if result.get("action") not in ("ok", "kick"):
            logger.warning("Unexpected name check action: %s", result)
            result["action"] = "ok"
        return result
    except Exception as exc:
        logger.error("Name check AI error: %s", exc)
        return {"action": "ok", "reason": f"AI error fallback: {exc}"}


def verify_answer(
    question: str,
    expected: str,
    conversation_history: list[dict],
    user_message: str,
) -> dict:
    """
    Evaluate a user's answer in the context of the full conversation.
    Returns: {"action": "pass" | "continue" | "kick", "reply": str}
    """
    # Format conversation history for the prompt
    history_lines = []
    for msg in conversation_history:
        role_label = "Assistant" if msg["role"] == "assistant" else "User"
        history_lines.append(f"{role_label}: {msg['content']}")
    history_text = "\n".join(history_lines) if history_lines else "(no previous conversation)"

    system_prompt = (
        VERIFICATION_PROMPT_TEMPLATE
        .replace("{question}", question)
        .replace("{expected}", expected)
        .replace("{conversation_history}", history_text)
        .replace("{user_message}", user_message)
    )

    try:
        result = _call_ai(system_prompt, user_message)
        if result.get("action") not in ("pass", "continue", "kick"):
            logger.warning("Unexpected verify action: %s", result)
            result["action"] = "continue"
            result.setdefault("reply", "Could you please elaborate on your answer?")
        return result
    except Exception as exc:
        logger.error("Verification AI error: %s", exc)
        raise


def check_spam(message_content: str) -> dict:
    """
    Determine whether a reported message is spam.
    Returns: {"result": "spam" | "not_spam", "reason": str}
    """
    system_prompt = SPAM_CHECK_PROMPT_TEMPLATE.replace("{message_content}", message_content)
    try:
        result = _call_ai(system_prompt, message_content)
        if result.get("result") not in ("spam", "not_spam"):
            logger.warning("Unexpected spam check result: %s", result)
            result["result"] = "not_spam"
        return result
    except Exception as exc:
        logger.error("Spam check AI error: %s", exc)
        return {"result": "not_spam", "reason": f"AI error fallback: {exc}"}
