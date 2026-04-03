"""System prompt loader for the STR Assistant."""

from datetime import datetime
from pathlib import Path

_CONFIG_DIR = Path(__file__).parent.parent.parent / "agent_config"


def get_current_date() -> str:
    return datetime.now().strftime("%B %d, %Y")


def get_system_prompt() -> str:
    template_path = _CONFIG_DIR / "system-prompt.md"
    template = template_path.read_text()
    return template.replace("{{current_date}}", get_current_date())
