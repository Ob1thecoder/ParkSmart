import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from app.config import Settings
from app.services import llm_service


def _make_settings(seeded_db: Path) -> Settings:
    return Settings(db_path=seeded_db, openai_api_key="test-key")


def _text_response(text: str) -> MagicMock:
    message = MagicMock()
    message.content = text
    message.tool_calls = None
    choice = MagicMock()
    choice.message = message
    choice.finish_reason = "stop"
    resp = MagicMock()
    resp.choices = [choice]
    return resp


def _tool_response(name: str, inputs: dict, tool_id: str = "call_01") -> MagicMock:
    tc = MagicMock()
    tc.id = tool_id
    tc.function.name = name
    tc.function.arguments = json.dumps(inputs)
    message = MagicMock()
    message.content = None
    message.tool_calls = [tc]
    choice = MagicMock()
    choice.message = message
    choice.finish_reason = "tool_calls"
    resp = MagicMock()
    resp.choices = [choice]
    return resp


# --- _dispatch_tool ---

def test_dispatch_get_live_occupancy(seeded_db):
    result = llm_service._dispatch_tool(
        "get_live_occupancy", {"location": "Westfield"}, seeded_db, _make_settings(seeded_db)
    )
    assert "error" not in result or result.get("error") == "no_match"
    if "error" not in result:
        assert "occupancy_pct" in result


def test_dispatch_get_zone_restrictions(seeded_db):
    result = llm_service._dispatch_tool(
        "get_zone_restrictions", {"street": "Victoria Avenue"}, seeded_db, _make_settings(seeded_db)
    )
    assert "street" in result or "error" in result


def test_dispatch_predict_availability(seeded_db):
    from datetime import datetime, timedelta, timezone
    target = (datetime.now(timezone.utc) + timedelta(hours=4)).isoformat()
    result = llm_service._dispatch_tool(
        "predict_availability",
        {"location": "Westfield", "target_datetime": target},
        seeded_db,
        _make_settings(seeded_db),
    )
    assert "predicted_occupancy_pct" in result or "error" in result


def test_dispatch_unknown_tool_returns_error(seeded_db):
    result = llm_service._dispatch_tool(
        "fly_to_moon", {"destination": "moon"}, seeded_db, _make_settings(seeded_db)
    )
    assert result["error"] == "unknown_tool"


# --- chat_stream ---

@pytest.mark.asyncio
async def test_chat_stream_no_tool_call(seeded_db):
    settings = _make_settings(seeded_db)
    mock_resp = _text_response("Westfield has 392 spots available.")

    with patch("app.services.llm_service.openai.AsyncOpenAI") as MockOAI:
        instance = MockOAI.return_value
        instance.chat.completions.create = AsyncMock(return_value=mock_resp)

        chunks = []
        async for chunk in llm_service.chat_stream("Where to park?", [], seeded_db, settings):
            chunks.append(json.loads(chunk))

    types = [c["type"] for c in chunks]
    assert "text" in types
    assert "done" in types


@pytest.mark.asyncio
async def test_chat_stream_one_tool_call_then_text(seeded_db):
    settings = _make_settings(seeded_db)
    tool_resp = _tool_response("get_live_occupancy", {"location": "Westfield"})
    text_resp = _text_response("Westfield is 72% full.")

    with patch("app.services.llm_service.openai.AsyncOpenAI") as MockOAI:
        instance = MockOAI.return_value
        instance.chat.completions.create = AsyncMock(side_effect=[tool_resp, text_resp])

        chunks = []
        async for chunk in llm_service.chat_stream("Where to park?", [], seeded_db, settings):
            chunks.append(json.loads(chunk))

    types = [c["type"] for c in chunks]
    assert "tool_call" in types
    assert "tool_result" in types
    assert "text" in types
    assert "done" in types


@pytest.mark.asyncio
async def test_chat_stream_stops_after_max_iterations(seeded_db):
    settings = _make_settings(seeded_db)
    always_tool = _tool_response("get_live_occupancy", {"location": "Westfield"})

    with patch("app.services.llm_service.openai.AsyncOpenAI") as MockOAI:
        instance = MockOAI.return_value
        instance.chat.completions.create = AsyncMock(return_value=always_tool)

        chunks = []
        async for chunk in llm_service.chat_stream("Hello", [], seeded_db, settings):
            chunks.append(json.loads(chunk))

    assert chunks[-1]["type"] == "done"
    tool_calls = [c for c in chunks if c["type"] == "tool_call"]
    assert len(tool_calls) == llm_service.MAX_TOOL_ITERATIONS
