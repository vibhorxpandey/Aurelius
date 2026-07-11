"""Aurelius — a fact-checked research MCP server.

Aurelius gives any MCP-capable app (Claude, Gemini CLI, Cursor, and — via a remote
deployment — ChatGPT) a set of research + fact-checking tools:

* screen a research topic against a restricted-domain policy,
* verify citations against real scholarly indexes (OpenAlex, Crossref, arXiv, Semantic
  Scholar) — DOI-precise, retraction-aware, and author/year-corroborated,
* verify a whole bibliography and numeric statistics (World Bank),
* batch-verify claims into a scored Evidence Ledger,
* search the web for general factual evidence (Tavily),
* polish already-verified prose, generate Mermaid diagrams, write LaTeX,
* plan and save long-form (20-80+ page) papers section by section,
* save drafts and verification reports.

By default the **host app's own model** does the reasoning, so Aurelius needs no LLM
API key of its own (host-driven mode). An optional **autonomous mode** runs the full
draft -> fact-check -> revise loop internally using a key you supply.
"""

__version__ = "0.3.0"

__all__ = ["__version__"]
