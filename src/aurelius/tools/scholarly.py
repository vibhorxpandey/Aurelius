"""Citation verification against real scholarly indexes (OpenAlex, Crossref), with a
Tavily web-search fallback for works not indexed there.

This is the authoritative replacement for the old naive Tavily-only `verify_citation`
that used to live in `search.py`: instead of treating "a webpage mentioned it" as
verification, this module confirms a citation against actual bibliographic databases,
recovers its real DOI/authors/venue, and — critically — surfaces retraction status.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

import httpx

from ..config import get_contact_email
from .search import web_search

OPENALEX_URL = "https://api.openalex.org/works"
CROSSREF_URL = "https://api.crossref.org/works"

MATCH_SCORE_HIGH = 0.75
MATCH_SCORE_ACCEPT = 0.50

_STOPWORDS = {"a", "an", "the", "of", "in", "on", "for", "and", "to", "is", "its", "its", "&"}
_TITLE_PREFIX_RE = re.compile(r"^[^()]{0,120}\(\d{4}[a-z]?\)\.?\s*")


def looks_like_citation(text: str) -> bool:
    """True if `text` looks like a formal citation (has a year + one of '(', 'et al', ',').

    Centralizes the heuristic previously inlined in autonomous/pipeline.py's evidence
    gathering step, unchanged, so existing behavior does not shift.
    """
    return any(ch.isdigit() for ch in text) and ("(" in text or "et al" in text.lower() or "," in text)


def _normalize_tokens(text: str) -> set:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {w for w in words if w not in _STOPWORDS}


def title_similarity(a: str, b: str) -> float:
    """Jaccard token overlap in [0.0, 1.0] between two titles. No NLP dependencies."""
    ta, tb = _normalize_tokens(a), _normalize_tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def extract_title_guess(citation: str) -> str:
    """Best-effort strip of a leading 'Author, A. B. (YYYY).' prefix to recover the title.

    Falls back to the original (trimmed) string if there's no such prefix, or if
    stripping it would leave too little text to search on.
    """
    stripped = _TITLE_PREFIX_RE.sub("", citation, count=1).strip()
    if len(stripped) >= 8:
        return stripped.rstrip(". ")
    return citation.strip().rstrip(". ")


def _normalize_doi(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    doi = raw.strip()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if doi.lower().startswith(prefix):
            doi = doi[len(prefix):]
            break
    return doi or None


def _sanitize_for_openalex_filter(text: str) -> str:
    """Strip characters that are syntactically special in OpenAlex's `filter=` mini-language.

    OpenAlex's filter DSL uses ',' to separate multiple filters and ':' to separate a
    filter's key from its value — even INSIDE a single filter's search text, an
    unescaped comma is rejected outright (HTTP 400) rather than treated as literal.
    Percent-encoding doesn't help (OpenAlex decodes before parsing the delimiter), and
    double-encoding avoids the error but breaks matching (it's searched as literal
    "%2C" text). Since title.search does tokenized matching, replacing these with
    spaces is safe and doesn't hurt relevance.
    """
    return text.replace(",", " ").replace(":", " ")


def _openalex_search(title_guess: str, max_results: int = 5) -> Dict[str, Any]:
    """Search OpenAlex by title. Returns {"ok": bool, "candidates": [...], "error": str|None}."""
    safe_title = _sanitize_for_openalex_filter(title_guess)
    params = {
        "filter": f"title.search:{safe_title}",
        "per-page": max_results,
        "select": "id,display_name,doi,publication_year,authorships,primary_location,"
                  "cited_by_count,is_retracted,open_access",
    }
    try:
        with httpx.Client(timeout=20.0) as client:
            resp = client.get(OPENALEX_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as e:
        return {"ok": False, "candidates": [], "error": f"OpenAlex HTTP {e.response.status_code}: {e.response.text[:200]}"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "candidates": [], "error": f"{type(e).__name__}: {e}"}

    candidates = []
    for w in data.get("results", []):
        loc = w.get("primary_location") or {}
        src = loc.get("source") or {}
        oa = w.get("open_access") or {}
        candidates.append({
            "title": w.get("display_name") or "",
            "doi": _normalize_doi(w.get("doi")),
            "year": w.get("publication_year"),
            "authors": [a["author"]["display_name"] for a in w.get("authorships", []) if a.get("author")],
            "venue": src.get("display_name"),
            "cited_by_count": w.get("cited_by_count"),
            "is_oa": oa.get("is_oa"),
            "oa_url": oa.get("oa_url"),
            "is_retracted": bool(w.get("is_retracted", False)),
            "source": "openalex",
        })
    return {"ok": True, "candidates": candidates, "error": None}


def _crossref_search(title_guess: str, max_results: int = 5) -> Dict[str, Any]:
    """Search Crossref by bibliographic text. Returns {"ok": bool, "candidates": [...], "error": str|None}."""
    params = {
        "query.bibliographic": title_guess,
        "rows": max_results,
        "select": "DOI,title,author,published,container-title,is-referenced-by-count,type,update-to",
    }
    email = get_contact_email()
    if email:
        params["mailto"] = email
    try:
        with httpx.Client(timeout=20.0) as client:
            resp = client.get(CROSSREF_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as e:
        return {"ok": False, "candidates": [], "error": f"Crossref HTTP {e.response.status_code}: {e.response.text[:200]}"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "candidates": [], "error": f"{type(e).__name__}: {e}"}

    candidates = []
    for item in data.get("message", {}).get("items", []):
        titles = item.get("title") or []
        authors = []
        for a in item.get("author", []) or []:
            name = " ".join(p for p in [a.get("given"), a.get("family")] if p)
            if name:
                authors.append(name)
        published = item.get("published") or item.get("issued") or {}
        date_parts = (published.get("date-parts") or [[None]])[0]
        year = date_parts[0] if date_parts else None
        venues = item.get("container-title") or []
        is_retracted = any((u.get("type") or "").lower() == "retraction" for u in item.get("update-to", []) or [])
        candidates.append({
            "title": titles[0] if titles else "",
            "doi": _normalize_doi(item.get("DOI")),
            "year": year,
            "authors": authors,
            "venue": venues[0] if venues else None,
            "cited_by_count": item.get("is-referenced-by-count"),
            "is_oa": None,
            "oa_url": None,
            "is_retracted": is_retracted,
            "source": "crossref",
        })
    return {"ok": True, "candidates": candidates, "error": None}


_RETRACTION_TIE_TOLERANCE = 0.1


def _best_match(candidates: List[Dict[str, Any]], title_guess: str) -> Optional[Dict[str, Any]]:
    """Pick the candidate that best represents the cited work.

    A scholarly index frequently returns several records for the same underlying paper
    (the original, a retraction notice, reprints, duplicate entries) that can tie or
    near-tie on title similarity. If any well-matched candidate is retracted, it MUST
    win over a coincidentally "cleaner" duplicate — silently picking the non-retracted
    twin would defeat the entire point of retraction-aware verification.
    """
    scored = [
        (title_similarity(title_guess, c.get("title", "")), c)
        for c in candidates
    ]
    scored = [(s, c) for s, c in scored if s >= MATCH_SCORE_ACCEPT]
    if not scored:
        return None

    best_score = max(s for s, _ in scored)
    retracted = [(s, c) for s, c in scored if c.get("is_retracted") and s >= best_score - _RETRACTION_TIE_TOLERANCE]
    pool = retracted if retracted else scored
    score, candidate = max(pool, key=lambda pair: pair[0])

    result = dict(candidate)
    result["match_score"] = score
    return result


def _to_matched_work(match: Dict[str, Any]) -> Dict[str, Any]:
    doi = match.get("doi")
    return {
        "title": match.get("title"),
        "doi": doi,
        "doi_url": f"https://doi.org/{doi}" if doi else None,
        "year": match.get("year"),
        "authors": match.get("authors") or [],
        "venue": match.get("venue"),
        "cited_by_count": match.get("cited_by_count"),
        "is_oa": match.get("is_oa"),
        "oa_url": match.get("oa_url"),
    }


def verify_citation(citation: str, max_results: int = 5) -> Dict[str, Any]:
    """Verify an academic citation against OpenAlex and Crossref (falls back to a Tavily
    web search if the work isn't indexed there). Drop-in replacement for the old
    search.py-based verify_citation — same signature.

    Returns {"ok": True, "citation": str, "verdict": "verified"|"retracted"|"unverified"|
    "not_found", "matched_work": {...}|None, "is_retracted": bool, "confidence":
    "high"|"medium"|"low", "match_score": float|None, "source": "openalex"|"crossref"|
    "web_fallback", "notes": str}
    """
    title_guess = extract_title_guess(citation)

    oa = _openalex_search(title_guess, max_results)
    match = _best_match(oa["candidates"], title_guess) if oa["ok"] else None
    source = "openalex"

    if match is not None and match["match_score"] < MATCH_SCORE_HIGH:
        # Medium-confidence OpenAlex match: try Crossref for DOI corroboration.
        cr = _crossref_search(title_guess, max_results)
        if cr["ok"]:
            cr_match = _best_match(cr["candidates"], title_guess)
            if cr_match and cr_match.get("doi") and cr_match["doi"] == match.get("doi"):
                match["match_score"] = max(match["match_score"], MATCH_SCORE_HIGH)

    if match is None:
        cr = _crossref_search(title_guess, max_results)
        match = _best_match(cr["candidates"], title_guess) if cr["ok"] else None
        source = "crossref"

    if match is not None:
        is_retracted = bool(match.get("is_retracted", False))
        confidence = "high" if match["match_score"] >= MATCH_SCORE_HIGH else "medium"
        verdict = "retracted" if is_retracted else "verified"
        return {
            "ok": True,
            "citation": citation,
            "verdict": verdict,
            "matched_work": _to_matched_work(match),
            "is_retracted": is_retracted,
            "confidence": confidence,
            "match_score": match["match_score"],
            "source": source,
            "notes": (
                f"Retracted work — flagged by {source}. Do not cite." if is_retracted
                else f"Matched via {source} (title similarity {match['match_score']:.2f})."
            ),
        }

    # Neither scholarly index has a confident match — fall back to web search.
    fallback = web_search(title_guess, max_results=max_results, academic_only=True)
    if fallback.get("ok") and any((r.get("score") or 0) >= 0.5 for r in fallback.get("results", [])):
        return {
            "ok": True,
            "citation": citation,
            "verdict": "unverified",
            "matched_work": None,
            "is_retracted": False,
            "confidence": "low",
            "match_score": None,
            "source": "web_fallback",
            "notes": "No confident record in OpenAlex or Crossref. Web evidence suggests "
                     "something matching may exist — verify manually before citing.",
        }
    return {
        "ok": True,
        "citation": citation,
        "verdict": "not_found",
        "matched_work": None,
        "is_retracted": False,
        "confidence": "low",
        "match_score": None,
        "source": "web_fallback",
        "notes": "No record found in OpenAlex, Crossref, or general web search. Treat as "
                 "unverifiable and remove or replace this citation.",
    }
