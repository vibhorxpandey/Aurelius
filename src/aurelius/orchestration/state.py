"""Central research state and audit-trail helpers for the orchestration layer.

`ResearchState` is the single object threaded through every node of the research DAG
(``orchestration.graph``). It is a plain ``TypedDict`` so it JSON-serializes cleanly for
checkpointing — no LangChain/LangGraph state objects involved.
"""
from __future__ import annotations

import datetime
import uuid
from typing import Any, Dict, List, Optional, TypedDict


class ResearchState(TypedDict, total=False):
    """Immutable-by-convention state passed between agents/nodes.

    Nodes return an updated copy (they may mutate in place; the graph treats the returned
    value as authoritative). Every key is optional so partial states checkpoint cleanly.
    """

    topic: str
    hypothesis: str
    alternative_hypotheses: List[Dict[str, Any]]
    gaps: List[str]
    literature_summary: str
    candidate_citations: List[str]
    experiment_design: str
    experiment_code: str
    sandbox_result: Dict[str, Any]
    evidence_ledger: List[Dict[str, Any]]
    verification_report: Dict[str, Any]
    adversarial_review: str
    paper_draft: str
    latex: str
    proof_of_rigor: str
    publication_urls: List[str]
    # bookkeeping
    approved: bool
    screen_reason: str
    researcher_id: str
    session_id: str
    created_at: str
    metadata: Dict[str, Any]
    audit_trail: List[Dict[str, Any]]


def now_iso() -> str:
    """UTC timestamp in ISO-8601, used for every audit entry."""
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def new_session_id() -> str:
    """Short, collision-resistant session id (also the checkpoint filename stem)."""
    return uuid.uuid4().hex[:16]


def new_state(
    topic: str,
    researcher_id: str = "local",
    session_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> ResearchState:
    """Build a fresh state for a research session with all collections initialized."""
    return ResearchState(
        topic=topic,
        hypothesis="",
        alternative_hypotheses=[],
        gaps=[],
        literature_summary="",
        candidate_citations=[],
        experiment_design="",
        experiment_code="",
        sandbox_result={},
        evidence_ledger=[],
        verification_report={},
        adversarial_review="",
        paper_draft="",
        latex="",
        proof_of_rigor="",
        publication_urls=[],
        approved=True,  # optimistic; the hypothesis validator can flip this to False
        screen_reason="",
        researcher_id=researcher_id,
        session_id=session_id or new_session_id(),
        created_at=now_iso(),
        metadata=metadata or {},
        audit_trail=[],
    )


def _summarize(result: Any, limit: int = 400) -> Any:
    """Compact a result for the audit trail so checkpoints stay small and JSON-safe."""
    if isinstance(result, str):
        return result if len(result) <= limit else result[:limit] + "…"
    if isinstance(result, (list, tuple)):
        return {"type": "list", "len": len(result)}
    if isinstance(result, dict):
        return {"keys": sorted(result.keys())}
    return result


def record(
    state: ResearchState,
    agent: str,
    action: str,
    result: Any = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Append an audit entry to ``state['audit_trail']`` and return the entry.

    Every agent action flows through here, so the trail is a complete, timestamped,
    JSON-serializable record of who did what — the observability guarantee for Phase 1.
    """
    entry = {
        "agent": agent,
        "action": action,
        "timestamp": now_iso(),
        "result": _summarize(result),
        "metadata": metadata or {},
    }
    state.setdefault("audit_trail", []).append(entry)
    return entry
