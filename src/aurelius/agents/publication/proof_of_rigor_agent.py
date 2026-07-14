"""ProofOfRigorAgent — a deterministic, human-readable attestation of the process.

Phase 1's Proof-of-Rigor is a transparent audit summary (not yet the Phase 3 cryptographic
signature / IPFS anchor): it records how many agents ran, the verification score, and the
retraction count, all derived from the state's own audit trail and Evidence Ledger. No LLM.
"""
from __future__ import annotations

from ...orchestration.state import ResearchState, now_iso
from ..base import ResearchAgent


class ProofOfRigorAgent(ResearchAgent):
    def __init__(self, **kwargs) -> None:
        super().__init__(
            name="Proof of Rigor",
            role="Attest to the rigor of the process from the audit trail",
            **kwargs,
        )

    def execute(self, state: ResearchState) -> ResearchState:
        report = state.get("verification_report", {})
        counts = report.get("counts", {})
        trail = state.get("audit_trail", [])
        agents_run = sorted({e["agent"] for e in trail if e.get("agent") != "graph"})
        lines = [
            "# Proof of Rigor (Phase 1 — process attestation)",
            f"- Session: {state.get('session_id','')}",
            f"- Generated: {now_iso()}",
            f"- Agents executed: {len(agents_run)} ({', '.join(agents_run)})",
            f"- Audit-trail entries: {len(trail)}",
            f"- Verification score: {report.get('verification_score', 0.0):.0%}",
            f"- Citations/claims checked: {counts.get('total', 0)} "
            f"(verified {counts.get('verified', 0)}, retracted {counts.get('retracted', 0)}, "
            f"unverified {counts.get('unverified', 0)})",
        ]
        if counts.get("retracted"):
            lines.append("- ⚠️ Retracted source(s) detected during verification.")
        state["proof_of_rigor"] = "\n".join(lines)
        return self.log(state, "proof_of_rigor", state["proof_of_rigor"], {"agents_run": len(agents_run)})
