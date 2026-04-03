"""Global in-memory storage for the STR Assistant."""

from typing import Optional

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore

from str_assistant.src.core.exceptions.exceptions import AppException, AppExceptionCode
from str_assistant.src.settings import settings
from str_assistant.utils.pylogger import get_python_logger

logger = get_python_logger(settings.PYTHON_LOG_LEVEL)

_global_checkpoint: Optional[InMemorySaver] = None
_global_store: Optional[InMemoryStore] = None
_thread_registry: dict[str, set[str]] = {}


def get_global_checkpoint() -> InMemorySaver:
    global _global_checkpoint
    if _global_checkpoint is None:
        _global_checkpoint = InMemorySaver()
        logger.info("Created global InMemorySaver checkpoint instance")
    return _global_checkpoint


def get_global_store() -> InMemoryStore:
    global _global_store
    if _global_store is None:
        _global_store = InMemoryStore()
        logger.info("Created global InMemoryStore instance")
    return _global_store


def register_thread(user_id: str, thread_id: str) -> None:
    global _thread_registry
    if user_id not in _thread_registry:
        _thread_registry[user_id] = set()
    _thread_registry[user_id].add(thread_id)


def get_user_threads(user_id: str) -> list[str]:
    global _thread_registry
    return list(_thread_registry.get(user_id, set()))


def reset_global_storage() -> None:
    global _global_checkpoint, _global_store, _thread_registry
    _global_checkpoint = None
    _global_store = None
    _thread_registry = {}


async def initialize_database() -> None:
    if settings.USE_INMEMORY_SAVER:
        logger.info("Using in-memory storage — skipping database initialization")
        return

    try:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        logger.info("Initializing PostgreSQL database schema")
        async with AsyncPostgresSaver.from_conn_string(settings.database_uri) as checkpoint:
            if hasattr(checkpoint, "setup"):
                await checkpoint.setup()
        logger.info("Database schema initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database schema: {e}", exc_info=True)
        raise AppException(
            f"Database initialization failed: {str(e)}",
            AppExceptionCode.CONFIGURATION_INITIALIZATION_ERROR,
        )
