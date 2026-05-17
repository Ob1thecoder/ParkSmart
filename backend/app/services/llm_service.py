import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncIterator

import openai

from app.config import Settings
from app.services import occupancy_service, prediction_service, zone_service

log = logging.getLogger(__name__)

MAX_TOOL_ITERATIONS = 5
_MODEL = "gpt-4o-mini"

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
        "type": "function",
        "function": {
            "name": "get_live_occupancy",
            "description": (
                "Get current parking occupancy for a car park in Chatswood CBD. "
                "Returns occupancy percentage, available spots, and whether the data is "
                "live (from TfNSW sensors) or estimated."
            ),
            "parameters": {
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
    },
    {
        "type": "function",
        "function": {
            "name": "predict_availability",
            "description": (
                "Predict parking availability at a specific future time (up to 7 days ahead). "
                "Use this only when the user mentions a future time, not for current conditions."
            ),
            "parameters": {
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
    },
    {
        "type": "function",
        "function": {
            "name": "get_zone_restrictions",
            "description": (
                "Get street parking time restrictions for a street in Chatswood CBD. "
                "Returns no-stopping zones, timed parking limits, and permit areas."
            ),
            "parameters": {
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
      {"type": "error",       "message": str}
      {"type": "done"}
    """
    if not settings.openai_api_key:
        yield json.dumps({"type": "error", "message": "OpenAI API key not configured on server."})
        yield json.dumps({"type": "done"})
        return

    client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
    system = SYSTEM_PROMPT.format(date=datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    messages = (
        [{"role": "system", "content": system}]
        + list(history)
        + [{"role": "user", "content": message}]
    )

    try:
        for _ in range(MAX_TOOL_ITERATIONS):
            response = await client.chat.completions.create(
                model=_MODEL,
                max_tokens=1024,
                messages=messages,
                tools=TOOLS,
            )

            choice = response.choices[0]

            if choice.message.content:
                yield json.dumps({"type": "text", "content": choice.message.content})

            if choice.finish_reason != "tool_calls":
                break

            tool_calls = choice.message.tool_calls or []
            assistant_msg = {
                "role": "assistant",
                "content": choice.message.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in tool_calls
                ],
            }
            messages.append(assistant_msg)

            for tc in tool_calls:
                inputs = json.loads(tc.function.arguments)
                yield json.dumps({"type": "tool_call", "tool": tc.function.name, "input": inputs})
                result = _dispatch_tool(tc.function.name, inputs, db_path, settings)
                yield json.dumps({"type": "tool_result", "tool": tc.function.name, "result": result})
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": json.dumps(result)})

    except openai.RateLimitError as e:
        log.error("OpenAI rate limit error: %s", e)
        yield json.dumps({"type": "error", "message": "OpenAI quota exceeded. Please check your billing."})
    except openai.AuthenticationError as e:
        log.error("OpenAI auth error: %s", e)
        yield json.dumps({"type": "error", "message": "Invalid OpenAI API key."})
    except openai.APIError as e:
        log.error("OpenAI API error: %s", e)
        yield json.dumps({"type": "error", "message": f"OpenAI error: {e.message}"})
    except Exception as e:
        log.exception("Unexpected error in chat_stream")
        yield json.dumps({"type": "error", "message": f"Unexpected error: {str(e)}"})

    yield json.dumps({"type": "done"})
