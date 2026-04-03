"""Streaming route for the STR Assistant."""

import json
from collections.abc import AsyncGenerator

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from str_assistant.src.core.manager import AgentManager
from str_assistant.src.schema import StreamRequest
from str_assistant.src.settings import settings
from str_assistant.utils.pylogger import get_python_logger

router = APIRouter()
app_logger = get_python_logger(settings.PYTHON_LOG_LEVEL)


async def message_generator(
    user_input: StreamRequest, agent_manager: AgentManager
) -> AsyncGenerator[str, None]:
    try:
        app_logger.info(f"Starting stream for: {user_input.message[:100]}...")

        async for event in agent_manager.stream_response(user_input):
            if (
                event.get("type") == "message"
                and event.get("content", {}).get("type") == "human"
                and event.get("content", {}).get("content") == user_input.message
            ):
                continue

            payload = json.dumps(event, separators=(",", ":"))
            app_logger.info(f"SSE -> {payload[:200]}")
            yield f"{payload}\n\n"

    except Exception as e:
        app_logger.error(f"Error in message generator: {e}")
        error_event = {
            "type": "error",
            "content": {"message": "Internal server error", "recoverable": False},
        }
        yield f"{json.dumps(error_event)}\n\n"
    finally:
        yield "[DONE]\n\n"


@router.post("/v1/stream", response_class=StreamingResponse)
async def stream(user_input: StreamRequest, request: Request) -> StreamingResponse:
    """Stream STR Assistant responses in real-time."""
    access_token = request.headers.get("X-Token")

    try:
        agent_manager = AgentManager(sso_token=access_token)
    except Exception as e:
        app_logger.error(f"Failed to initialize AgentManager: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to initialize agent: {str(e)}")

    return StreamingResponse(
        message_generator(user_input, agent_manager),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
