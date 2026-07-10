"""Aurelius — a fact-checked research MCP server.

Aurelius gives any MCP-capable app (Claude, Gemini CLI, Cursor, and — via a remote
deployment — ChatGPT) a set of research + fact-checking tools:

* screen a research topic against a restricted-domain policy,
* search the web and verify citations against live sources (Tavily),
* save drafts and verification reports.

By default the **host app's own model** does the reasoning, so Aurelius needs no LLM
API key of its own (host-driven mode). An optional **autonomous mode** runs the full
draft -> fact-check -> revise loop internally using a key you supply.
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
