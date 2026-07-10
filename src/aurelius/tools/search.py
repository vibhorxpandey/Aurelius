"""Web search and citation verification, backed by the Tavily API.

These are the heart of Aurelius's fact-checking: every claim or citation the model
makes can be checked against live, reputable web sources instead of trusted blindly.
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


def verify_citation(citation: str, max_results: int = 5) -> Dict[str, Any]:
    """Check whether an academic citation actually exists in reputable sources.

    Args:
        citation: The citation text, e.g. "Okun, A. M. (1962). Potential GNP: Its Measurement and Significance".
        max_results: Number of corroborating results to return.

    Returns a dict with `found` (bool heuristic), `answer`, and `results`. The final
    judgement should be made by the model reading the evidence, but `found` gives a
    quick signal based on whether reputable sources surface the work.
    """
    query = f'Verify this academic paper exists: "{citation}"'
    result = _tavily_search(query, max(1, min(int(max_results), 10)), ACADEMIC_DOMAINS, "advanced")
    if not result.get("ok"):
        return result
    # Heuristic: consider it corroborated if at least one reputable result scores well.
    corroborated = any((r.get("score") or 0) >= 0.5 for r in result.get("results", []))
    result["found"] = bool(corroborated)
    result["citation"] = citation
    return result
