from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from app.config import Settings, get_settings
from app.models import ChatRequest
from app.services import llm_service

router = APIRouter()


@router.post("/chat")
async def chat(
    request: ChatRequest,
    settings: Settings = Depends(get_settings),
) -> StreamingResponse:
    async def event_stream():
        async for chunk in llm_service.chat_stream(
            request.message, request.history, settings.db_path, settings
        ):
            yield f"data: {chunk}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
