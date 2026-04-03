"""Main entry point for the STR Assistant."""

import sys
from typing import Any

import uvicorn

from str_assistant.src.api import app
from str_assistant.src.settings import settings
from str_assistant.utils.pylogger import get_python_logger, get_uvicorn_log_config

logger = get_python_logger()


def main() -> None:
    try:
        logger.info(f"Starting STR Assistant on {settings.AGENT_HOST}:{settings.AGENT_PORT}")
        logger.info(f"MCP Server URL: {settings.MCP_SERVER_URL}")
        logger.info(f"OpenAI model: {settings.GEMINI_MODEL}")

        uvicorn_config: dict[str, Any] = {}
        if settings.AGENT_SSL_KEYFILE and settings.AGENT_SSL_CERTFILE:
            uvicorn_config["ssl_keyfile"] = settings.AGENT_SSL_KEYFILE
            uvicorn_config["ssl_certfile"] = settings.AGENT_SSL_CERTFILE

        uvicorn.run(
            app,
            host=settings.AGENT_HOST,
            port=settings.AGENT_PORT,
            log_config=get_uvicorn_log_config(settings.PYTHON_LOG_LEVEL),
            **uvicorn_config,
        )
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.critical(f"Server startup failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
