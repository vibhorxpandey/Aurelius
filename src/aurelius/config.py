"""Runtime configuration and API-key resolution for Aurelius.

Keys are read from environment variables so users never hard-code secrets. When an MCP
client launches the server it can inject these via the `env` block of its config file.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


def _first_env(*names: str) -> Optional[str]:
    """Return the first non-empty environment variable among `names`."""
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    return None


def get_tavily_key() -> Optional[str]:
    """Tavily key for web search / citation verification (host-driven + autonomous modes)."""
    return _first_env("TAVILY_API_KEY", "AURELIUS_TAVILY_API_KEY")


def get_llm_key(provider: str) -> Optional[str]:
    """LLM key for autonomous mode. Only needed if you use `autonomous_research`.

    provider: 'openai' | 'anthropic' | 'google'
    """
    provider = provider.lower()
    if provider == "openai":
        return _first_env("OPENAI_API_KEY", "AURELIUS_OPENAI_API_KEY")
    if provider == "anthropic":
        return _first_env("ANTHROPIC_API_KEY", "AURELIUS_ANTHROPIC_API_KEY")
    if provider == "google":
        return _first_env("GOOGLE_API_KEY", "GEMINI_API_KEY", "AURELIUS_GOOGLE_API_KEY")
    return None


def get_output_dir() -> Path:
    """Directory where drafts and reports are written.

    Defaults to `./aurelius_output` under the current working directory. Override with
    AURELIUS_OUTPUT_DIR. The directory is created on demand.
    """
    raw = os.environ.get("AURELIUS_OUTPUT_DIR", "aurelius_output")
    path = Path(raw).expanduser().resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def resolve_output_path(filename: str) -> Path:
    """Resolve a user-supplied filename safely inside the output directory.

    Prevents path traversal: only the basename is honored unless an absolute path is
    explicitly given (which we then respect, since the server runs locally).
    """
    p = Path(filename)
    if p.is_absolute():
        p.parent.mkdir(parents=True, exist_ok=True)
        return p
    return get_output_dir() / p.name
