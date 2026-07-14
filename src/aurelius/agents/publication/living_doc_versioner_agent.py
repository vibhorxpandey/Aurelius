"""LivingDocVersionerAgent — append an immutable version entry for the run (Phase 3).

A "living document" evolves over time; this agent records each run as a version in an
append-only ledger (`<output_dir>/living_docs/<topic-slug>.jsonl`), keyed by the run's
Proof-of-Rigor content hash. Successive runs on the same topic accrue a verifiable, ordered
history — the lightweight, local form of the Phase 3 "living documents with version control"
goal (git/IPFS-backed versioning can layer on top later).
"""
from __future__ import annotations

import json
import re

from ...config import get_output_dir
from ...orchestration.state import ResearchState, now_iso
from ..base import ResearchAgent


class LivingDocVersionerAgent(ResearchAgent):
    def __init__(self, **kwargs) -> None:
        super().__init__(
            name="Living Doc Versioner",
            role="Append an immutable, content-hash-keyed version entry for the run",
            **kwargs,
        )

    def execute(self, state: ResearchState) -> ResearchState:
        proof = state.get("proof", {}) or {}
        slug = _slug(state.get("topic", "untitled")) or "untitled"
        path = get_output_dir() / "living_docs" / f"{slug}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)

        version = sum(1 for _ in path.open(encoding="utf-8")) + 1 if path.exists() else 1
        entry = {
            "version": version,
            "ts": now_iso(),
            "session_id": state.get("session_id", ""),
            "content_hash": proof.get("content_hash"),
            "ipfs_cid": (proof.get("ipfs") or {}).get("cid"),
            "verification_score": (state.get("verification_report", {}) or {}).get("verification_score"),
            "hypothesis": state.get("hypothesis", ""),
        }
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, default=str) + "\n")

        state["living_doc"] = {"path": str(path), "version": version, "content_hash": entry["content_hash"]}
        return self.log(state, "update_living_doc", f"v{version} @ {slug}",
                        {"version": version, "path": str(path)})


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60]
