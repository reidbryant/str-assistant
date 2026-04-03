"""Settings for the STR Assistant agent."""

from typing import Optional

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings

from str_assistant.utils.pylogger import get_python_logger

logger = get_python_logger()

try:
    load_dotenv()
except Exception as e:
    logger.warning(f"Could not load .env file: {e}")


class Settings(BaseSettings):
    """Configuration settings for the STR Assistant."""

    # Server
    AGENT_HOST: str = Field(default="0.0.0.0")
    AGENT_PORT: int = Field(default=8081)
    AGENT_SSL_KEYFILE: Optional[str] = Field(default=None)
    AGENT_SSL_CERTFILE: Optional[str] = Field(default=None)
    PYTHON_LOG_LEVEL: str = Field(default="INFO")
    USE_INMEMORY_SAVER: bool = Field(default=True)

    # Database (only needed when USE_INMEMORY_SAVER=False)
    POSTGRES_USER: str = Field(default="pgvector")
    POSTGRES_PASSWORD: str = Field(default="pgvector")
    POSTGRES_DB: str = Field(default="pgvector")
    POSTGRES_HOST: str = Field(default="pgvector")
    POSTGRES_PORT: int = Field(default=5432)

    # LLM (OpenAI)
    OPENAI_API_KEY: str = Field(default="")
    OPENAI_MODEL: str = Field(default="gpt-4o-mini")

    # Langfuse (optional tracing)
    LANGFUSE_PUBLIC_KEY: Optional[str] = Field(default=None)
    LANGFUSE_SECRET_KEY: Optional[str] = Field(default=None)
    LANGFUSE_BASE_URL: Optional[str] = Field(default=None)

    # MCP Server
    MCP_SERVER_NAME: str = Field(default="str-mcp-server")
    MCP_SERVER_URL: str = Field(default="http://localhost:5001/mcp/")
    MCP_TRANSPORT_PROTOCOL: str = Field(default="streamable_http")
    MCP_CONNECTION_TIMEOUT: int = Field(default=30)
    MCP_SSL_VERIFY: bool = Field(default=False)

    # Request logging
    REQUEST_LOGGING_ENABLED: bool = Field(default=True)
    REQUEST_LOG_HEADERS: bool = Field(default=False)
    REQUEST_LOG_BODY: bool = Field(default=False)
    REQUEST_LOG_BODY_MAX_SIZE: int = Field(default=10240)

    @property
    def database_uri(self) -> str:
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"


settings = Settings()
