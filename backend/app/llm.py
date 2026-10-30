"""Thin Claude adapter (official Anthropic SDK). Business logic never depends on a provider directly."""
import json
import re

from . import config


class LLMUnavailable(Exception):
    pass


def client():
    if not config.claude_enabled():
        raise LLMUnavailable("ANTHROPIC_API_KEY not configured")
    import anthropic
    import os
    return anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", config.ANTHROPIC_API_KEY), max_retries=2, timeout=60)


def model() -> str:
    import os
    return os.environ.get("ANTHROPIC_MODEL", config.ANTHROPIC_MODEL)


def complete_json(system: str, prompt: str, max_tokens: int = 4000) -> dict:
    c = client()
    msg = c.messages.create(model=model(), max_tokens=max_tokens, system=system,
                            messages=[{"role": "user", "content": prompt}])
    text = "".join(b.text for b in msg.content if b.type == "text")
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("model returned no JSON")
    return json.loads(m.group(0))
