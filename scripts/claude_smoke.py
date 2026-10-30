"""Verifies the Claude setup from .env: lists models your key can use, then runs a real tool-calling round trip
with the configured ANTHROPIC_MODEL. Never prints the key. Usage: .venv/bin/python scripts/claude_smoke.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app import config, llm  # noqa: E402

if not config.claude_enabled():
    sys.exit("ANTHROPIC_API_KEY is not set in .env")
c = llm.client()
ids = [m.id for m in c.models.list(limit=50).data]
print("Models available to this key:", ", ".join(ids))
model = llm.model()
if model not in ids:
    sys.exit(f"Configured ANTHROPIC_MODEL '{model}' is not in that list — set one of the above in .env")
tool = {"name": "get_project", "description": "Project summary by code", "input_schema": {"type": "object", "properties": {"code": {"type": "string"}}, "required": ["code"]}}
r = c.messages.create(model=model, max_tokens=300, tools=[tool], messages=[{"role": "user", "content": "Look up project NSU."}])
calls = [b for b in r.content if b.type == "tool_use"]
print(f"Model {model}: stop_reason={r.stop_reason}, tool calls={[(b.name, b.input) for b in calls]}")
print("OK — tool calling works." if calls else "WARNING — model answered without calling the tool.")
