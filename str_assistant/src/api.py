"""FastAPI application for the STR Assistant."""

import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Callable

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from str_assistant.src.core.backend import initialize_backend
from str_assistant.src.core.exceptions.exceptions import AppException, AppExceptionCode
from str_assistant.src.core.storage import initialize_database
from str_assistant.src.routes.feedback import router as feedback_router
from str_assistant.src.routes.health import router as health_router
from str_assistant.src.routes.history import router as history_router
from str_assistant.src.routes.stream import router as stream_router
from str_assistant.src.routes.threads import router as threads_router
from str_assistant.src.settings import settings
from str_assistant.utils.pylogger import get_python_logger

logger = get_python_logger(settings.PYTHON_LOG_LEVEL)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable):
        if not settings.REQUEST_LOGGING_ENABLED:
            return await call_next(request)

        start_time = time.time()
        response = await call_next(request)
        duration_ms = (time.time() - start_time) * 1000
        logger.info(
            f"{request.method} {request.url.path} → {response.status_code} ({duration_ms:.1f}ms)"
        )
        return response


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("STR Assistant starting up")

    try:
        await initialize_database()
    except Exception as e:
        logger.critical(f"Failed to initialize database: {e}")
        raise

    try:
        initialize_backend()
    except Exception as e:
        logger.warning(f"Backend initialization warning: {e}")

    logger.info("STR Assistant ready")
    yield
    logger.info("STR Assistant shutting down")


app = FastAPI(lifespan=lifespan, title="STR Assistant", version="0.1.0")

app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.logger = get_python_logger(settings.PYTHON_LOG_LEVEL)

app.include_router(health_router)
app.include_router(stream_router)
app.include_router(feedback_router)
app.include_router(history_router)
app.include_router(threads_router)


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail_message": str(exc), "message": "Internal Server Error"},
    )


@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    logger.warning(f"App exception: {exc}")
    return JSONResponse(
        status_code=exc.response_code,
        content={
            "detail_message": exc.detail_message,
            "message": exc.message,
            "error_code": exc.error_code,
        },
    )
