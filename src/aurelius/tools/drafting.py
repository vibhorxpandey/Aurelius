"""Drafting helpers: a standard academic outline plus artifact persistence."""
from __future__ import annotations

from typing import Any, Dict

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


def save_draft(content: str, filename: str = "draft.md") -> Dict[str, Any]:
    """Save a Markdown research draft to disk.

    Args:
        content: The full Markdown text of the draft.
        filename: Output filename (basename saved under the Aurelius output dir).

    Returns the absolute path written.
    """
    path = resolve_output_path(filename)
    path.write_text(content, encoding="utf-8")
    return {"ok": True, "path": str(path), "bytes": len(content.encode("utf-8"))}


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
    return {"ok": True, "path": str(path), "status": status}
