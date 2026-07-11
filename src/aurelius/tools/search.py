"""General web search evidence, backed by the Tavily API.

For citation verification, see `scholarly.py` — it checks against real bibliographic
indexes (OpenAlex, Crossref) rather than treating "a webpage mentioned it" as proof,
and it's retraction-aware. This module remains the source of general factual-claim
evidence, and is also `scholarly.py`'s fallback for citations that aren't indexed.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import httpx

from ..config import get_tavily_key

TAVILY_URL = "https://api.tavily.com/search"

# Reputable sources to bias academic citation checks toward. Callers can override.
ACADEMIC_DOMAINS = [
    "arxiv.org",
    "nature.com",
    "pubmed.ncbi.nlm.nih.gov",
    "scholar.google.com",
    "sciencedirect.com",
    "springer.com",
    "ieee.org",
    "jstor.org",
    "ssrn.com",
]


def _tavily_search(
    query: str,
    max_results: int,
    include_domains: Optional[List[str]],
    search_depth: str,
) -> Dict[str, Any]:
    api_key = get_tavily_key()
    if not api_key:
        return {
            "ok": False,
            "error": "TAVILY_API_KEY is not set. Get a free key at https://tavily.com and "
            "provide it via the TAVILY_API_KEY environment variable (see the Aurelius "
            "client config examples).",
        }

    payload: Dict[str, Any] = {
        "api_key": api_key,
        "query": query,
        "search_depth": search_depth,
        "include_answer": True,
        "max_results": max_results,
    }
    if include_domains:
        payload["include_domains"] = include_domains

    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(TAVILY_URL, json=payload)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as e:
        return {"ok": False, "error": f"Tavily HTTP {e.response.status_code}: {e.response.text[:200]}"}
    except Exception as e:  # noqa: BLE001 - surface any transport error to the model
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}

    results = [
        {
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "snippet": (r.get("content", "") or "")[:600],
            "score": r.get("score"),
        }
        for r in data.get("results", [])
    ]
    return {"ok": True, "answer": data.get("answer"), "results": results}


def web_search(query: str, max_results: int = 5, academic_only: bool = False) -> Dict[str, Any]:
    """Search the web for evidence about a factual claim.

    Args:
        query: A factual claim or question to check, e.g. "Okun's law coefficient US 0.5".
        max_results: Number of results to return (1-10).
        academic_only: If True, restrict to reputable academic domains.

    Returns a dict with `answer` (Tavily's synthesized answer) and `results`
    (title/url/snippet/score), or `{ok: false, error: ...}` on failure.
    """
    max_results = max(1, min(int(max_results), 10))
    domains = ACADEMIC_DOMAINS if academic_only else None
    return _tavily_search(query, max_results, domains, search_depth="advanced")
