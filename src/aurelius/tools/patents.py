"""Patent-freedom screening (Phase 5): surface potentially-overlapping patents.

Backends, in order:
  1. **PatentsView** (USPTO full-text search, free key from patentsview.org) — real patent
     records: number, title, date, assignees.
  2. **Web search fallback** (Tavily, if configured) — patent mentions from Google Patents
     and similar, lower precision.
  3. Neither configured → an honest "insufficient data" verdict, never a fake all-clear.

**This is a screening aid, not legal advice.** Freedom-to-operate is a legal opinion that
depends on claim construction, jurisdictions, and prosecution history — only patent counsel
can give it. Every result carries that disclaimer.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

import httpx

from ..config import get_patentsview_key
from . import search

PATENTSVIEW_URL = "https://search.patentsview.org/api/v1/patent/"

DISCLAIMER = (
    "Screening aid only - NOT legal advice. Freedom-to-operate requires analysis of patent "
    "claims by qualified counsel. Absence of hits here does not prove freedom to operate."
)


def search_patents(query: str, max_results: int = 5) -> Dict[str, Any]:
    """Search for patents matching `query`. Returns {"ok", "backend", "results", "note"}."""
    key = get_patentsview_key()
    if key:
        return _patentsview(query, max_results, key)

    r = search.web_search(f"patent {query}", max_results=max_results, academic_only=False)
    if r.get("ok"):
        return {"ok": True, "backend": "web", "results": [
            {"title": x.get("title", ""), "url": x.get("url", ""), "snippet": x.get("snippet", "")}
            for x in r.get("results", [])
        ], "note": "Web-search fallback (set PATENTSVIEW_API_KEY for real USPTO records)."}

    return {"ok": False, "backend": "none", "results": [],
            "note": "No patent data source configured (PATENTSVIEW_API_KEY or TAVILY_API_KEY)."}


def _patentsview(query: str, max_results: int, key: str) -> Dict[str, Any]:
    params = {
        "q": json.dumps({"_text_any": {"patent_title": query}}),
        "f": json.dumps(["patent_id", "patent_title", "patent_date",
                         "assignees.assignee_organization"]),
        "o": json.dumps({"size": max(1, min(int(max_results), 25))}),
    }
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.get(PATENTSVIEW_URL, params=params, headers={"X-Api-Key": key})
        if resp.status_code != 200:
            return {"ok": False, "backend": "patentsview", "results": [],
                    "note": f"PatentsView HTTP {resp.status_code}: {resp.text[:200]}"}
        data = resp.json()
    except (httpx.HTTPError, ValueError) as e:
        return {"ok": False, "backend": "patentsview", "results": [],
                "note": f"PatentsView request failed: {e}"}

    results = [
        {
            "patent_id": p.get("patent_id"),
            "title": p.get("patent_title"),
            "date": p.get("patent_date"),
            "assignees": [a.get("assignee_organization") for a in p.get("assignees", [])
                          if a.get("assignee_organization")],
            "url": f"https://patents.google.com/patent/US{p.get('patent_id')}",
        }
        for p in data.get("patents", []) or []
    ]
    return {"ok": True, "backend": "patentsview", "results": results,
            "note": f"{len(results)} USPTO record(s) matched the title text."}


def patent_freedom_report(hypothesis: str, topic: str = "", max_results: int = 5) -> Dict[str, Any]:
    """Screen a hypothesis/topic for potentially-overlapping patents.

    Returns {"ok", "verdict": "no_hits"|"potential_overlap"|"insufficient_data",
             "backend", "hits", "disclaimer", "note"}.
    """
    query = (hypothesis or topic or "").strip()
    if not query:
        return {"ok": False, "verdict": "insufficient_data", "backend": "none", "hits": [],
                "disclaimer": DISCLAIMER, "note": "Nothing to screen."}

    r = search_patents(query[:200], max_results)
    if not r["ok"]:
        return {"ok": True, "verdict": "insufficient_data", "backend": r["backend"],
                "hits": [], "disclaimer": DISCLAIMER, "note": r["note"]}

    hits = r["results"]
    verdict = "potential_overlap" if hits else "no_hits"
    note = (
        f"{len(hits)} potentially related record(s) found via {r['backend']} - review with "
        "counsel before commercialization." if hits else
        f"No related records found via {r['backend']} - still not proof of freedom to operate."
    )
    return {"ok": True, "verdict": verdict, "backend": r["backend"], "hits": hits,
            "disclaimer": DISCLAIMER, "note": note}
