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


def get_semantic_scholar_key() -> Optional[str]:
    """Optional Semantic Scholar API key (raises rate limits). The API works keyless too."""
    return _first_env("SEMANTIC_SCHOLAR_API_KEY", "AURELIUS_SEMANTIC_SCHOLAR_API_KEY")


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


def get_proof_hmac_secret() -> Optional[str]:
    """Optional shared secret for HMAC-signing Proof-of-Rigor bundles (Phase 3).

    If unset, Aurelius signs with a local ed25519 key when `cryptography` is available, or
    falls back to a content hash only. The content hash alone already makes the proof
    tamper-evident; a signature adds authenticity."""
    return _first_env("AURELIUS_PROOF_HMAC_SECRET")


def get_pinata_jwt() -> Optional[str]:
    """Optional Pinata JWT for pinning Proof-of-Rigor bundles to IPFS (Phase 3). Without it,
    proofs are stored locally only."""
    return _first_env("PINATA_JWT", "AURELIUS_PINATA_JWT")


def get_chain_config() -> dict:
    """Optional blockchain-anchoring config (Phase 3). Anchoring is skipped unless BOTH an
    RPC URL and a funded private key are set (and the `web3` extra is installed).

    Returns {"rpc": str|None, "private_key": str|None, "chain_id": int|None}.
    """
    chain_id = _first_env("AURELIUS_CHAIN_ID")
    return {
        "rpc": _first_env("AURELIUS_CHAIN_RPC", "AURELIUS_CHAIN_RPC_URL"),
        "private_key": _first_env("AURELIUS_CHAIN_PRIVATE_KEY"),
        "chain_id": int(chain_id) if chain_id and chain_id.isdigit() else None,
    }


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
