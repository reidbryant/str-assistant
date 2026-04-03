"""Shell backend for the STR Assistant agent."""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from deepagents.backends import LocalShellBackend

from str_assistant.utils.pylogger import get_python_logger

logger = get_python_logger()

SYSTEM_PATH = "/usr/local/bin:/usr/bin:/bin"
_PASSTHROUGH_VARS = ("HOME", "USER", "LANG", "LC_ALL", "TZ", "TERM")

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / "agent_config"

_backend: LocalShellBackend | None = None


def _base_python() -> str:
    if sys.prefix != sys.base_prefix:
        candidate = Path(sys.base_prefix) / "bin" / "python3"
        if candidate.exists():
            return str(candidate)
    return sys.executable


def _ensure_venv(root_dir: Path, pyproject: Path) -> Path:
    project_hash = hashlib.sha256(str(root_dir.resolve()).encode()).hexdigest()[:12]
    toml_hash = hashlib.sha256(pyproject.read_bytes()).hexdigest()[:8]
    venv_dir = Path(tempfile.gettempdir()) / f"str-agent-venv-{project_hash}"
    stamp = venv_dir / ".toml_hash"

    needs_install = False
    if not (venv_dir / "bin" / "python").exists():
        base = _base_python()
        logger.info(f"Creating agent venv at {venv_dir}")
        subprocess.run([base, "-m", "venv", "--clear", str(venv_dir)], check=True, capture_output=True, text=True)
        needs_install = True

    if not needs_install and stamp.exists() and stamp.read_text() == toml_hash:
        logger.info(f"Agent venv up-to-date ({venv_dir})")
        return venv_dir

    pkg_dir = venv_dir / "_pkg"
    pkg_dir.mkdir(exist_ok=True)
    shutil.copy2(pyproject, pkg_dir / "pyproject.toml")

    pip = str(venv_dir / "bin" / "pip")
    logger.info(f"Installing dependencies from {pyproject.name}")
    result = subprocess.run([pip, "install", "--quiet", str(pkg_dir)], capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"pip install failed: {result.stderr.strip()}")

    stamp.write_text(toml_hash)
    return venv_dir


def _build_env(venv_dir: Path, extra: dict[str, str] | None = None) -> dict[str, str]:
    env = {k: os.environ[k] for k in _PASSTHROUGH_VARS if k in os.environ}
    env["VIRTUAL_ENV"] = str(venv_dir)
    env["PATH"] = f"{venv_dir}/bin:{SYSTEM_PATH}"
    if extra:
        env.update(extra)
    return env


def get_backend(
    root_dir: Path | None = None,
    pyproject: Path | None = None,
    *,
    timeout: int = 120,
    max_output_bytes: int = 100_000,
    extra_env: dict[str, str] | None = None,
) -> LocalShellBackend:
    global _backend
    if _backend is None:
        actual_root = root_dir or _REPO_ROOT
        actual_pyproject = pyproject or (_CONFIG_DIR / "pyproject.toml")

        if not actual_pyproject.is_file():
            logger.warning(f"pyproject.toml not found at {actual_pyproject}, using minimal backend")
            _backend = LocalShellBackend(
                root_dir=str(actual_root),
                virtual_mode=False,
                timeout=timeout,
                max_output_bytes=max_output_bytes,
            )
            return _backend

        venv_dir = _ensure_venv(actual_root, actual_pyproject)
        env = _build_env(venv_dir, extra_env)

        _backend = LocalShellBackend(
            root_dir=str(actual_root),
            virtual_mode=False,
            timeout=timeout,
            max_output_bytes=max_output_bytes,
            env=env,
        )
        logger.info(f"Backend ready — venv={venv_dir}")
    return _backend


def initialize_backend() -> LocalShellBackend:
    logger.info("Pre-initializing shell backend")
    backend = get_backend()
    logger.info("Backend initialization complete")
    return backend
