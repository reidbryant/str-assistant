"""Threads route — returns thread list for a user."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from str_assistant.src.core.storage import get_user_threads
from str_assistant.src.settings import settings
from str_assistant.utils.pylogger import get_python_logger

router = APIRouter()
logger = get_python_logger(settings.PYTHON_LOG_LEVEL)


@router.get("/v1/threads/{user_id}")
async def get_threads(user_id: str):
    """Get all thread IDs for a user."""
    threads = get_user_threads(user_id)
    return JSONResponse(content={"user_id": user_id, "threads": threads})
