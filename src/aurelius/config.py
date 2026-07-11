"""Runtime configuration and API-key resolution for Aurelius.

Keys are read from environment variables so users never hard-code secrets. When an MCP
client launches the server it can inject these via the `env` block of its config file.
"""
from __future__ import annotations

import os
import tempfile
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


def get_contact_email() -> Optional[str]:
    """Optional contact email for Crossref's "polite pool" (faster, more reliable rate
    limits). Harmless to leave unset — Crossref works fine without it."""
    return _first_env("AURELIUS_CONTACT_EMAIL")


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

    Defaults to `~/aurelius_output` in the user's home directory. This is deliberately
    NOT relative to the current working directory: MCP clients (e.g. Claude Desktop)
    frequently launch the server with cwd set to a protected/unknown location such as
    ``C:\\Windows\\System32``, which is not writable. Override with AURELIUS_OUTPUT_DIR.
    Falls back to a temp directory if the preferred location can't be created.
    """
    candidates = []
    raw = os.environ.get("AURELIUS_OUTPUT_DIR")
    if raw:
        candidates.append(Path(raw).expanduser())
    candidates.append(Path.home() / "aurelius_output")
    candidates.append(Path(tempfile.gettempdir()) / "aurelius_output")

    for candidate in candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            return candidate.resolve()
        except OSError:
            continue

    # Last resort — never crash a tool call over the output location.
    fallback = Path(tempfile.gettempdir()) / "aurelius_output"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback.resolve()


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
