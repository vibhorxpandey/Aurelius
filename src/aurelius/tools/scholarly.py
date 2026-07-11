"""Citation verification against real scholarly indexes, with author/year corroboration.

Order of precision:
  1. If the citation carries a DOI, look it up directly (OpenAlex -> Crossref) — exact.
  2. Otherwise title-search across OpenAlex -> Crossref -> arXiv -> Semantic Scholar.
  3. Fall back to a Tavily academic web search for works none of them index.

A title match alone is NOT treated as verification: the cited first-author surname and
year are corroborated against the matched record, so a same-titled paper by different
authors (the classic Okun-1962 vs. a 1979 reprint case) is honestly flagged, not passed.
Retraction status (OpenAlex / Crossref) is surfaced as an impossible-to-miss top-level flag.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional

import httpx

from ..config import get_contact_email, get_semantic_scholar_key
from .search import web_search

OPENALEX_URL = "https://api.openalex.org/works"
CROSSREF_URL = "https://api.crossref.org/works"
ARXIV_URL = "https://export.arxiv.org/api/query"
SEMANTIC_SCHOLAR_URL = "https://api.semanticscholar.org/graph/v1/paper/search"

MATCH_SCORE_HIGH = 0.75
MATCH_SCORE_ACCEPT = 0.50
_RETRACTION_TIE_TOLERANCE = 0.1

_STOPWORDS = {"a", "an", "the", "of", "in", "on", "for", "and", "to", "is", "its", "&"}
_TITLE_PREFIX_RE = re.compile(r"^[^()]{0,120}\(\d{4}[a-z]?\)\.?\s*")
_DOI_RE = re.compile(r"10\.\d{4,9}/[-._;()/:a-zA-Z0-9]+")
_ARXIV_RE = re.compile(r"arxiv:\s*(\d{4}\.\d{4,5})", re.IGNORECASE)
_ARXIV_BARE_RE = re.compile(r"\b(\d{4}\.\d{4,5})(?:v\d+)?\b")
_YEAR_PAREN_RE = re.compile(r"\((\d{4})[a-z]?\)")
_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")

_ATOM = {"a": "http://www.w3.org/2005/Atom"}
_ARXIV_DOI_TAG = "{http://arxiv.org/schemas/atom}doi"


# --------------------------------------------------------------------------- #
# Parsing helpers
# --------------------------------------------------------------------------- #
def looks_like_citation(text: str) -> bool:
    """True if `text` looks like a formal citation (a year/number + one of '(', 'et al', ',')."""
    return any(ch.isdigit() for ch in text) and ("(" in text or "et al" in text.lower() or "," in text)


def _normalize_tokens(text: str) -> set:
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in _STOPWORDS}


def title_similarity(a: str, b: str) -> float:
    """Jaccard token overlap in [0.0, 1.0] between two titles. No NLP dependencies."""
    ta, tb = _normalize_tokens(a), _normalize_tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def extract_title_guess(citation: str) -> str:
    """Recover the title by stripping a leading 'Author, A. B. (YYYY).' prefix."""
    stripped = _TITLE_PREFIX_RE.sub("", citation, count=1).strip()
    if len(stripped) >= 8:
        return stripped.rstrip(". ")
    return citation.strip().rstrip(". ")


def extract_doi(citation: str) -> Optional[str]:
    """Pull a DOI out of a citation string, if present."""
    m = _DOI_RE.search(citation)
    if not m:
        return None
    return m.group(0).rstrip(".,);")


def extract_arxiv_id(citation: str) -> Optional[str]:
    """Pull an arXiv id (new-style NNNN.NNNNN) out of a citation string, if present."""
    m = _ARXIV_RE.search(citation)
    if m:
        return m.group(1)
    m = _ARXIV_BARE_RE.search(citation)
    return m.group(1) if m else None


def extract_first_author_surname(citation: str) -> Optional[str]:
    """Best-effort first-author surname: handles 'Okun, A. M. (1962)' and 'A. M. Okun (1962)'."""
    head = re.split(r"\(\d{4}", citation)[0].strip().rstrip(",")
    if not head:
        return None
    surname = head.split(",")[0].strip() if "," in head else (head.split()[-1] if head.split() else "")
    surname = re.sub(r"[^A-Za-z\-]", "", surname)
    return surname or None


def extract_year(citation: str) -> Optional[int]:
    """Best-effort publication year (prefers a parenthesized year)."""
    m = _YEAR_PAREN_RE.search(citation)
    if m:
        return int(m.group(1))
    m = _YEAR_RE.search(citation)
    return int(m.group(0)) if m else None


def _author_surnames(names: List[str]) -> set:
    """Lowercased surnames (last whitespace token) of 'First Last' author strings."""
    out = set()
    for n in names or []:
        toks = re.sub(r"[^A-Za-z\-\s]", "", n).split()
        if toks:
            out.add(toks[-1].lower())
    return out


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
    """Strip characters OpenAlex's filter= DSL chokes on. ',' and ':' are delimiters
    (HTTP 400 if literal); '?' and '*' are treated as wildcards on the stemmed
    title.search field (also HTTP 400). title.search is tokenized, so dropping this
    punctuation is safe and doesn't hurt matching."""
    return re.sub(r'[,:?*"()]', " ", text)


# --------------------------------------------------------------------------- #
# Source fetchers -> normalized candidate dicts
# --------------------------------------------------------------------------- #
def _normalize_openalex_work(w: Dict[str, Any]) -> Dict[str, Any]:
    loc = w.get("primary_location") or {}
    src = loc.get("source") or {}
    oa = w.get("open_access") or {}
    return {
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
    }


_OPENALEX_SELECT = ("id,display_name,doi,publication_year,authorships,primary_location,"
                    "cited_by_count,is_retracted,open_access")


def _openalex_search(title_guess: str, max_results: int = 5) -> Dict[str, Any]:
    params = {"filter": f"title.search:{_sanitize_for_openalex_filter(title_guess)}",
              "per-page": max_results, "select": _OPENALEX_SELECT}
    try:
        with httpx.Client(timeout=20.0) as client:
            resp = client.get(OPENALEX_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as e:
        return {"ok": False, "candidates": [], "error": f"OpenAlex HTTP {e.response.status_code}: {e.response.text[:200]}"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "candidates": [], "error": f"{type(e).__name__}: {e}"}
    return {"ok": True, "candidates": [_normalize_openalex_work(w) for w in data.get("results", [])], "error": None}


def _openalex_by_doi(doi: str) -> Optional[Dict[str, Any]]:
    try:
        with httpx.Client(timeout=20.0) as client:
            resp = client.get(f"{OPENALEX_URL}/https://doi.org/{doi}", params={"select": _OPENALEX_SELECT})
            if resp.status_code != 200:
                return None
            return _normalize_openalex_work(resp.json())
    except Exception:  # noqa: BLE001
        return None


def _normalize_crossref_item(item: Dict[str, Any]) -> Dict[str, Any]:
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
    return {
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
    }


_CROSSREF_SELECT = "DOI,title,author,published,container-title,is-referenced-by-count,type,update-to"


def _crossref_search(title_guess: str, max_results: int = 5) -> Dict[str, Any]:
    params = {"query.bibliographic": title_guess, "rows": max_results, "select": _CROSSREF_SELECT}
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
    items = data.get("message", {}).get("items", [])
    return {"ok": True, "candidates": [_normalize_crossref_item(it) for it in items], "error": None}


def _crossref_by_doi(doi: str) -> Optional[Dict[str, Any]]:
    try:
        with httpx.Client(timeout=20.0) as client:
            resp = client.get(f"{CROSSREF_URL}/{doi}")
            if resp.status_code != 200:
                return None
            return _normalize_crossref_item(resp.json().get("message", {}))
    except Exception:  # noqa: BLE001
        return None


def _parse_arxiv_entry(e: ET.Element) -> Optional[Dict[str, Any]]:
    title_el = e.find("a:title", _ATOM)
    title = " ".join((title_el.text or "").split()) if title_el is not None else ""
    if not title or title.lower() == "error":
        return None
    authors = [a.find("a:name", _ATOM).text for a in e.findall("a:author", _ATOM)
               if a.find("a:name", _ATOM) is not None]
    pub_el = e.find("a:published", _ATOM)
    year = int(pub_el.text[:4]) if pub_el is not None and pub_el.text else None
    id_el = e.find("a:id", _ATOM)
    abs_url = id_el.text if id_el is not None else None
    doi_el = e.find(_ARXIV_DOI_TAG)
    return {
        "title": title,
        "doi": _normalize_doi(doi_el.text) if doi_el is not None else None,
        "year": year,
        "authors": authors,
        "venue": "arXiv (preprint)",
        "cited_by_count": None,
        "is_oa": True,
        "oa_url": abs_url,
        "is_retracted": False,
        "source": "arxiv",
    }


def _arxiv_search(title_guess: str, max_results: int = 5) -> Dict[str, Any]:
    """Search arXiv (preprints/working papers OpenAlex/Crossref often miss)."""
    clean = title_guess.replace('"', " ").strip()
    params = {"search_query": f'ti:"{clean}"', "max_results": max_results}
    try:
        with httpx.Client(timeout=25.0, follow_redirects=True) as client:
            resp = client.get(ARXIV_URL, params=params)
            resp.raise_for_status()
            root = ET.fromstring(resp.text)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "candidates": [], "error": f"{type(e).__name__}: {e}"}
    candidates = [c for c in (_parse_arxiv_entry(e) for e in root.findall("a:entry", _ATOM)) if c]
    return {"ok": True, "candidates": candidates, "error": None}


def _arxiv_by_id(arxiv_id: str) -> Optional[Dict[str, Any]]:
    """Direct arXiv lookup by id — exact identifier, no title matching needed."""
    try:
        with httpx.Client(timeout=25.0, follow_redirects=True) as client:
            resp = client.get(ARXIV_URL, params={"id_list": arxiv_id, "max_results": 1})
            resp.raise_for_status()
            root = ET.fromstring(resp.text)
    except Exception:  # noqa: BLE001
        return None
    e = root.find("a:entry", _ATOM)
    return _parse_arxiv_entry(e) if e is not None else None


def _semantic_scholar_search(title_guess: str, max_results: int = 5) -> Dict[str, Any]:
    """Search Semantic Scholar (broad coverage incl. preprints + citation counts)."""
    params = {"query": title_guess, "limit": max_results,
              "fields": "title,year,authors,externalIds,citationCount,openAccessPdf,publicationVenue"}
    headers = {}
    key = get_semantic_scholar_key()
    if key:
        headers["x-api-key"] = key
    try:
        with httpx.Client(timeout=25.0) as client:
            resp = client.get(SEMANTIC_SCHOLAR_URL, params=params, headers=headers)
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "candidates": [], "error": f"{type(e).__name__}: {e}"}
    candidates = []
    for p in data.get("data", []) or []:
        ext = p.get("externalIds") or {}
        oa = p.get("openAccessPdf") or {}
        venue = (p.get("publicationVenue") or {}).get("name") if p.get("publicationVenue") else None
        candidates.append({
            "title": p.get("title") or "",
            "doi": _normalize_doi(ext.get("DOI")),
            "year": p.get("year"),
            "authors": [a.get("name") for a in p.get("authors", []) if a.get("name")],
            "venue": venue,
            "cited_by_count": p.get("citationCount"),
            "is_oa": bool(oa.get("url")),
            "oa_url": oa.get("url"),
            "is_retracted": False,
            "source": "semantic_scholar",
        })
    return {"ok": True, "candidates": candidates, "error": None}


# --------------------------------------------------------------------------- #
# Matching + formatting
# --------------------------------------------------------------------------- #
def _best_match(candidates: List[Dict[str, Any]], title_guess: str) -> Optional[Dict[str, Any]]:
    """Best candidate by title similarity, but a retracted near-tie wins over a clean twin."""
    scored = [(title_similarity(title_guess, c.get("title", "")), c) for c in candidates]
    scored = [(s, c) for s, c in scored if s >= MATCH_SCORE_ACCEPT]
    if not scored:
        return None
    best_score = max(s for s, _ in scored)
    retracted = [(s, c) for s, c in scored if c.get("is_retracted") and s >= best_score - _RETRACTION_TIE_TOLERANCE]
    score, candidate = max(retracted or scored, key=lambda pair: pair[0])
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


def _format_authors(authors: List[str]) -> str:
    authors = [a for a in (authors or []) if a]
    if not authors:
        return "Unknown author"
    if len(authors) > 5:
        return ", ".join(authors[:3]) + ", et al."
    return ", ".join(authors)


def format_citation(work: Dict[str, Any]) -> str:
    """A clean, human-readable citation built from authoritative metadata."""
    parts = [_format_authors(work.get("authors"))]
    if work.get("year"):
        parts[-1] += f" ({work['year']})."
    else:
        parts[-1] += "."
    if work.get("title"):
        parts.append(f"{work['title']}.")
    if work.get("venue"):
        parts.append(f"{work['venue']}.")
    if work.get("doi"):
        parts.append(f"https://doi.org/{work['doi']}")
    return " ".join(parts)


def to_bibtex(work: Dict[str, Any]) -> str:
    """A BibTeX entry from authoritative metadata (paired with the latex_outline tool)."""
    authors = work.get("authors") or []
    first_toks = re.sub(r"[^A-Za-z\-\s]", "", authors[0]).split() if authors else []
    first = first_toks[-1].lower() if first_toks else "unknown"
    key = f"{first}{work.get('year') or ''}"
    authors_bib = " and ".join(work.get("authors") or []) or "Unknown"
    lines = [f"@article{{{key},",
             f"  author  = {{{authors_bib}}},",
             f"  title   = {{{work.get('title') or ''}}},"]
    if work.get("venue"):
        lines.append(f"  journal = {{{work['venue']}}},")
    if work.get("year"):
        lines.append(f"  year    = {{{work['year']}}},")
    if work.get("doi"):
        lines.append(f"  doi     = {{{work['doi']}}},")
    lines.append("}")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def verify_citation(citation: str, max_results: int = 5) -> Dict[str, Any]:
    """Verify an academic citation and return a rich, actionable verdict.

    Precision order: DOI direct lookup -> title search (OpenAlex, Crossref, arXiv,
    Semantic Scholar) -> web fallback. A title match is corroborated against the cited
    first-author surname and year, so a same-titled paper by different authors is flagged
    'unverified', not passed. Retraction is surfaced via a top-level `is_retracted`.

    Returns keys: ok, citation, verdict ('verified'|'retracted'|'unverified'|'not_found'),
    matched_work|None, is_retracted, confidence ('high'|'medium'|'low'), match_score,
    source, author_match, year_match, corrected_citation, bibtex, notes.
    """
    doi = extract_doi(citation)
    arxiv_id = extract_arxiv_id(citation)
    cited_surname = extract_first_author_surname(citation)
    cited_year = extract_year(citation)
    title_guess = extract_title_guess(citation)
    max_results = max(1, min(int(max_results), 10))

    match: Optional[Dict[str, Any]] = None
    source: Optional[str] = None
    exact = False

    # 1. DOI direct lookup — inherently exact.
    if doi:
        for fetch, src in ((_openalex_by_doi, "openalex"), (_crossref_by_doi, "crossref")):
            cand = fetch(doi)
            if cand and cand.get("title"):
                cand["match_score"] = 1.0
                match, source, exact = cand, src, True
                break

    # 1b. arXiv id direct lookup — exact identifier for preprints.
    if match is None and arxiv_id:
        cand = _arxiv_by_id(arxiv_id)
        if cand:
            cand["match_score"] = 1.0
            match, source, exact = cand, "arxiv", True

    # 2. Title search across sources (authoritative first, then broad coverage).
    if match is None:
        for searcher in (_openalex_search, _crossref_search, _arxiv_search, _semantic_scholar_search):
            res = searcher(title_guess, max_results)
            if res.get("ok"):
                m = _best_match(res["candidates"], title_guess)
                if m:
                    match, source = m, m.get("source")
                    break

    # 3. Web fallback — nothing in any scholarly index.
    if match is None:
        fallback = web_search(title_guess, max_results=max_results, academic_only=True)
        found = fallback.get("ok") and any((r.get("score") or 0) >= 0.5 for r in fallback.get("results", []))
        return {
            "ok": True, "citation": citation,
            "verdict": "unverified" if found else "not_found",
            "matched_work": None, "is_retracted": False, "confidence": "low",
            "match_score": None, "source": "web_fallback",
            "author_match": None, "year_match": None,
            "corrected_citation": None, "bibtex": None,
            "notes": ("No confident record in OpenAlex, Crossref, arXiv, or Semantic Scholar. "
                      "Web evidence suggests something matching may exist — verify manually."
                      if found else
                      "No record found in any scholarly index or web search. Treat as "
                      "unverifiable and remove or replace this citation."),
        }

    matched_surnames = _author_surnames(match.get("authors") or [])
    author_match = bool(cited_surname and cited_surname.lower() in matched_surnames)
    year_match = (cited_year is None or match.get("year") is None or abs(cited_year - match["year"]) <= 1)
    is_retracted = bool(match.get("is_retracted"))
    matched_work = _to_matched_work(match)
    corrected = format_citation(match)
    bibtex = to_bibtex(match)
    no_retraction_data = source in ("arxiv", "semantic_scholar")

    if is_retracted:
        verdict, confidence = "retracted", "high"
        notes = f"Retracted work — flagged by {source}. Do not cite."
    elif exact or author_match:
        verdict = "verified"
        confidence = "high" if (exact or match.get("match_score", 0) >= MATCH_SCORE_HIGH) else "medium"
        note_bits = [f"Matched via {source}" + ("" if exact else f" (title similarity {match.get('match_score', 0):.2f}, author corroborated)") + "."]
        if not year_match:
            confidence = "medium" if confidence == "high" else confidence
            note_bits.append(f"Year differs (cited {cited_year} vs found {match.get('year')}) — check you have the right edition.")
        if no_retraction_data:
            note_bits.append("Retraction status not checked (not in OpenAlex/Crossref).")
        notes = " ".join(note_bits)
    else:
        # Title matched but the authors don't — the Okun-1962-vs-Plosser-1979 case.
        verdict, confidence = "unverified", "low"
        found_names = ", ".join((match.get("authors") or [])[:3]) or "unknown"
        notes = (f"Found a work with this title but different authors (found: {found_names}; "
                 f"cited: {cited_surname or 'unknown'}) — likely not the paper you cited. "
                 "Verify manually or use the corrected_citation if it is the intended work.")

    return {
        "ok": True, "citation": citation, "verdict": verdict,
        "matched_work": matched_work, "is_retracted": is_retracted,
        "confidence": confidence, "match_score": match.get("match_score"),
        "source": source, "author_match": author_match, "year_match": year_match,
        "corrected_citation": corrected, "bibtex": bibtex, "notes": notes,
    }
