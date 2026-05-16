import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncIterator

import anthropic

from app.config import Settings
from app.services import occupancy_service, prediction_service, zone_service

log = logging.getLogger(__name__)

MAX_TOOL_ITERATIONS = 5
_MODEL = "claude-haiku-4-5-20251001"

SYSTEM_PROMPT = """\
You are ParkSmart, a helpful parking assistant for Chatswood CBD, Sydney, Australia.

You have three tools:
- get_live_occupancy(location): Current occupancy for a car park near a location or landmark.
- predict_availability(location, target_datetime): Predicted occupancy at a future time (up to 7 days). Use only when the user mentions a specific future time.
- get_zone_restrictions(street): Parking time rules for a street in Chatswood.

Behaviour rules:
- For "where to park" queries: call get_live_occupancy first. Then predict_availability only if the user mentions a future time.
- For "parking rules on X" queries: call get_zone_restrictions directly.
- If a tool returns {{"error": "no_match", "candidates": [...]}}, pick the closest candidate name and retry.
- Simulated car parks use pattern-based estimates — label them clearly as "estimated".
- Be concise and practical. Mention walking distance context when recommending a car park.
- Today is {date}. Sydney time is AEST (UTC+10) or AEDT (UTC+11) during daylight saving.\
"""

TOOLS: list[dict] = [
    {
        "name": "get_live_occupancy",
        "description": (
            "Get current parking occupancy for a car park in Chatswood CBD. "
            "Returns occupancy percentage, available spots, and whether the data is "
            "live (from TfNSW sensors) or estimated."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "Car park name or nearby landmark (e.g. 'Westfield', 'Mandarin Centre', 'Victoria Avenue')",
                }
            },
            "required": ["location"],
        },
    },
    {
        "name": "predict_availability",
        "description": (
            "Predict parking availability at a specific future time (up to 7 days ahead). "
            "Use this only when the user mentions a future time, not for current conditions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "Car park name or nearby landmark in Chatswood",
                },
                "target_datetime": {
                    "type": "string",
                    "description": "ISO 8601 datetime string, e.g. '2026-05-15T18:00:00'. Must be within 7 days.",
                },
            },
            "required": ["location", "target_datetime"],
        },
    },
    {
        "name": "get_zone_restrictions",
        "description": (
            "Get street parking time restrictions for a street in Chatswood CBD. "
            "Returns no-stopping zones, timed parking limits, and permit areas."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "street": {
                    "type": "string",
                    "description": "Street name in Chatswood CBD, e.g. 'Victoria Avenue', 'Albert Avenue'",
                }
            },
            "required": ["street"],
        },
    },
]


def _dispatch_tool(name: str, inputs: dict, db_path: Path, settings: Settings) -> dict:
    """Call the matching service function and return a JSON-serialisable dict."""
    try:
        if name == "get_live_occupancy":
            return occupancy_service.get_live_occupancy_tool(
                inputs["location"], db_path, settings
            )
        if name == "predict_availability":
            return prediction_service.predict_availability_tool(
                inputs["location"], inputs["target_datetime"], db_path
            )
        if name == "get_zone_restrictions":
            return zone_service.get_zone_restrictions(inputs["street"], db_path)
        return {"error": "unknown_tool", "tool": name}
    except Exception as exc:
        log.error("Tool dispatch error for '%s': %s", name, exc)
        return {"error": "tool_error", "detail": str(exc)}


async def chat_stream(
    message: str,
    history: list[dict],
    db_path: Path,
    settings: Settings,
) -> AsyncIterator[str]:
    """
    Async generator yielding JSON-encoded SSE data strings.
    Each string is one of:
      {"type": "text",        "content": str}
      {"type": "tool_call",   "tool": str, "input": dict}
      {"type": "tool_result", "tool": str, "result": dict}
      {"type": "done"}
    """
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    messages = list(history) + [{"role": "user", "content": message}]
    system = SYSTEM_PROMPT.format(date=datetime.now(timezone.utc).strftime("%Y-%m-%d"))

    for _ in range(MAX_TOOL_ITERATIONS):
        response = await client.messages.create(
            model=_MODEL,
            max_tokens=1024,
            system=system,
            tools=TOOLS,
            messages=messages,
        )

        for block in response.content:
            if block.type == "text":
                yield json.dumps({"type": "text", "content": block.text})

        if response.stop_reason != "tool_use":
            break

        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            yield json.dumps({"type": "tool_call", "tool": block.name, "input": block.input})
            result = _dispatch_tool(block.name, block.input, db_path, settings)
            yield json.dumps({"type": "tool_result", "tool": block.name, "result": result})
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result),
                }
            )

        messages = messages + [
            {"role": "assistant", "content": response.content},
            {"role": "user", "content": tool_results},
        ]

    yield json.dumps({"type": "done"})
