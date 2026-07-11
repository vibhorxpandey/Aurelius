"""Aurelius MCP server (stdio).

Registers the research + fact-checking tools so any MCP-capable app can call them.
Launch with the `aurelius` console command, or `python -m aurelius`.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP

from .tools import diagrams, drafting, latex, ledger, scholarly, screening, search, style
from .autonomous.pipeline import run_autonomous_research

mcp = FastMCP(
    "Aurelius",
    instructions=(
        "Aurelius provides fact-checked research tools. Recommended workflow: "
        "(1) screen_topic to confirm the topic is in scope; "
        "(2) for long-form papers, call plan_paper_length first for a section-by-section "
        "word budget; (3) draft the paper yourself using draft_outline (or latex_outline "
        "for LaTeX) for structure; (4) for EVERY citation call verify_citation (checked "
        "against OpenAlex/Crossref, retraction-aware) and for key claims call web_search, "
        "or batch-verify a whole list at once with verify_claims; (5) remove or fix "
        "anything the evidence does not support -- an is_retracted:true result is an "
        "automatic reject regardless of anything else; (6) optionally call polish_prose "
        "on the now-verified draft for readability (never before fact-checking); "
        "(7) save_draft (use append=True for long-form papers, section by section) and "
        "save_report. Use diagram_template for any flowchart/architecture/sequence "
        "diagram, embedded as a fenced ```mermaid block. Never present a citation you "
        "did not verify."
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


# --- Drafting & long-form planning ----------------------------------------------
@mcp.tool()
def draft_outline(topic: str) -> Dict[str, str]:
    """Return a standard academic outline scaffold (Abstract..References) for a topic."""
    return drafting.draft_outline(topic)


@mcp.tool()
def plan_paper_length(
    target_pages: Optional[int] = None,
    target_pages_min: Optional[int] = None,
    target_pages_max: Optional[int] = None,
    words_per_page: int = drafting.WORDS_PER_PAGE_DEFAULT,
) -> Dict[str, Any]:
    """Compute a section-by-section word-count budget for a target page count.

    Use for long-form papers (e.g. 20-80 pages): call this first, then draft and
    verify section by section, appending each via save_draft(..., append=True)."""
    return drafting.plan_paper_length(target_pages, target_pages_min, target_pages_max, words_per_page)


@mcp.tool()
def save_draft(content: str, filename: str = "draft.md", append: bool = False) -> Dict[str, Any]:
    """Save (or, with append=True, append to) a Markdown research draft. Use
    append=True for long-form papers so you never resend the whole accumulated draft."""
    return drafting.save_draft(content, filename, append)


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
    """Verify an academic citation against OpenAlex and Crossref (falls back to a web
    search if the work isn't indexed there). Surfaces retraction status explicitly via
    `is_retracted` -- a retracted paper is never quietly treated as verified."""
    return scholarly.verify_citation(citation, max_results)


@mcp.tool()
def verify_claims(claims: List[str]) -> Dict[str, Any]:
    """Batch-verify a list of citations and/or factual claims in one call. Produces a
    scored evidence ledger (verification_score, per-item verdicts + sources) and a
    save_report-ready Markdown summary with unverified/retracted items struck through."""
    return ledger.verify_claims(claims)


# --- Style (post-verification only) ---------------------------------------------
@mcp.tool()
def polish_prose(
    content: str,
    use_llm: bool = False,
    model: str = "gpt-4o-mini-2024-07-18",
    provider: Optional[str] = None,
) -> Dict[str, Any]:
    """Improve prose style/readability of an ALREADY FACT-CHECKED draft -- never alters
    citations, numbers, or claims. This is a readability pass, not an AI-detector
    evasion tool. Default returns guidelines for you to apply yourself; set
    use_llm=True to have Aurelius rewrite it (needs an LLM key; falls back to
    guidelines if none is configured)."""
    return style.polish_prose(content, use_llm, model, provider)


# --- Diagrams --------------------------------------------------------------------
@mcp.tool()
def diagram_template(diagram_type: str, description: str) -> Dict[str, Any]:
    """Return a Mermaid syntax scaffold (flowchart | architecture | sequence) to
    complete and embed in a ```mermaid fenced block."""
    return diagrams.diagram_template(diagram_type, description)


# --- LaTeX -------------------------------------------------------------------------
@mcp.tool()
def latex_outline(topic: str) -> Dict[str, str]:
    """Return a compile-ready LaTeX article skeleton (Abstract..References) + a
    BibTeX entry stub."""
    return latex.latex_outline(topic)


@mcp.tool()
def save_latex(content: str, filename: str = "paper.tex") -> Dict[str, Any]:
    """Save LaTeX (.tex) or BibTeX (.bib) source to the Aurelius output directory."""
    return latex.save_latex(content, filename)


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
