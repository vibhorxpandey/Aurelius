"""Drafting helpers: a standard academic outline, long-form length planning, and
artifact persistence."""
from __future__ import annotations

from typing import Any, Dict, Optional

from ..config import resolve_output_path

ACADEMIC_OUTLINE = """# {title}

## Abstract
<150-250 words: aim, method, key findings, implications.>

## Introduction
<Context and motivation; the gap; the research question; what this work does.>

## Methods
<Data sources and analytical techniques; enough detail to be reproducible.>

## Results
<Findings with concrete, verifiable evidence (numbers, effect sizes, citations).>

## Discussion
<Interpretation; comparison to prior work; implications.>

### Limitations
<Honest constraints on the findings.>

## Conclusion
<What was shown; why it matters; future directions.>

## References
<Real, verifiable citations only. Every one will be checked.>
"""


def draft_outline(topic: str) -> Dict[str, str]:
    """Return a standard academic outline scaffold for a topic (no LLM call).

    Args:
        topic: The research topic; used as the working title.
    """
    return {"topic": topic, "outline": ACADEMIC_OUTLINE.format(title=topic)}


WORDS_PER_PAGE_DEFAULT = 525  # ~500-550 words/page: double-spaced, 12pt, 1in margins

# (section name, share of total word budget) -- sums to 1.00. References gets a
# non-trivial share because long papers cite a lot, but it's a citation list, not
# prose, so treat its "word count" as approximate.
SECTION_PROPORTIONS = [
    ("Abstract", 0.02),
    ("Introduction", 0.12),
    ("Methods", 0.15),
    ("Results", 0.25),
    ("Discussion", 0.22),
    ("Limitations", 0.05),
    ("Conclusion", 0.08),
    ("References", 0.11),
]


def plan_paper_length(
    target_pages: Optional[int] = None,
    target_pages_min: Optional[int] = None,
    target_pages_max: Optional[int] = None,
    words_per_page: int = WORDS_PER_PAGE_DEFAULT,
) -> Dict[str, Any]:
    """Compute a section-by-section word-count budget for a target page count.

    For long-form papers (e.g. 20-80 pages): call this first, then draft section by
    section, verifying each section's citations before appending it via
    save_draft(..., append=True). No LLM call is made here — it's pure arithmetic.

    Args:
        target_pages: A single target page count; a +/-10% band is derived automatically.
            Provide this OR target_pages_min/target_pages_max, not both.
        target_pages_min: Explicit lower bound on pages (used with target_pages_max).
        target_pages_max: Explicit upper bound on pages.
        words_per_page: Override the ~525 words/page assumption if your target format
            differs (e.g. single-spaced, different font/margins).

    Returns {"ok": bool, "target_pages": {"min","max"}, "words_per_page": int,
             "total_words": {"min","max"}, "sections": [{"name","proportion","words":
             {"min","max"}}, ...], "notes": str, "error": str|None}
    """
    if target_pages is None and (target_pages_min is None or target_pages_max is None):
        return {
            "ok": False,
            "target_pages": None,
            "words_per_page": words_per_page,
            "total_words": None,
            "sections": [],
            "notes": "",
            "error": "Provide either target_pages, or both target_pages_min and target_pages_max.",
        }

    if target_pages is not None:
        pmin = max(1, round(target_pages * 0.9))
        pmax = round(target_pages * 1.1)
    else:
        pmin, pmax = int(target_pages_min), int(target_pages_max)

    if pmin < 1 or pmax < pmin or pmax > 300:
        return {
            "ok": False,
            "target_pages": None,
            "words_per_page": words_per_page,
            "total_words": None,
            "sections": [],
            "notes": "",
            "error": f"Invalid page range [{pmin}, {pmax}]. Must satisfy 1 <= min <= max <= 300.",
        }

    total_min = pmin * words_per_page
    total_max = pmax * words_per_page

    sections = [
        {
            "name": name,
            "proportion": prop,
            "words": {"min": round(total_min * prop), "max": round(total_max * prop)},
        }
        for name, prop in SECTION_PROPORTIONS
    ]

    notes = (
        "References' word budget is approximate -- it's a citation list, not prose; "
        "don't force it to hit the target exactly. For totals over ~15,000 words, draft "
        "and verify section by section, appending each with save_draft(content, filename, "
        "append=True) rather than sending the whole accumulated draft in one call."
    )

    return {
        "ok": True,
        "target_pages": {"min": pmin, "max": pmax},
        "words_per_page": words_per_page,
        "total_words": {"min": total_min, "max": total_max},
        "sections": sections,
        "notes": notes,
        "error": None,
    }


def save_draft(content: str, filename: str = "draft.md", append: bool = False) -> Dict[str, Any]:
    """Save (or append to) a Markdown research draft.

    Args:
        content: The Markdown text to write. With append=True, this is just the new
            chunk (e.g. one section) -- not the whole accumulated document.
        filename: Output filename (basename saved under the Aurelius output dir).
        append: If True, append to the existing file instead of overwriting it. Use
            this for long-form papers so you never resend the whole draft each call.

    Returns {"ok": True, "path": str, "bytes": int (total file size after this write),
             "bytes_written": int (size of just this call's content), "appended": bool}.
    """
    path = resolve_output_path(filename)
    with path.open("a" if append else "w", encoding="utf-8") as f:
        f.write(content)
    return {
        "ok": True,
        "path": str(path),
        "bytes": path.stat().st_size,
        "bytes_written": len(content.encode("utf-8")),
        "appended": append,
    }


def save_report(content: str, filename: str = "verification.md") -> Dict[str, Any]:
    """Save a fact-checking / verification report to disk.

    The report should begin with a single line that is exactly 'STATUS: VERIFIED' or
    'STATUS: REJECTED', followed by an itemized list of checked claims and verdicts.

    Args:
        content: The full Markdown text of the report.
        filename: Output filename (basename saved under the Aurelius output dir).
    """
    path = resolve_output_path(filename)
    path.write_text(content, encoding="utf-8")
    status = "UNKNOWN"
    for line in content.splitlines():
        s = line.strip().upper()
        if not s:
            continue
        if "VERIFIED" in s and "REJECT" not in s:
            status = "VERIFIED"
        elif "REJECT" in s:
            status = "REJECTED"
        break
    return {"ok": True, "path": str(path), "status": status, "bytes": len(content.encode("utf-8"))}
