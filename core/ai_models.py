"""
ai_models.py
Ordered list of AI model configurations.
The verifier tries each entry in sequence, falling back to the next on failure.
Add, remove, or reorder entries here to change provider priority.
"""

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class ModelEntry:
    api_key: str
    model: str
    base_url: str | None = None      # None = use default OpenAI endpoint
    extra_body: dict | None = None   # provider-specific request parameters


MODEL_CHAIN: list[ModelEntry] = [
    ModelEntry(
        api_key=os.environ.get("OPENROUTER_API_KEY", ""),
        base_url="https://openrouter.ai/api/v1",
        model="qwen/qwen3.5-flash-02-23",
        extra_body={"thinking": {"type": "disabled"}},
    ),
    ModelEntry(
        api_key=os.environ.get("OPENAI_API_KEY", ""),
        model="gpt-4o-mini",
    ),
]
