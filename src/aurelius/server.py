"""Aurelius MCP server (stdio).

Registers the research + fact-checking tools so any MCP-capable app can call them.
Launch with the `aurelius` console command, or `python -m aurelius`.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from mcp.server.fastmcp import FastMCP

from .tools import drafting, screening, search
from .autonomous.pipeline import run_autonomous_research

mcp = FastMCP(
    "Aurelius",
    instructions=(
        "Aurelius provides fact-checked research tools. Recommended workflow: (1) screen_topic "
        "to confirm the topic is in scope; (2) draft the paper yourself using draft_outline for "
        "structure; (3) for EVERY citation call verify_citation and for key claims call web_search; "
        "(4) remove or fix anything the evidence does not support; (5) save_draft and save_report. "
        "Never present a citation you did not verify."
    ),
)


# --- Screening -----------------------------------------------------------------
@mcp.tool()
def get_research_policy() -> Dict[str, Any]:
    """Return Aurelius's admission policy (accepted vs restricted research domains)."""
    return screening.get_research_policy()


@mcp.tool()
def screen_topic(topic: str) -> Dict[str, Any]:
    """Screen a research topic against the restricted-domain policy before drafting.

    Returns a heuristic flag plus the full policy; you make the final accept/reject call.
    """
    return screening.screen_topic(topic)


# --- Drafting ------------------------------------------------------------------
@mcp.tool()
def draft_outline(topic: str) -> Dict[str, str]:
    """Return a standard academic outline scaffold (Abstract..References) for a topic."""
    return drafting.draft_outline(topic)


@mcp.tool()
def save_draft(content: str, filename: str = "draft.md") -> Dict[str, Any]:
    """Save a Markdown research draft to the Aurelius output directory."""
    return drafting.save_draft(content, filename)


@mcp.tool()
def save_report(content: str, filename: str = "verification.md") -> Dict[str, Any]:
    """Save a fact-checking report (first line 'STATUS: VERIFIED'/'STATUS: REJECTED')."""
    return drafting.save_report(content, filename)


# --- Fact-checking -------------------------------------------------------------
@mcp.tool()
def web_search(query: str, max_results: int = 5, academic_only: bool = False) -> Dict[str, Any]:
    """Search the web (Tavily) for evidence about a factual claim or question."""
    return search.web_search(query, max_results, academic_only)


@mcp.tool()
def verify_citation(citation: str, max_results: int = 5) -> Dict[str, Any]:
    """Check whether an academic citation actually exists in reputable sources (Tavily)."""
    return search.verify_citation(citation, max_results)


# --- Autonomous (BYO-key) mode -------------------------------------------------
@mcp.tool()
def autonomous_research(
    topic: str,
    model: str = "gpt-4o-mini-2024-07-18",
    provider: Optional[str] = None,
    max_rounds: int = 2,
) -> Dict[str, Any]:
    """Run the FULL research loop autonomously (screen -> draft -> fact-check -> revise).

    Requires an LLM API key with quota in the environment (OPENAI_API_KEY /
    ANTHROPIC_API_KEY / GOOGLE_API_KEY). Use this only when you want Aurelius to drive
    its own model instead of the host app's model. May take a few minutes.
    """
    return run_autonomous_research(topic, model=model, provider=provider, max_rounds=max_rounds)


def main() -> None:
    """Console entry point: run the MCP server over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
