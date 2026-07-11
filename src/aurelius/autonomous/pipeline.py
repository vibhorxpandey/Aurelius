"""Autonomous research pipeline: screen -> draft -> fact-check -> revise.

Mirrors the host-driven workflow but drives its own LLM so it can run unattended (CLI
or as the `autonomous_research` MCP tool). Requires an LLM API key with quota.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from ..tools.drafting import save_draft, save_report
from ..tools.screening import get_research_policy
from ..tools.scholarly import looks_like_citation, verify_citation
from ..tools.search import web_search
from .llm import complete

_SCREEN_SYSTEM = (
    "You are the Principal Investigator of an evidence-based research lab. You only admit topics "
    "whose claims can be grounded in empirical, quantitative, web-verifiable evidence."
)

_WRITER_SYSTEM = (
    "You are a rigorous academic writer. You produce well-structured papers and never invent data "
    "or citations, because every claim you make is independently fact-checked against the web."
)

_CHECKER_SYSTEM = (
    "You are a ruthless fact-checker. You extract every citation and factual claim and decide, from "
    "the provided web evidence, whether each is substantiated. You never assume; you rely only on evidence."
)


def _screen(topic: str, model: str, provider, api_key) -> Dict[str, Any]:
    policy = get_research_policy()
    prompt = (
        f"Evaluate this topic for admission:\n\nTOPIC: \"{topic}\"\n\n"
        f"POLICY:\n{json.dumps(policy, indent=2)}\n\n"
        'Respond with ONLY JSON: {"approved": true/false, "domain": "<domain>", "reason": "<one sentence>"}'
    )
    raw = complete(_SCREEN_SYSTEM, prompt, model, provider, api_key, temperature=0.0, max_tokens=300)
    try:
        start, end = raw.find("{"), raw.rfind("}")
        data = json.loads(raw[start : end + 1])
        return {
            "approved": bool(data.get("approved", False)),
            "domain": str(data.get("domain", "unknown")),
            "reason": str(data.get("reason", "")),
        }
    except (ValueError, KeyError):
        return {"approved": False, "domain": "unknown", "reason": f"Could not parse screening verdict: {raw[:150]}"}


def _draft(topic: str, model, provider, api_key, report: Optional[str]) -> str:
    if report:
        prompt = (
            f'A fact-checker reviewed your draft on "{topic}" and returned the report below. Revise the '
            "draft to fix every flagged issue: remove or replace any unverifiable citation or claim.\n\n"
            f"=== REPORT ===\n{report}\n=== END REPORT ===\n\n"
            "Return ONLY the corrected, complete Markdown draft."
        )
    else:
        prompt = (
            f"Write a rigorous academic research draft on:\n\nTOPIC: {topic}\n\n"
            "Use sections: Abstract, Introduction, Methods, Results, Discussion, Conclusion, References. "
            "Include at least two REAL, verifiable academic citations. Do not invent data. "
            "Return ONLY the Markdown draft."
        )
    return complete(_WRITER_SYSTEM, prompt, model, provider, api_key, temperature=0.4, max_tokens=4096)


def _gather_evidence(draft: str, model, provider, api_key) -> str:
    """Ask the model to list the claims/citations to check, then search each."""
    prompt = (
        "From the draft below, list up to 8 items to fact-check: every citation and the most "
        "load-bearing factual/statistical claims. Return ONLY a JSON array of short search strings.\n\n"
        f"=== DRAFT ===\n{draft}\n=== END DRAFT ==="
    )
    raw = complete(_CHECKER_SYSTEM, prompt, model, provider, api_key, temperature=0.0, max_tokens=600)
    queries: List[str] = []
    try:
        start, end = raw.find("["), raw.rfind("]")
        queries = [str(q) for q in json.loads(raw[start : end + 1])][:8]
    except (ValueError, KeyError):
        queries = []

    evidence_blocks = []
    for q in queries:
        res = verify_citation(q) if looks_like_citation(q) else web_search(q, max_results=3, academic_only=False)
        evidence_blocks.append(f"### Query: {q}\n{json.dumps(res)[:1500]}")
    return "\n\n".join(evidence_blocks) if evidence_blocks else "(no queries extracted)"


def _check(draft: str, evidence: str, model, provider, api_key) -> str:
    prompt = (
        "Fact-check the draft using ONLY the web evidence provided. For each citation and key claim, give "
        "a verdict.\n\n"
        f"=== DRAFT ===\n{draft}\n=== END DRAFT ===\n\n"
        f"=== WEB EVIDENCE ===\n{evidence}\n=== END EVIDENCE ===\n\n"
        "Return a report whose FIRST line is exactly 'STATUS: VERIFIED' (if every citation and key claim is "
        "substantiated) or 'STATUS: REJECTED' (if any is not), followed by an itemized list with your verdict "
        "and, if REJECTED, exactly what the writer must remove or replace."
    )
    return complete(_CHECKER_SYSTEM, prompt, model, provider, api_key, temperature=0.0, max_tokens=2048)


def _is_verified(report: str) -> bool:
    for line in report.splitlines():
        s = line.strip().upper()
        if not s:
            continue
        return "VERIFIED" in s and "REJECT" not in s
    return False


def run_autonomous_research(
    topic: str,
    model: str = "gpt-4o-mini-2024-07-18",
    provider: Optional[str] = None,
    api_key: Optional[str] = None,
    max_rounds: int = 2,
    save: bool = True,
) -> Dict[str, Any]:
    """Run the full autonomous research loop and return the result.

    Returns a dict: {approved, reason, verified, rounds, draft, report, files}.
    """
    verdict = _screen(topic, model, provider, api_key)
    if not verdict["approved"]:
        return {
            "approved": False,
            "reason": f"Rejected ({verdict['domain']}): {verdict['reason']}",
            "verified": False,
            "rounds": 0,
            "draft": None,
            "report": None,
            "files": {},
        }

    draft = ""
    report = ""
    verified = False
    rounds_done = 0
    for rnd in range(1, max(1, int(max_rounds)) + 1):
        rounds_done = rnd
        draft = _draft(topic, model, provider, api_key, report or None)
        evidence = _gather_evidence(draft, model, provider, api_key)
        report = _check(draft, evidence, model, provider, api_key)
        verified = _is_verified(report)
        if verified:
            break

    files: Dict[str, str] = {}
    if save:
        files["draft"] = save_draft(draft)["path"]
        files["report"] = save_report(report)["path"]

    return {
        "approved": True,
        "reason": f"Accepted ({verdict['domain']}): {verdict['reason']}",
        "verified": verified,
        "rounds": rounds_done,
        "draft": draft,
        "report": report,
        "files": files,
    }
