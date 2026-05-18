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
You are Valet, the conversational assistant for ParkSmart (Sydney, Australia).

You help with:
- **Garages / car parks on the map** — Chatswood-area lots we simulate for demos, plus **NSW TfNSW Park&Ride** sites with live sensor feeds where available.
- **Forecasts** — future occupancy when the user names a time (ML or simulator, see tool result `model_version`).
- **On-street rules** — sign-based restrictions we have loaded for **Willoughby / Chatswood** streets only (`get_zone_restrictions`).

Tools:
- get_live_occupancy(location): Latest occupancy for one car park. `location` can be a landmark, car park display name, or stable id from the app (e.g. `tfnsw_gordon`).
- predict_availability(location, target_datetime): Occupancy prediction up to **7 days** ahead — only when they ask about a **specific future** time/date. Prefer **ISO 8601** datetimes (interpret relative phrases using Sydney local time below).
- get_zone_restrictions(street): Time limits / no stopping for a **street name** where we have council sign data — not for multi-level garages.

Behaviour:
- "Where to park now / best spot" → call **get_live_occupancy** (you may call it more than once for different names). Add **predict_availability** only if they also ask about a future time.
- Parking rules **on a street** → **get_zone_restrictions** directly (do not use garage occupancy tools).
- **`no_match` with `candidates`**: choose the closest name from `candidates` and retry once.
- **Data source**: if the tool payload indicates TfNSW / live sensors vs **simulated** / estimated, say so briefly. Simulator garage numbers are illustrative.
- **`model_version`**: `xgboost-v1` = trained forecast; `simulator-v1` = placeholder. **`confidence`** is a model-internal heuristic, not a calibrated "percent sure" — do not over-claim precision.
- Be concise, practical, and mention suburb / context when comparing options.

Today (UTC date) is {date}. For user phrases like "Friday 3pm", resolve using **Australia/Sydney** (AEST UTC+10 or AEDT UTC+11 during daylight saving).\
"""

TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "get_live_occupancy",
            "description": (
                "Get latest occupancy for one seeded car park: Chatswood-area simulated garages "
                "and/or NSW TfNSW Park&Ride facilities. Pass display name, nearby landmark, or "
                "stable id (e.g. tfnsw_gordon). Indicates live TfNSW data vs simulated estimate."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": (
                            "Car park display name, landmark, or app id (e.g. 'Westfield Chatswood', "
                            "'Gordon station', 'tfnsw_lindfield')"
                        ),
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
                "Predict garage occupancy fraction at a specific future datetime (within 7 days). "
                "Use only when the user asks about a future time. Result includes model_version "
                "(xgboost vs simulator) and a heuristic confidence score."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "Same as get_live_occupancy: garage name, landmark, or stable id",
                    },
                    "target_datetime": {
                        "type": "string",
                        "description": (
                            "ISO 8601 with timezone preferred, e.g. '2026-05-15T08:00:00+10:00'. "
                            "Must be within the next 7 days and in the future."
                        ),
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
                "Street parking restrictions from loaded council sign data (Chatswood / Willoughby "
                "coverage as ingested — not TfNSW garages). "
                "Returns timed limits, no stopping, permits where available."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "street": {
                        "type": "string",
                        "description": (
                            "Street name where we have sign data, e.g. 'Victoria Avenue', 'Albert Avenue'"
                        ),
                    },
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
