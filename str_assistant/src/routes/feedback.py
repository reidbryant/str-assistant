"""Feedback route (stub — Langfuse optional)."""

from fastapi import APIRouter

from str_assistant.src.schema import FeedbackRequest, FeedbackResponse
from str_assistant.utils.pylogger import get_python_logger

router = APIRouter()
logger = get_python_logger()


@router.post("/v1/feedback", response_model=FeedbackResponse)
async def record_feedback(feedback: FeedbackRequest):
    """Record user feedback (logged locally; Langfuse optional)."""
    logger.info(
        f"Feedback received: run_id={feedback.run_id}, key={feedback.key}, score={feedback.score}"
    )
    return FeedbackResponse(status="success")
