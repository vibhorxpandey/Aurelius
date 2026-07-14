"""ProofOfRigorAgent — build a cryptographic, tamper-evident attestation of the run (Phase 3).

Phase 1 shipped this as a plain-text process summary. Phase 3 upgrades it: it builds a signed
content-hash proof bundle (``proof.rigor``), optionally pins it to IPFS and anchors the hash
on-chain (both graceful no-ops when unconfigured), writes the bundle to disk, and records the
content hash + signature + any IPFS/anchor references into the state. The human-readable
summary is retained for convenience.
"""
from __future__ import annotations

from ...orchestration.state import ResearchState, now_iso
from ...proof import anchor, ipfs, rigor
from ..base import ResearchAgent


class ProofOfRigorAgent(ResearchAgent):
    def __init__(self, **kwargs) -> None:
        super().__init__(
            name="Proof of Rigor",
            role="Produce a signed, tamper-evident cryptographic attestation of the run",
            **kwargs,
        )

    def execute(self, state: ResearchState) -> ResearchState:
        bundle = rigor.build_proof(state)
        bundle["ipfs"] = ipfs.pin_json(bundle)                      # graceful no-op w/o key
        bundle["anchor"] = anchor.anchor_hash(bundle["content_hash"], state.get("session_id", ""))
        path = rigor.save_proof(bundle, state.get("session_id"))

        state["proof"] = bundle
        state["proof_of_rigor"] = self._render(state, bundle, path)
        return self.log(
            state, "proof_of_rigor", bundle["content_hash"],
            {"sig_algo": bundle["sig_algo"], "ipfs_pinned": bundle["ipfs"].get("pinned"),
             "anchored": bundle["anchor"].get("anchored"), "path": path},
        )

    @staticmethod
    def _render(state: ResearchState, bundle: dict, path: str) -> str:
        vr = state.get("verification_report", {}) or {}
        mr = state.get("methodology_report", {}) or {}
        trail = state.get("audit_trail", [])
        agents_run = sorted({e["agent"] for e in trail if e.get("agent") != "graph"})
        lines = [
            "# Proof of Rigor (Phase 3 — cryptographic attestation)",
            f"- Session: {bundle.get('session_id','')}",
            f"- Generated: {now_iso()}",
            f"- Content hash (sha256): `{bundle['content_hash']}`",
            f"- Signature: {bundle['sig_algo']}"
            + (f" (pubkey {bundle['public_key'][:16]}…)" if bundle.get("public_key") else ""),
            f"- IPFS: {'pinned '+ (bundle['ipfs'].get('url') or '') if bundle['ipfs'].get('pinned') else 'not pinned'}",
            f"- Anchor: {'on-chain '+ str(bundle['anchor'].get('chain',{}).get('tx_hash','')) if bundle['anchor'].get('chain',{}).get('anchored') else 'local log'}",
            f"- Agents executed: {len(agents_run)} ({', '.join(agents_run)})",
            f"- Verification score: {vr.get('verification_score', 0.0):.0%} "
            f"({(vr.get('counts') or {}).get('total', 0)} checked)",
            f"- Methodology risk: {mr.get('risk','n/a')} (score {mr.get('risk_score','n/a')})",
            f"- Proof bundle: {path}",
            "",
            "Verify with: aurelius.proof.verify_proof(json.load(open(<path>))).",
        ]
        return "\n".join(lines)
