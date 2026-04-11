"""
core/verifier.py
All AI call logic: name pre-check, verification judgment, spam judgment.
"""

import json
import logging
from pathlib import Path
from openai import OpenAI
from config import AI_TEMPERATURE, AI_MAX_TOKENS
from .ai_models import MODEL_CHAIN

logger = logging.getLogger(__name__)

# Load prompt templates once at module import
_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

def _load_prompt(filename: str) -> str:
    return (_PROMPTS_DIR / filename).read_text(encoding="utf-8")

NAME_CHECK_PROMPT = _load_prompt("name_check.txt")
VERIFICATION_PROMPT_TEMPLATE = _load_prompt("verification.txt")
SPAM_CHECK_PROMPT_TEMPLATE = _load_prompt("spam_check.txt")

# Build one OpenAI-compatible client per configured model entry (skip entries with no key)
_model_clients = [
    (
        OpenAI(api_key=e.api_key, **({"base_url": e.base_url} if e.base_url else {})),
        e,
    )
    for e in MODEL_CHAIN
    if e.api_key
]


def _parse_response(raw: str) -> dict:
    """Strip Markdown fences if present and parse JSON."""
    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.splitlines()
        inner = lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
        raw = "\n".join(inner).strip()
    return json.loads(raw)


def _call_ai(system_prompt: str, user_content: str) -> dict:
    """
    Try each model in MODEL_CHAIN in order, returning on the first success.
    Raises the last exception if all models fail.
    """
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]
    last_exc: Exception | None = None
    for client, entry in _model_clients:
        try:
            kwargs: dict = dict(
                model=entry.model,
                temperature=AI_TEMPERATURE,
                max_tokens=AI_MAX_TOKENS,
                messages=messages,
            )
            if entry.extra_body:
                kwargs["extra_body"] = entry.extra_body
            response = client.chat.completions.create(**kwargs)
            raw = response.choices[0].message.content
            logger.debug("AI raw response (%s): %s", entry.model, raw)
            return _parse_response(raw)
        except Exception as exc:
            logger.warning("Model %s failed (%s), trying next", entry.model, exc)
            last_exc = exc
    raise last_exc or RuntimeError("No AI models configured in MODEL_CHAIN")


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
