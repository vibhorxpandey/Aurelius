"""Retraction watcher (Phase 5): re-check previously verified citations.

A paper you cited last month can be retracted today. This module re-runs Aurelius's
retraction-aware ``verify_citation`` over citations that were verified earlier — either an
explicit list, or every citation recorded in the saved Proof-of-Rigor bundles under the
output directory — and reports anything whose status has degraded (newly retracted, or no
longer verifiable).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..config import get_output_dir
from .scholarly import verify_citation


def recheck_references(references: List[str]) -> Dict[str, Any]:
    """Re-verify a list of citation strings now. Returns per-item verdicts plus an
    `alerts` list containing only the items that are retracted or no longer verified."""
    items = []
    alerts = []
    for ref in references:
        ref = (ref or "").strip()
        if not ref:
            continue
        r = verify_citation(ref)
        entry = {
            "citation": ref,
            "verdict": r["verdict"],
            "is_retracted": r.get("is_retracted", False),
            "notes": r.get("notes", ""),
        }
        items.append(entry)
        if r.get("is_retracted") or r["verdict"] != "verified":
            alerts.append(entry)

    return {
        "ok": True,
        "checked": len(items),
        "alerts": alerts,
        "retracted": sum(1 for a in alerts if a["is_retracted"]),
        "items": items,
        "note": (f"{len(alerts)} of {len(items)} citation(s) need attention."
                 if alerts else f"All {len(items)} citation(s) still verify cleanly."),
    }


def _citations_from_proofs(proof_dir: Path) -> List[str]:
    """Pull every citation-type ledger claim out of the saved proof bundles."""
    citations: List[str] = []
    seen = set()
    for path in sorted(proof_dir.glob("proof_*.json")):
        try:
            bundle = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for item in bundle.get("payload", {}).get("evidence_ledger", []):
            claim = item.get("claim", "")
            if item.get("type") == "citation" and claim and claim not in seen:
                seen.add(claim)
                citations.append(claim)
    return citations


def retraction_watch(references: Optional[List[str]] = None) -> Dict[str, Any]:
    """Re-check citations for retractions/verification drift.

    Args:
        references: Citation strings to re-check. If omitted, scans every saved
            Proof-of-Rigor bundle in the output directory and re-checks all citations
            recorded there.

    Returns recheck results plus `sessions_scanned` when running from saved proofs.
    """
    if references:
        return recheck_references(references)

    proof_dir = get_output_dir() / "proofs"
    if not proof_dir.is_dir():
        return {"ok": True, "checked": 0, "alerts": [], "retracted": 0, "items": [],
                "note": "No saved proof bundles found - nothing to watch yet."}

    citations = _citations_from_proofs(proof_dir)
    result = recheck_references(citations)
    result["sessions_scanned"] = len(list(proof_dir.glob("proof_*.json")))
    return result
