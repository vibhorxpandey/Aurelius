"""The Evidence Ledger: batch-verify a list of claims/citations into a scored,
auditable provenance record — Aurelius's signature "shows its receipts" artifact.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List

from .scholarly import looks_like_citation, verify_citation
from .search import web_search

_REF_MARKER_RE = re.compile(r"^\s*(?:\[\d+\]|\(\d+\)|\d+[.\)]|[-*•])\s+")
_HEADER_RE = re.compile(r"^\s*(references|bibliography|works cited)\s*:?\s*$", re.IGNORECASE)
_YEAR_RE = re.compile(r"(19|20)\d{2}")

DEFAULT_THRESHOLD = 1.0  # all-or-nothing by default: matches the zero-tolerance brand


def _verify_one(item: str) -> Dict[str, Any]:
    """Route one claim/citation to the right checker and normalize to a ledger entry."""
    if looks_like_citation(item):
        r = verify_citation(item)
        sources = [r["matched_work"]] if r.get("matched_work") else []
        return {
            "claim": item,
            "type": "citation",
            "verdict": r["verdict"],
            "confidence": r["confidence"],
            "sources": sources,
            "notes": r["notes"],
        }

    r = web_search(item, max_results=5, academic_only=True)
    if not r.get("ok"):
        return {
            "claim": item,
            "type": "claim",
            "verdict": "not_found",
            "confidence": "low",
            "sources": [],
            "notes": r.get("error", "Search failed."),
        }
    results = r.get("results", [])
    verified = any((res.get("score") or 0) >= 0.5 for res in results)
    verdict = "verified" if verified else ("unverified" if results else "not_found")
    sources = [{"title": res["title"], "url": res["url"], "doi": None} for res in results[:3]]
    return {
        "claim": item,
        "type": "claim",
        "verdict": verdict,
        "confidence": "medium" if verified else "low",
        "sources": sources,
        "notes": r.get("answer") or "",
    }


def verify_claims(claims: List[str], threshold: float = DEFAULT_THRESHOLD) -> Dict[str, Any]:
    """Batch-verify a list of citations and/or factual claims into a scored evidence ledger.

    Auto-detects whether each item is a citation (routed to scholarly.verify_citation,
    which is retraction-aware) or a factual/statistical claim (routed to an
    academic-domain web search). Produces a document-level verification_score and a
    ready-to-save Markdown report.

    Args:
        claims: A list of citation strings and/or factual claim strings.
        threshold: Fraction of items that must verify for the report's STATUS line to
            read VERIFIED (default 1.0 — all items must check out).

    Returns {"ok": True, "ledger": [...], "verification_score": float,
             "counts": {"verified","retracted","unverified","not_found","total"},
             "markdown": str}
    """
    ledger = [_verify_one(item) for item in claims]

    counts = {"verified": 0, "retracted": 0, "unverified": 0, "not_found": 0}
    for entry in ledger:
        verdict = entry["verdict"]
        if verdict in counts:
            counts[verdict] += 1
    counts["total"] = len(ledger)

    verification_score = (counts["verified"] / counts["total"]) if counts["total"] else 0.0
    markdown = render_ledger_markdown(ledger, counts, verification_score, threshold)

    return {
        "ok": True,
        "ledger": ledger,
        "verification_score": verification_score,
        "counts": counts,
        "markdown": markdown,
    }


def render_ledger_markdown(
    ledger: List[Dict[str, Any]],
    counts: Dict[str, int],
    verification_score: float,
    threshold: float = DEFAULT_THRESHOLD,
) -> str:
    """Render a ledger as shareable Markdown, compatible with drafting.save_report's
    'STATUS: VERIFIED' / 'STATUS: REJECTED' first-line convention.

    Retracted/unverified/not_found items are shown struck through with the reason;
    verified items are shown plainly with their source.
    """
    status = "VERIFIED" if verification_score >= threshold else "REJECTED"
    lines = [f"STATUS: {status}", ""]
    lines.append(
        f"**Verification score:** {verification_score:.0%} "
        f"({counts.get('verified', 0)}/{counts.get('total', 0)} verified)"
    )
    lines.append(
        f"Verified: {counts.get('verified', 0)} · Retracted: {counts.get('retracted', 0)} · "
        f"Unverified: {counts.get('unverified', 0)} · Not found: {counts.get('not_found', 0)}"
    )
    lines.append("")
    lines.append("## Evidence Ledger")
    lines.append("")

    # ASCII markers only (no emoji): emoji in Markdown printed through a non-UTF-8
    # console (Windows cp1252 is the default) raises UnicodeEncodeError and crashes
    # whatever is printing it. Bracket labels match the existing STATUS: line convention.
    for entry in ledger:
        claim, verdict = entry["claim"], entry["verdict"]
        if verdict == "verified":
            lines.append(f"- [VERIFIED] {claim}")
            for src in entry.get("sources", []):
                title = src.get("title", "")
                doi = src.get("doi")
                url = src.get("url")
                ref = f"https://doi.org/{doi}" if doi else url
                if title or ref:
                    lines.append(f"  - Source: {title} {f'({ref})' if ref else ''}".strip())
        else:
            label = {
                "retracted": "RETRACTED",
                "unverified": "UNVERIFIED",
                "not_found": "NOT FOUND",
            }.get(verdict, verdict.upper())
            reason = {
                "retracted": "do not cite",
                "unverified": "no confident scholarly record",
                "not_found": "not found in any source",
            }.get(verdict, verdict)
            lines.append(f"- [{label}] ~~{claim}~~ — {reason}")
            if entry.get("notes"):
                lines.append(f"  - {entry['notes']}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def split_references(text: str) -> List[str]:
    """Split a References/Bibliography block into individual citation strings.

    Handles numbered ([1], 1., (1)), bulleted (-, *), and blank-line-separated entries.
    Keeps only entries that look like real citations (contain a 4-digit year).
    """
    lines = text.strip().splitlines()
    if lines and _HEADER_RE.match(lines[0]):
        lines = lines[1:]
    body = "\n".join(lines).strip()

    entries: List[str] = []
    if any(_REF_MARKER_RE.match(l) for l in lines):
        cur: List[str] = []
        for l in lines:
            if _REF_MARKER_RE.match(l):
                if cur:
                    entries.append(" ".join(cur).strip())
                cur = [_REF_MARKER_RE.sub("", l).strip()]
            elif l.strip():
                cur.append(l.strip())
        if cur:
            entries.append(" ".join(cur).strip())
    else:
        chunks = re.split(r"\n\s*\n", body)
        if len(chunks) > 1:
            entries = [" ".join(c.split()) for c in chunks if c.strip()]
        else:
            entries = [l.strip() for l in lines if l.strip()]

    return [e for e in entries if len(e) > 15 and _YEAR_RE.search(e)]


def verify_bibliography(text: str, threshold: float = DEFAULT_THRESHOLD) -> Dict[str, Any]:
    """Verify an entire References/Bibliography block at once.

    Splits the text into individual citations, verifies each against the scholarly indexes,
    and returns a scored ledger plus two actionable artifacts: `corrected_bibtex` (a clean,
    DOI-backed BibTeX file for the entries that resolved) and `corrected_references` (the
    authoritative citation strings). The "check and clean my whole paper's sources" workflow.

    Returns {"ok": True, "count": int, "ledger": [...], "verification_score": float,
             "counts": {...}, "markdown": str, "corrected_bibtex": str,
             "corrected_references": [...]} — or {"ok": False, "error": ...} if no citations
             were found in the text.
    """
    refs = split_references(text)
    if not refs:
        return {"ok": False, "error": "No citations found. Provide a References/Bibliography "
                "block with one entry per line (numbered, bulleted, or blank-line separated)."}

    ledger: List[Dict[str, Any]] = []
    counts = {"verified": 0, "retracted": 0, "unverified": 0, "not_found": 0}
    bibtex_entries: List[str] = []
    corrected_refs: List[str] = []

    for ref in refs:
        r = verify_citation(ref)
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
        ledger.append({
            "claim": ref,
            "type": "citation",
            "verdict": r["verdict"],
            "confidence": r["confidence"],
            "sources": [r["matched_work"]] if r.get("matched_work") else [],
            "notes": r["notes"],
            "corrected_citation": r.get("corrected_citation"),
            "bibtex": r.get("bibtex"),
        })
        if r.get("bibtex") and r["verdict"] == "verified":
            bibtex_entries.append(r["bibtex"])
        if r.get("corrected_citation"):
            corrected_refs.append(r["corrected_citation"])

    counts["total"] = len(ledger)
    score = counts["verified"] / counts["total"] if counts["total"] else 0.0
    markdown = render_ledger_markdown(ledger, counts, score, threshold)

    return {
        "ok": True,
        "count": len(ledger),
        "ledger": ledger,
        "verification_score": score,
        "counts": counts,
        "markdown": markdown,
        "corrected_bibtex": "\n\n".join(bibtex_entries),
        "corrected_references": corrected_refs,
    }
