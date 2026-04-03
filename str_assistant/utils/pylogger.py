"""Structured logger utility for the STR Assistant."""

import logging
import sys
from typing import Any, Dict, List, Set

import structlog

HTTP_CLIENT_LOGGERS = {"urllib3", "requests", "httpx"}
MCP_LOGGERS = {"fastmcp", "fastmcp.server", "fastmcp.server.http"}
OBSERVABILITY_LOGGERS = {"langfuse", "langfuse.client", "langfuse.callback"}
SILENT_LOGGERS: Set[str] = {"opentelemetry.context"}

THIRD_PARTY_LOGGERS: Set[str] = (
    HTTP_CLIENT_LOGGERS | MCP_LOGGERS | OBSERVABILITY_LOGGERS | SILENT_LOGGERS
)
ERROR_ONLY_LOGGERS: Set[str] = OBSERVABILITY_LOGGERS

_LOGGING_CONFIGURED = False

for _name in SILENT_LOGGERS:
    logging.getLogger(_name).setLevel(logging.CRITICAL)


def _clear_handlers(logger: logging.Logger) -> None:
    logger.handlers.clear()
    logger.filters.clear()


def _setup_logger(logger_name: str, level: str) -> None:
    logger = logging.getLogger(logger_name)
    _clear_handlers(logger)
    if logger_name in SILENT_LOGGERS:
        logger.setLevel(logging.CRITICAL)
    elif logger_name in ERROR_ONLY_LOGGERS:
        logger.setLevel(logging.ERROR)
    else:
        logger.setLevel(level)
    logger.propagate = True


def _configure_third_party_loggers(log_level: str) -> None:
    logging.getLogger().handlers.clear()
    for name in THIRD_PARTY_LOGGERS:
        _setup_logger(name, log_level)


def force_reconfigure_all_loggers(log_level: str = "INFO") -> None:
    global _LOGGING_CONFIGURED
    _LOGGING_CONFIGURED = False
    get_python_logger(log_level)


def get_python_logger(log_level: str = "INFO") -> structlog.BoundLogger:
    global _LOGGING_CONFIGURED
    log_level = log_level.upper()

    if not _LOGGING_CONFIGURED:
        logging.basicConfig(
            format="%(message)s",
            stream=sys.stdout,
            level=log_level,
        )
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
                structlog.processors.JSONRenderer(),
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )
        _LOGGING_CONFIGURED = True

    _configure_third_party_loggers(log_level)
    return structlog.get_logger()


def get_uvicorn_log_config(log_level: str = "INFO") -> Dict[str, Any]:
    log_level = log_level.upper()
    default_formatter = {
        "()": "structlog.stdlib.ProcessorFormatter",
        "processor": structlog.processors.JSONRenderer(),
        "foreign_pre_chain": [
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
        ],
    }

    def make_logger_config(names: List[str], level: str) -> Dict[str, Any]:
        return {
            name: {"handlers": ["default"], "level": level, "propagate": False}
            for name in names
        }

    passthrough_formatter = {"format": "%(message)s"}
    uvicorn_loggers = ["uvicorn", "uvicorn.error", "uvicorn.asgi", "uvicorn.protocols"]
    access_loggers = ["uvicorn.access"]

    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": default_formatter,
            "access": default_formatter,
            "passthrough": passthrough_formatter,
        },
        "handlers": {
            "default": {
                "formatter": "default",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
            },
            "access": {
                "formatter": "access",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
            },
            "passthrough": {
                "formatter": "passthrough",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
            },
        },
        "loggers": {
            "": {"handlers": ["passthrough"], "level": log_level, "propagate": False},
            **make_logger_config(uvicorn_loggers, log_level),
            **make_logger_config(access_loggers, log_level),
            **make_logger_config(
                list(THIRD_PARTY_LOGGERS - ERROR_ONLY_LOGGERS - SILENT_LOGGERS),
                log_level,
            ),
            **make_logger_config(list(ERROR_ONLY_LOGGERS), "ERROR"),
            **make_logger_config(list(SILENT_LOGGERS), "CRITICAL"),
        },
    }
