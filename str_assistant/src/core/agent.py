"""Core agent implementation for the STR Assistant using deepagents + OpenAI."""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import yaml
from deepagents import SubAgent, create_deep_agent
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.memory import InMemorySaver

from str_assistant.src.core.backend import get_backend
from str_assistant.src.core.exceptions.exceptions import AppException, AppExceptionCode
from str_assistant.src.core.prompt import get_system_prompt
from str_assistant.src.core.storage import get_global_checkpoint, get_global_store
from str_assistant.src.settings import settings
from str_assistant.utils.pylogger import get_python_logger

logger = get_python_logger(settings.PYTHON_LOG_LEVEL)

CONFIG_DIR = Path(__file__).parent.parent.parent / "agent_config"


def _parse_agent_frontmatter(path: Path) -> dict[str, Any]:
    """Parse a markdown agent file with YAML frontmatter."""
    content = path.read_text()
    if not content.startswith("---"):
        return {"body": content.strip()}

    parts = content.split("---", 2)
    if len(parts) < 3:
        return {"body": content.strip()}

    frontmatter: dict[str, Any] = yaml.safe_load(parts[1]) or {}
    frontmatter["body"] = parts[2].strip()
    return frontmatter


@asynccontextmanager
async def get_str_agent(sso_token: str | None = None):
    """Get a fully initialized STR deep agent with MCP tools, subagents, and memory."""
    tools: list = []

    logger.info(f"Connecting to MCP server at {settings.MCP_SERVER_URL}")

    try:
        import asyncio
        import httpx

        async def connect_with_timeout():
            server_config: dict = {
                "url": settings.MCP_SERVER_URL,
                "transport": settings.MCP_TRANSPORT_PROTOCOL,
                "headers": {"Authorization": f"Bearer {sso_token}"} if sso_token else {},
            }

            if not settings.MCP_SSL_VERIFY:
                server_config["httpx_client_factory"] = (
                    lambda **kwargs: httpx.AsyncClient(verify=False, **kwargs)  # nosec B501
                )

            client = MultiServerMCPClient({settings.MCP_SERVER_NAME: server_config})
            return await client.get_tools()

        tools = await asyncio.wait_for(
            connect_with_timeout(), timeout=settings.MCP_CONNECTION_TIMEOUT
        )
        logger.info(f"Connected to MCP server — loaded {len(tools)} tools: {[t.name for t in tools]}")

    except Exception as e:
        logger.error(f"Failed to connect to MCP server: {type(e).__name__}: {e}")

        if settings.USE_INMEMORY_SAVER:
            logger.warning("Running in local dev mode without MCP tools")
            tools = []
        else:
            raise AppException(
                f"Failed to connect to MCP server at {settings.MCP_SERVER_URL}: {e}",
                AppExceptionCode.PRODUCTION_MCP_CONNECTION_ERROR,
            )

    # Initialize Google Gemini model
    if not settings.GOOGLE_API_KEY:
        raise AppException(
            "GOOGLE_API_KEY is not set. Get a free key at https://aistudio.google.com/app/apikey",
            AppExceptionCode.CONFIGURATION_VALIDATION_ERROR,
        )

    model = ChatGoogleGenerativeAI(
        model=settings.GEMINI_MODEL,
        temperature=0,
        google_api_key=settings.GOOGLE_API_KEY,
    )

    # Load subagent definitions from agents/ directory
    agents_dir = CONFIG_DIR / "agents"
    tool_by_name = {t.name: t for t in tools}
    skills_base = CONFIG_DIR / "skills"

    main_skills_dir = skills_base / "str-intake"
    main_skills_path = [str(main_skills_dir)] if main_skills_dir.exists() else []

    subagents_config: list[SubAgent] | None = None
    if agents_dir.is_dir():
        subagents_config = []
        for agent_file in sorted(agents_dir.glob("*.md")):
            config = _parse_agent_frontmatter(agent_file)
            name = config.get("name", agent_file.stem)

            sa: SubAgent = SubAgent(
                name=name,
                description=config.get("description", ""),
                system_prompt=config.get("body", ""),
            )

            yaml_tool_names = config.get("tools", [])
            if yaml_tool_names:
                resolved = [tool_by_name[n] for n in yaml_tool_names if n in tool_by_name]
                missing = [n for n in yaml_tool_names if n not in tool_by_name]
                if missing:
                    logger.warning(f"Subagent '{name}' references unknown tools: {missing}")
                sa["tools"] = resolved

            skill_names = config.get("skills", [])
            if skill_names:
                skill_paths: list[str] = []
                for skill_name in skill_names:
                    skill_dir = skills_base / skill_name
                    if skill_dir.exists():
                        skill_paths.append(str(skill_dir))
                if skill_paths:
                    sa["skills"] = skill_paths

            subagents_config.append(sa)
            logger.info(f"Loaded subagent: {name}")
    else:
        logger.warning(f"Agents directory not found at {agents_dir}")

    system_prompt = get_system_prompt()
    backend = get_backend()

    checkpointer = get_global_checkpoint()
    store = get_global_store()

    agent = create_deep_agent(
        model=model,
        system_prompt=system_prompt,
        skills=main_skills_path,
        tools=[],
        subagents=subagents_config,
        backend=backend,
        checkpointer=checkpointer,
        store=store,
    )
    logger.info("STR deep agent initialized successfully")
    yield agent
