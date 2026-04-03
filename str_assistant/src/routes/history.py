"""History route — returns conversation messages for a thread."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from str_assistant.src.core.storage import get_global_checkpoint
from str_assistant.src.core.agent_utils import langchain_to_chat_message
from str_assistant.src.schema import ChatHistoryResponse
from str_assistant.src.settings import settings
from str_assistant.utils.pylogger import get_python_logger

router = APIRouter()
logger = get_python_logger(settings.PYTHON_LOG_LEVEL)


@router.get("/v1/history/{thread_id}", response_model=ChatHistoryResponse)
async def get_history(thread_id: str):
    """Get conversation history for a thread."""
    try:
        checkpoint = get_global_checkpoint()
        config = {"configurable": {"thread_id": thread_id}}

        state = await checkpoint.aget(config)
        if state is None:
            return ChatHistoryResponse(messages=[])

        raw_messages = state.get("channel_values", {}).get("messages", [])
        chat_messages = []
        for msg in raw_messages:
            try:
                chat_messages.append(langchain_to_chat_message(msg))
            except Exception as e:
                logger.warning(f"Could not convert message: {e}")

        return ChatHistoryResponse(messages=chat_messages)
    except Exception as e:
        logger.error(f"Error fetching history for thread {thread_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
